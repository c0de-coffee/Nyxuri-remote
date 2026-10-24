"""Deps core — the CORE_DEPS checklist as a status table.

Rows are read-only; one action installs everything missing (disclosed and
confirmed first, then the whole pacman/AUR round-trip runs in a handed-off
terminal — same call as ``nyxuri deps core``).
"""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from nyxuri.core import msg
from nyxuri.market import actions
from nyxuri.market.modals import ConfirmModal, plain


class DepsCoreScreen(Screen):
    BINDINGS = [
        Binding("i", "install", "Install"),
        Binding("r", "reload", "Refresh"),
        Binding("q,escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield DataTable(id="deps-core-table", cursor_type="row", zebra_stripes=True)
        yield Static(msg("deps_core_hint"), id="hint-bar")

    def on_mount(self) -> None:
        table = self.query_one("#deps-core-table", DataTable)
        table.border_title = plain(msg("dep_menu_title").strip())
        table.add_column("dep", key="dep")
        table.add_column("status", key="status", width=16)
        self._reload()

    def on_show(self) -> None:
        self._reload()

    def _reload(self) -> None:
        table = self.query_one("#deps-core-table", DataTable)
        table.clear()
        self._rows = self.app.data.core_deps()
        for row in self._rows:
            style = "green" if row["installed"] else "yellow"
            table.add_row(row["name"], Text(plain(msg("installed" if row["installed"] else "missing")), style=style))

    @property
    def _missing(self) -> list:
        return [row["name"] for row in self._rows if not row["installed"]]

    def action_install(self) -> None:
        missing = self._missing
        if not missing:
            self.notify(plain(msg("deps_core_all_present")))
            return

        def _confirmed(answer: bool) -> None:
            if not answer:
                return
            ok = self.app.handoff(actions.install_missing_core, missing)
            self._reload()
            self.notify(
                plain(msg("opt_apps_install_done" if ok else "log_official_pkgs_partial_fail")),
                severity="information" if ok else "error",
            )

        self.app.push_screen(
            ConfirmModal(", ".join(missing) + "\n" + plain(msg("cli_confirm_install")).strip()),
            callback=_confirmed,
        )

    def action_reload(self) -> None:
        self._reload()

    def action_back(self) -> None:
        self.app.pop_screen()
