"""Uninstall — the §8 scope checklist.

Group headers + checkboxes straight from state.uninstall's option rows;
confirming (destructive, default No) hands the terminal off so the vault
round-trips, sudo prompts and per-item reports run exactly as on the CLI.
"""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Static

from nyxuri.core import msg
from nyxuri.market import actions
from nyxuri.market.modals import ConfirmModal, plain


class UninstallScreen(Screen):
    BINDINGS = [
        Binding("enter,ctrl+enter", "confirm", "Uninstall"),
        Binding("q,escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="uninstall-scroll")
        yield Static(plain(msg("uninstall_hint").strip()), id="hint-bar")

    def on_mount(self) -> None:
        self.border_title = plain(msg("uninstall_title").strip())
        scroll = self.query_one("#uninstall-scroll", VerticalScroll)
        scroll.remove_children()
        rows = self.app.data.uninstall_options()
        n = 0
        for row in rows:
            if "group" in row:
                scroll.mount(Static(Text(plain(row["group"]).strip(), style="bold cyan")))
            else:
                scroll.mount(Checkbox(plain(row["label"]), value=row["checked"],
                                      id=f"uninstall-{row['key']}"))
                n += 1
        scroll.mount(Button(plain(msg("uninstall_run")), id="uninstall-confirm", variant="error"))

    def _collect(self) -> set:
        rows = self.app.data.uninstall_options()
        selected = set()
        for row in rows:
            if "key" not in row:
                continue
            try:
                box = self.query_one(f"#uninstall-{row['key']}", Checkbox)
            except Exception:
                continue
            if box.value:
                selected.add(row["key"])
        return selected

    def on_button_pressed(self, event) -> None:
        if event.button.id == "uninstall-confirm":
            self.action_confirm()

    def action_confirm(self) -> None:
        selected = self._collect()

        def _confirmed(answer: bool) -> None:
            if not answer:
                return
            ok = self.app.handoff(actions.uninstall, selected)
            self.app.notify(
                plain(msg("uninstall_done" if ok else "uninstall_incomplete")),
                severity="information" if ok else "error",
            )

        self.app.push_screen(ConfirmModal(plain(msg("uninstall_title").strip()), danger=True),
                             callback=_confirmed)

    def action_back(self) -> None:
        self.app.pop_screen()
