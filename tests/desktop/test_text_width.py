"""Regression tests for terminal text width, clipping, and clean.py helpers."""

import contextlib
import io
import os
import sys
import unicodedata
import unittest
from pathlib import Path
from unittest.mock import patch

from nyxuri.core import Colors
from nyxuri.ux import display_width, truncate_display


def _reference_width(text: str) -> int:
    total = 0
    for char in text:
        if unicodedata.combining(char) or unicodedata.category(char) in ("Cf", "Mn", "Me"):
            continue
        total += 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
    return total


class TestDisplayWidth(unittest.TestCase):
    def test_zero_width_characters_do_not_consume_columns(self):
        for text in ("a\u200db", "a\u200bb", "\ufeff", "e\u0301", "\u00ad", "a\u200eb", "\u2060"):
            self.assertEqual(display_width(text), _reference_width(text), repr(text))

    def test_cjk_and_ascii_widths(self):
        self.assertEqual(display_width("中文"), 4)
        self.assertEqual(display_width("abc"), 3)

    def test_ansi_sequences_are_not_counted(self):
        self.assertEqual(display_width(f"{Colors.RED}abc{Colors.RESET}"), 3)


class TestTruncateDisplay(unittest.TestCase):
    def test_never_exceeds_requested_width(self):
        pool = list("abc中文🙂") + ["\u200d", "\u0301", "\ufe0f", "\u200b", Colors.RED, Colors.RESET]
        for suffix in ("…", "...", ""):
            for width in range(0, 12):
                for count in range(0, 8):
                    text = "".join(pool[(i * 3 + count) % len(pool)] for i in range(count))
                    self.assertLessEqual(
                        display_width(truncate_display(text, width, suffix=suffix)),
                        width,
                        f"text={text!r} width={width} suffix={suffix!r}",
                    )

    def test_suffix_larger_than_width_is_clipped(self):
        self.assertLessEqual(display_width(truncate_display("hello", 2, suffix="...")), 2)
        self.assertEqual(truncate_display("hello", 1, suffix="…"), "…")
        self.assertEqual(truncate_display("hello", 0), "")

    def test_text_within_width_is_returned_unchanged(self):
        self.assertEqual(truncate_display("abc", 5), "abc")


class TestCleanHelpers(unittest.TestCase):
    def test_tilde_only_shortens_paths_actually_below_home(self):
        import nyxuri.desktop.clean as clean

        with patch.object(clean, "HOME", Path("/home/user")):
            self.assertEqual(clean.tilde("/home/user/.cache"), "~/.cache")
            self.assertEqual(clean.tilde("/home/user"), "~")
            self.assertEqual(clean.tilde("/home/user/.cache/sub"), "~/.cache/sub")
            self.assertEqual(clean.tilde("/home/username/secret"), "/home/username/secret")
            self.assertEqual(clean.tilde("/home/users/data"), "/home/users/data")

    def test_line_form_prompts_survive_stdin_without_fileno(self):
        """The ux line-form prompts must not crash on a pseudo stdin.

        A redirected stdin with isatty()=True but no fileno used to crash
        the raw-mode guard; prompt_confirm must degrade to its default.
        """
        import nyxuri.desktop.clean as clean
        from nyxuri.ux import prompt_confirm

        class NoFileno:
            def isatty(self):
                return True

            def fileno(self):
                raise io.UnsupportedOperation("redirected stdin is pseudofile")

        with patch.object(sys, "stdin", NoFileno()), \
             contextlib.redirect_stdout(io.StringIO()), \
             patch.dict(os.environ, {"NYXURI_AUTO_YES": "0"}):
            self.assertFalse(prompt_confirm("purge_prompt", "n", destructive=True))


if __name__ == "__main__":
    unittest.main()
