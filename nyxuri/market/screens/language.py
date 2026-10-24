"""Language selection modal — parity with the pre-Textual select_language."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class LanguageModal(ModalScreen[None]):
    """中文 / English. Shown at startup only when no locale hint exists;
    otherwise reachable any time via the ``L`` binding. Cancel keeps the
    locale-derived language."""

    BINDINGS = [Binding("escape,q", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        yield Label("── 请选择语言 / Select Language ──")
        with Horizontal(id="lang-buttons"):
            yield Button("English", id="en")
            yield Button("简体中文", id="zh")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._apply(event.button.id)

    def _apply(self, lang: str) -> None:
        self.dismiss(None)
        self.app.apply_language(lang)

    def action_cancel(self) -> None:
        self.dismiss(None)
