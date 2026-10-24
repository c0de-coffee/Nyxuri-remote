"""Architecture contracts for the market layer (T2).

1. Textual is imported ONLY inside nyxuri/market/ — the engine core stays
   pure standard library and every CLI verb runs without the dependency.
2. market/data.py, market/actions.py and market/gate.py never import
   Textual: they must stay testable on machines without a graphics stack.
3. The engine never imports the market (dependency direction: market → ux
   + engine, never the reverse).
"""

import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

from tests.utils import TempEnv

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE = REPO_ROOT / "nyxuri"
MARKET = ENGINE / "market"

TEXTUAL_IMPORTS = ("textual", "rich")  # rich ships with textual; same rule


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module or ""]
        for name in names:
            yield name.split(".")[0]


class TestTextualContainment(unittest.TestCase):
    def test_only_market_imports_textual(self):
        offenders = []
        for py in ENGINE.rglob("*.py"):
            if py.is_relative_to(MARKET):
                continue
            heads = set(_imports(py))
            hit = heads & set(TEXTUAL_IMPORTS)
            if hit:
                offenders.append(f"{py.relative_to(REPO_ROOT)}: {sorted(hit)}")
        self.assertEqual(offenders, [])

    def test_market_core_modules_stay_headless(self):
        for name in ("data.py", "actions.py", "gate.py", "__init__.py"):
            path = MARKET / name
            heads = set(_imports(path))
            self.assertEqual(heads & set(TEXTUAL_IMPORTS), set(),
                             f"market/{name} must not import textual/rich")

    def test_engine_never_imports_market(self):
        """Dependency direction: market → ux + engine, never the reverse.

        The one sanctioned bridge is the composition root: cli.py's
        interactive entry (a lazy import inside main(), so CLI verbs run
        without Textual installed).
        """
        sanctioned = {"cli.py"}
        offenders = []
        for py in ENGINE.rglob("*.py"):
            if py.is_relative_to(MARKET) or py.name in sanctioned:
                continue
            if "nyxuri.market" in py.read_text(encoding="utf-8"):
                offenders.append(str(py.relative_to(REPO_ROOT)))
        self.assertEqual(sorted(offenders), [])

    def test_cli_bridge_is_lazy(self):
        """The market import must sit inside main() so module import (and
        every CLI verb) works on machines without Textual."""
        cli = (ENGINE / "cli.py").read_text(encoding="utf-8")
        self.assertIn("from nyxuri.market import run as run_market", cli)
        # Not a module-level import: no top-level line references it.
        top_level = [
            line for line in cli.splitlines()
            if line.startswith(("import ", "from ")) and "nyxuri.market" in line
        ]
        self.assertEqual(top_level, [])


class TestOldWorldIsDead(unittest.TestCase):
    """T2 verdict: the pre-Textual control panel must not exist on disk.

    A resurrected tui.py/menus.py would silently split the interface in two
    and drag the engine back onto the old control flow.
    """

    def test_old_ui_modules_are_gone(self):
        for rel in ("nyxuri/tui.py", "nyxuri/installer/menus.py"):
            self.assertFalse((REPO_ROOT / rel).exists(), f"{rel} must stay deleted")

    def test_no_module_imports_the_old_ui(self):
        dead = {"nyxuri.tui", "nyxuri.installer.menus"}
        offenders = []
        for py in list(ENGINE.rglob("*.py")) + list((REPO_ROOT / "tests").rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or ""]
                if any(n == d or n.startswith(d + ".") for n in names for d in dead):
                    offenders.append(str(py.relative_to(REPO_ROOT)))
                    break
        self.assertEqual(sorted(offenders), [])


class TestGate(unittest.TestCase):
    def test_find_spec_matches_importability(self):
        from nyxuri.market.gate import textual_available

        self.assertEqual(textual_available(), importlib.util.find_spec("textual") is not None)

    def test_missing_textual_explains_and_exits_nonzero(self):
        """No old-UI fallback: one remediation line, then a clean refusal."""
        import contextlib
        import io
        from unittest.mock import patch

        from nyxuri.market import gate

        with TempEnv(), \
             patch.object(gate, "textual_available", return_value=False), \
             patch.object(gate, "_try_install_textual", return_value=False), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(gate.run(), 1)
        self.assertIn("python-textual", out.getvalue())

    def test_engine_runs_without_site_packages(self):
        """`python3 -S` proves no engine import needs an installed dependency."""
        import os
        import subprocess
        import sys

        env = dict(os.environ, HOME=tempfile.mkdtemp(prefix="nyxuri-nosite-"))
        proc = subprocess.run(
            [sys.executable, "-S", "-m", "nyxuri", "help"],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("nyxuri", proc.stdout)


if __name__ == "__main__":
    unittest.main()
