"""Market App skeleton: global chrome, language handling, and handoff().

The App owns the terminal. Selection and browsing live in screens; execution
(pacman, the deploy pipeline, diff pagers, $EDITOR) leaves through
``handoff`` — ``app.suspend()`` hands the cooked terminal to the engine, the
linear progress and completion screens stay in scrollback, and control
returns to the App when the call finishes. Light switches that need no
external program never suspend at all.
"""

import os

from textual.app import App
from textual.widgets import Header

from nyxuri.core import get_env, set_lang
from nyxuri.market.data import MarketData


def locale_known() -> bool:
    """A usable locale hint exists — the language screen can be skipped."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if os.environ.get(var, "").strip():
            return True
    return False


class MarketApp(App):
    """Nyxuri 桌面插件市场 — the interactive face of the four verbs."""

    TITLE = "Nyxuri"
    SUB_TITLE = ""
    theme = "ansi-dark"

    CSS = """
Screen, App {
    layout: vertical;
    background: ansi_default;
}
Header {
    background: ansi_default;
}
OptionList, DataTable, Tree, Static, VerticalScroll {
    background: ansi_default;
}
OptionList:focus {
    background-tint: transparent;
}
#screen-body {
    height: 1fr;
    background: ansi_default;
}
#hint-bar {
    dock: bottom;
    height: 1;
    background: ansi_default;
    color: $text-muted;
    padding: 0 1;
}
#home-list {
    margin: 0 1;
    border: round $primary;
    background: ansi_default;
}
#workshop-units {
    width: 1fr;
    margin: 0 0 0 1;
    border: round $primary;
    background: ansi_default;
}
#workshop-detail {
    width: 2fr;
    margin: 0 1 0 0;
    padding: 0 1;
    border: round $primary;
    background: ansi_default;
}
#lang-buttons {
    height: auto;
    width: auto;
    align-horizontal: center;
}
#lang-buttons Button {
    margin: 0 1;
}
#screen-title {
    dock: top;
    height: 1;
    background: ansi_default;
    color: $text;
    padding: 0 1;
}
ConfirmModal, InputModal, ReportModal {
    align: center middle;
    background: ansi_default;
}
ConfirmModal Label, InputModal Label {
    width: auto;
    margin: 0 2 1 2;
}
#modal-buttons {
    height: auto;
    width: auto;
    layout: horizontal;
    align-horizontal: center;
}
#modal-buttons Button {
    margin: 0 1;
}
InputModal Input {
    width: 60%;
}
ReportModal {
    padding: 1 2;
}
#report-body {
    max-height: 70%;
    width: 90%;
    border: round $primary;
    padding: 0 1;
}
#report-hint {
    color: $text-muted;
    width: 90%;
}
"""

    def __init__(self) -> None:
        super().__init__()
        self.data = MarketData()
        env = get_env()
        self.SUB_TITLE = f"{env.version} · {env.mode_label}"

    def compose(self):
        yield Header(show_clock=False)

    def on_mount(self) -> None:
        from nyxuri.market.screens.home import HomeScreen
        from nyxuri.market.screens.language import LanguageModal

        self.push_screen(HomeScreen())
        if not locale_known():
            self.push_screen(LanguageModal())

    # -- terminal handoff -------------------------------------------------

    def handoff(self, fn, *args, **kwargs):
        """Run ``fn`` with the terminal handed back to the engine.

        While suspended the App is invisible, the terminal is cooked, and
        engine line output (pacman, prompts, completion screens) behaves
        exactly as on the CLI. Never call for light switches.
        """
        with self.suspend():
            return fn(*args, **kwargs)

    # -- language ---------------------------------------------------------

    def apply_language(self, lang: str) -> None:
        """Switch language and rebuild the screen stack with fresh labels."""
        from nyxuri.market.screens.home import HomeScreen

        set_lang(lang)
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(HomeScreen())
