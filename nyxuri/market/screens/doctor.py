"""Doctor — the three-state reconciliation table plus the system checkup.

The audit is a projection (in-App table); the full system checkup and the
bug-report export are linear engine runs — they leave through handoff so
their output lands in scrollback exactly as on the CLI.
"""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from nyxuri.core import msg
from nyxuri.kernel.transaction import (
    STATE_DRIFTED,
    STATE_GHOST,
    STATE_SYNCED,
)

_VERDICT_STYLE = {
    STATE_SYNCED: "green",
    STATE_DRIFTED: "yellow",
    STATE_GHOST: "red",
}


class DoctorScreen(Screen):
    BINDINGS = [
        Binding("s", "checkup", "Checkup"),
        Binding("b", "bug_report", "Report"),
        Binding("r", "reload", "Refresh"),
        Binding("q,escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield DataTable(id="doctor-table", cursor_type="row", zebra_stripes=True)
        yield Static(msg("doctor_hint"), id="hint-bar")

    def on_mount(self) -> None:
        table = self.query_one("#doctor-table", DataTable)
        table.border_title = msg("doctor_title")
        table.add_column(msg("cli_detail_audit"), key="verdict", width=10)
        table.add_column("unit", key="unit")
        self._reload()

    def on_show(self) -> None:
        self._reload()

    def _reload(self) -> None:
        table = self.query_one("#doctor-table", DataTable)
        table.clear()
        report = self.app.data.audit_report()
        if not report:
            table.add_row(Text(msg("cli_audit_clean"), style="green"), "")
            return
        for uid in sorted(report):
            verdict = report[uid]
            table.add_row(Text(verdict, style=_VERDICT_STYLE.get(verdict, "")), uid)
        if STATE_DRIFTED in report.values():
            self.notify(msg("cli_audit_drifted_hint"), severity="warning")
        if STATE_GHOST in report.values():
            self.notify(msg("cli_audit_ghost_hint"), severity="warning")

    def action_checkup(self) -> None:
        """Full system checkup: linear output belongs in the terminal."""
        from nyxuri.sysdoctor import run_doctor
        from nyxuri.ux import press_any_key

        def _run() -> None:
            run_doctor()
            press_any_key()

        self.app.handoff(_run)
        self.app.data.invalidate()
        self._reload()

    def action_bug_report(self) -> None:
        from nyxuri.sysdoctor import generate_bug_report
        from nyxuri.ux import press_any_key

        def _run() -> None:
            generate_bug_report()
            press_any_key()

        self.app.handoff(_run)

    def action_reload(self) -> None:
        self.app.data.invalidate()
        self._reload()

    def action_back(self) -> None:
        self.app.pop_screen()
