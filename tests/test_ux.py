"""Regression tests for the zero-dependency UX base (nyxuri/ux.py).

Covers the line-form contracts the CLI verbs rely on after the Textual
migration: single-key confirm semantics, raw-key EOF handling, the numbered
multi-select parser, and transaction step prose.
"""

import contextlib
import io
import os
import sys
import unittest
from unittest.mock import patch

from nyxuri.ux import _RawKeys, _resolve_confirm, format_steps, prompt_confirm, select_many
from tests.utils import TempEnv


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


class _Stdin:
    def __init__(self, line):
        self._line = line

    def readline(self):
        return self._line


class TestConfirmSemantics(unittest.TestCase):

    def test_yes_is_yes_whatever_the_default(self):
        for default in ("y", "n"):
            self.assertTrue(_resolve_confirm("y", default))
            self.assertTrue(_resolve_confirm("Y", default))

    def test_enter_takes_the_default(self):
        self.assertTrue(_resolve_confirm("ENTER", "y"))
        self.assertFalse(_resolve_confirm("ENTER", "n"))

    def test_closed_terminal_never_consents(self):
        for key in ("EOF", "EXIT", "ESC", "n", ""):
            self.assertFalse(_resolve_confirm(key, "y"), key)

    def test_non_tty_stdin_falls_back_to_default(self):
        with TempEnv(), \
             patch("nyxuri.ux.stdin_fd", return_value=None), \
             patch.dict(os.environ, {"NYXURI_AUTO_YES": "0"}):
            self.assertTrue(_quiet(prompt_confirm, "prompt_install_missing_deps", "y"))
            self.assertFalse(_quiet(prompt_confirm, "prompt_install_missing_deps", "n"))

    def test_raw_key_path_answers_through_the_guard(self):
        """Regression: the guard must hand back the reader, not the raw fd.

        Every real-terminal prompt used to die with
        ``AttributeError: 'int' object has no attribute 'read'`` because
        ``__enter__`` returned ``self.fd``.
        """
        import threading

        r, w = os.pipe()
        for fd in (r, w):
            self.addCleanup(os.close, fd)
        typer = threading.Timer(0.1, os.write, args=(w, b"y"))
        typer.start()
        try:
            with TempEnv(), \
                 patch("nyxuri.ux.stdin_fd", return_value=r), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 patch.dict(os.environ, {"NYXURI_AUTO_YES": "0"}):
                self.assertTrue(prompt_confirm("prompt_install_missing_deps", "n"))
        finally:
            typer.join()


class TestRawKeyReads(unittest.TestCase):

    def _reader(self, payload):
        r, w = os.pipe()
        os.write(w, payload)
        os.close(w)
        raw = _RawKeys()
        raw.fd = r
        self.addCleanup(os.close, r)
        return raw

    def test_named_keys(self):
        for payload, expected in ((b"\r", "ENTER"), (b"\n", "ENTER"), (b"\x1b", "ESC"),
                                  (b"\x03", "EXIT"), (b"\x04", "EXIT"), (b" ", "SPACE"),
                                  (b"a", "a")):
            self.assertEqual(self._reader(payload).read(), expected, payload)

    def test_eof_cancels_instead_of_blocking(self):
        self.assertEqual(self._reader(b"").read(), "EOF")

    def test_no_tty_reads_as_enter(self):
        raw = _RawKeys()
        raw.fd = None
        self.assertEqual(raw.read(), "ENTER")

    def test_terminal_guard_restore_survives_missing_stdin(self):
        """atexit runs after stdin may be closed/None; restore must not raise."""
        from nyxuri.ux import _TerminalGuard

        saved = _TerminalGuard._orig
        try:
            _TerminalGuard._orig = [0, 0, 0, 0, 0, 0, []]
            with patch.object(sys, "stdin", None), contextlib.redirect_stdout(io.StringIO()):
                _TerminalGuard.restore()
            self.assertIsNone(_TerminalGuard._orig)
        finally:
            _TerminalGuard._orig = saved


class TestSelectMany(unittest.TestCase):

    def _pick(self, line, labels=("a", "b", "c")):
        with TempEnv(), patch("sys.stdin", _Stdin(line)):
            return _quiet(select_many, list(labels))

    def test_spaces_commas_and_ranges(self):
        self.assertEqual(self._pick("1 3\n"), [0, 2])
        self.assertEqual(self._pick("1,3\n"), [0, 2])
        self.assertEqual(self._pick("2-3\n"), [1, 2])
        self.assertEqual(self._pick("3 1 3\n"), [0, 2])

    def test_all_returns_every_index(self):
        self.assertEqual(self._pick("all\n"), [0, 1, 2])

    def test_empty_and_eof_cancel(self):
        self.assertIsNone(self._pick("\n"))
        self.assertIsNone(self._pick(""))

    def test_out_of_range_or_garbage_cancels(self):
        for line in ("0\n", "4\n", "3-2\n", "x\n"):
            self.assertIsNone(self._pick(line), line)


class _Step:
    def __init__(self, unit, detail):
        self.unit = unit
        self.detail = detail


class TestFormatSteps(unittest.TestCase):

    def test_marks_track_outcome(self):
        with TempEnv():
            lines = format_steps([
                _Step("kitty", "enabled"),
                _Step("niri", "already-enabled"),
                _Step("mango", "disabled"),
                _Step("fish", "deploy-failed"),
            ])
        self.assertIn("[✓]", lines[0])
        self.assertIn("[•]", lines[1])
        self.assertIn("[✓]", lines[2])
        self.assertIn("[✗]", lines[3])
        for line, unit in zip(lines, ("kitty", "niri", "mango", "fish")):
            self.assertIn(unit, line)

    def test_missing_packages_carry_the_package_list(self):
        with TempEnv():
            lines = format_steps([_Step("kitty", "missing-packages: foot, fzf")])
        self.assertIn("foot, fzf", lines[0])


if __name__ == "__main__":
    unittest.main()
