"""Attendance guard for the market App — the only Textual awareness outside it.

``run()`` never imports Textual unless the module is actually importable:
the engine (and every CLI verb) must keep working on machines without it.
When Textual is missing the guard prints the one-line remediation and,
where pacman exists, offers to install it before relaunching the App.
"""

import importlib.util

from nyxuri.core import msg
from nyxuri.ux import prompt_confirm


def textual_available() -> bool:
    """True when the ``textual`` package can be imported."""
    try:
        return importlib.util.find_spec("textual") is not None
    except (ImportError, ValueError):
        return False


def _try_install_textual() -> bool:
    import shutil

    if not shutil.which("pacman"):
        return False
    if not prompt_confirm("tui_install_textual_prompt", "y"):
        return False
    from nyxuri.pkg import install as pkg_install

    ok = bool(pkg_install(["python-textual"]))
    # A freshly installed package must be visible to the immediate recheck.
    importlib.invalidate_caches()
    return ok


def run() -> int:
    """Enter the market App when possible; otherwise explain and exit 1."""
    if not textual_available():
        print(msg("tui_missing_textual"))
        if _try_install_textual() and textual_available():
            pass  # installed just now — fall through into the App
        else:
            return 1

    # Lazy import: nothing below this line executes without Textual present.
    from nyxuri.market.app import MarketApp

    MarketApp().run()
    return 0
