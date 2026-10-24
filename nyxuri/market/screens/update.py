"""Update — pull, diff, or deploy through the update-grade carry.

``enter`` pulls in a handed-off terminal and, on success, execve's into the
fresh code (the App process is intentionally replaced — deploy must run on
the updated engine; the pending-upgrade marker brings the interactive face
back). ``d`` pages the current living-area diff; ``c`` opens the components
screen in update mode for a carry-grade deploy of the current code.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from nyxuri.core import msg
from nyxuri.market import actions
from nyxuri.market.modals import ConfirmModal, plain


class UpdateScreen(Screen):
    BINDINGS = [
        Binding("enter", "pull", "Pull & update"),
        Binding("d", "diff", "Diff"),
        Binding("c", "deploy", "Deploy"),
        Binding("q,escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield OptionList(
            Option(msg("overwrite_opt1")),
            Option(msg("overwrite_opt2")),
            Option(msg("overwrite_opt3")),
            id="update-list",
        )
        yield Static(msg("update_hint"), id="hint-bar")

    def on_mount(self) -> None:
        self.query_one("#update-list", OptionList).border_title = plain(
            msg("overwrite_title").strip())
        self.query_one("#update-list", OptionList).highlighted = 0
        self.query_one("#update-list", OptionList).focus()

    def on_option_list_option_selected(self, event) -> None:
        {0: self.action_pull, 1: self.action_diff, 2: self.action_back}[
            event.option_list.highlighted or 0
        ]()

    def action_pull(self) -> None:
        def _confirmed(answer: bool) -> None:
            if not answer:
                return
            # Never returns on success: the process is replaced while the
            # terminal is still handed off (cooked, App invisible).
            self.app.handoff(actions.update_pull_and_reexec)

        self.app.push_screen(ConfirmModal(plain(msg("update_confirm_pull"))),
                             callback=_confirmed)

    def action_diff(self) -> None:
        self.app.handoff(actions.view_update_diff)

    def action_deploy(self) -> None:
        from nyxuri.market.screens.components import ComponentsScreen

        self.app.push_screen(ComponentsScreen(mode="full", update=True))

    def action_back(self) -> None:
        self.app.pop_screen()
