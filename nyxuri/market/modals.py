"""Modal interactions: confirm / input / step-report — the only Textual here.

Screens own the flow; these modals own the keystroke plumbing so no screen
re-implements a dialog. All prompts arrive as plain (ANSI-free) strings;
step reports arrive as ``format_steps`` ANSI lines and are converted with
``Text.from_ansi`` so the shared bilingual prose renders identically inside
the App and on the linear CLI.
"""

from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from nyxuri.core import msg
from nyxuri.ux import ANSI_ESCAPE_RE


def plain(line: str) -> str:
    """Strip ANSI from msg() templates — screens style with Textual, not SGR."""
    return ANSI_ESCAPE_RE.sub("", line)


class ConfirmModal(ModalScreen[bool]):
    """Yes/No question. Esc/q = No. Returns via ``push_screen_wait``."""

    BINDINGS = [
        Binding("y,enter", "answer(True)", "Yes"),
        Binding("n", "answer(False)", "No"),
        Binding("escape,q", "answer(False)", "No", show=False),
    ]

    def __init__(self, prompt: str, danger: bool = False) -> None:
        super().__init__()
        self._prompt = prompt
        self._danger = danger

    def compose(self) -> ComposeResult:
        line = Text(self._prompt)
        if self._danger:
            line.stylize("bold red")
        yield Label(line)
        with Static(id="modal-buttons"):
            yield Button(msg("modal_yes"), variant="error" if self._danger else "primary", id="yes")
            yield Button(msg("modal_no"), variant="default", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.action_answer(event.button.id == "yes")

    def action_answer(self, answer: bool) -> None:
        self.dismiss(answer)


class InputModal(ModalScreen[Optional[str]]):
    """One-line text entry. Esc/q = cancel (None)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        yield Label(self._prompt)
        yield Input(id="modal-input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ReportModal(ModalScreen[None]):
    """Multi-line step report (ANSI prose welcome). Any key dismisses."""

    BINDINGS = [
        Binding("enter,space,escape,q", "dismiss_report", "OK", show=False),
    ]

    def __init__(self, title: str, lines: list) -> None:
        super().__init__()
        self._title = title
        self._lines = lines

    def compose(self) -> ComposeResult:
        yield Label(Text(self._title, style="bold cyan"))
        with VerticalScroll(id="report-body"):
            for line in self._lines:
                if isinstance(line, str):
                    yield Static(Text.from_ansi(line))
                else:
                    yield Static(line)
        yield Static(msg("workshop_back_hint"), id="report-hint")

    def action_dismiss_report(self) -> None:
        self.dismiss(None)
