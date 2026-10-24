"""Snapshots — the 30-slot rolling archive, one table.

Create (with a note prompt), delete and rollback all land in handed-off
terminals: their engine halves print per-item progress and finish lines
that belong in scrollback. Destructive actions confirm first, default No.
"""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from nyxuri.core import msg
from nyxuri.market import actions
from nyxuri.market.modals import ConfirmModal, InputModal, plain


class SnapshotsScreen(Screen):
    BINDINGS = [
        Binding("c", "create", "Create"),
        Binding("d", "delete", "Delete"),
        Binding("r", "rollback", "Rollback"),
        Binding("q,escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield DataTable(id="snapshot-table", cursor_type="row", zebra_stripes=True)
        yield Static(msg("snapshot_hint"), id="hint-bar")

    def on_mount(self) -> None:
        table = self.query_one("#snapshot-table", DataTable)
        table.border_title = plain(msg("snapshot_menu_title").strip())
        table.add_column("#", key="index", width=5)
        table.add_column("name", key="name")
        table.add_column("note", key="note")
        self._reload()

    def on_show(self) -> None:
        self._reload()

    def _reload(self) -> None:
        table = self.query_one("#snapshot-table", DataTable)
        table.clear()
        self._rows = self.app.data.snapshots()
        if not self._rows:
            table.add_row("", Text(plain(msg("no_backups_found")), style="dim"), "")
            return
        for row in self._rows:
            table.add_row(str(row["index"]), row["name"],
                          Text(row["note"], style="bright_black"))

    def _focused_index(self) -> int:
        table = self.query_one("#snapshot-table", DataTable)
        if table.cursor_row is None or not self._rows:
            return 0
        row = self._rows[min(table.cursor_row, len(self._rows) - 1)]
        return row["index"]

    def action_create(self) -> None:
        def _named(note) -> None:
            self.app.handoff(actions.snapshot_create, note or "")
            self._reload()

        self.app.push_screen(InputModal(plain(msg("snapshot_note_prompt")).strip()),
                             callback=_named)

    def action_delete(self) -> None:
        if not self._rows:
            return
        index = self._focused_index()
        name = next(r["name"] for r in self._rows if r["index"] == index)

        def _confirmed(answer: bool) -> None:
            if not answer:
                return
            self.app.handoff(actions.snapshot_delete, index)
            self._reload()

        self.app.push_screen(
            ConfirmModal(plain(msg("preset_prompt_delete_confirm", name)), danger=True),
            callback=_confirmed,
        )

    def action_rollback(self) -> None:
        if not self._rows:
            return
        index = self._focused_index()
        name = next(r["name"] for r in self._rows if r["index"] == index)

        def _confirmed(answer: bool) -> None:
            if not answer:
                return
            self.app.handoff(actions.snapshot_rollback, index)
            self._reload()

        self.app.push_screen(
            ConfirmModal(plain(msg("rollback_confirm", name)), danger=True),
            callback=_confirmed,
        )

    def action_back(self) -> None:
        self.app.pop_screen()
