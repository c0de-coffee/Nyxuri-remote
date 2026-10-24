"""Unit Workshop — the ledger on screen, one transaction path underneath.

Dual pane: left = every unit with its state, right = the focused unit's
manifest declarations joined with its ledger record and reconciliation
verdict. ``o``/``f`` route through the exact same transaction calls as the
CLI verbs; missing-package installs (and only those) hand the terminal off.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from nyxuri.core import msg
from nyxuri.market import actions
from nyxuri.market.modals import ConfirmModal, ReportModal
from nyxuri.ux import format_steps


class WorkshopScreen(Screen):
    BINDINGS = [
        Binding("o", "switch_on", "On"),
        Binding("f", "switch_off", "Off"),
        Binding("r", "refresh", "Refresh"),
        Binding("q,escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Horizontal(
            OptionList(id="workshop-units"),
            Static(id="workshop-detail", expand=True),
            id="screen-body",
        )
        yield Static(msg("workshop_hint"), id="hint-bar")

    def on_mount(self) -> None:
        self.border_title = msg("workshop_title")
        self._reload()

    def on_show(self) -> None:
        # Returning from a result view: re-read the ledger (cache protocol).
        self._reload()

    def _reload(self) -> None:
        data = self.app.data
        rows = data.unit_rows()
        self._uids = [row["uid"] for row in rows]
        option_list = self.query_one("#workshop-units", OptionList)
        option_list.clear_options()
        option_list.border_title = msg("workshop_left_header")
        for row in rows:
            option_list.add_option(self._unit_option(row))
        if not option_list.highlighted or option_list.highlighted < 0:
            option_list.highlighted = 0
        option_list.focus()
        self._render_detail()

    def _unit_option(self, row: dict) -> Option:
        from rich.text import Text

        state = row["state"]
        style = "green" if state == "enabled" else ("bright_black" if state in ("disabled", "-") else "yellow")
        return Option(
            Text.assemble(
                (f"{row['uid']:<24}", ""),
                (state, style),
            ),
        )

    def _focused_uid(self) -> str:
        option_list = self.query_one("#workshop-units", OptionList)
        if option_list.highlighted is None:
            return ""
        return self._uids[option_list.highlighted] if self._uids else ""

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        self._render_detail()

    def _render_detail(self) -> None:
        from rich.text import Text
        from rich.table import Table

        detail_pane = self.query_one("#workshop-detail", Static)
        uid = self._focused_uid()
        if not uid:
            detail_pane.update(Text(msg("cli_list_none")))
            return
        detail = self.app.data.unit_detail(uid)

        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim", no_wrap=True)
        grid.add_column()

        def row(key: str, value: str) -> None:
            if value:
                grid.add_row(msg(key), value)

        state_text = Text(detail.state)
        state_text.stylize(
            "green" if detail.state == "enabled"
            else "bright_black" if detail.state in ("disabled", "-") else "yellow"
        )
        grid.add_row(msg("cli_detail_state"), state_text)
        row("cli_detail_preset", detail.preset)
        row("cli_detail_label", detail.label)
        row("cli_detail_category", detail.category)
        row("cli_detail_packages", ", ".join(detail.packages))
        row("cli_detail_dependencies", ", ".join(detail.dependencies))
        row("cli_detail_privilege", detail.privilege)
        if detail.audit:
            audit_text = Text(detail.audit)
            audit_text.stylize(
                "green" if detail.audit == "Synced"
                else "yellow" if detail.audit == "Drifted" else "red"
            )
            grid.add_row(msg("cli_detail_audit"), audit_text)
        row("cli_detail_vault", detail.vault)

        from rich.console import Group

        detail_pane.update(Group(Text(detail.uid, style="bold"), grid))

    # -- actions ----------------------------------------------------------
    # Synchronous + dismiss callbacks on purpose: an action that awaits a
    # modal result keeps the message pump busy and deadlocks Pilot.press
    # (which waits for the app to go idle). Push, return, resume in the
    # callback.

    def action_switch_on(self) -> None:
        uid = self._focused_uid()
        if not uid:
            return
        incoming, missing = actions.plan_on_disclosure(uid)
        if not missing:
            self._after_switch(actions.switch_on(uid))
            return
        disclose = msg("cli_plan_packages", uid, ", ".join(missing))

        def _confirmed(answer: bool) -> None:
            if not answer:
                return
            # Package installs own the terminal: hand it off for the whole
            # transaction, exactly like the CLI verb.
            steps = self.app.handoff(actions.switch_on, uid)
            self._after_switch(steps)

        self.app.push_screen(
            ConfirmModal(disclose + "\n" + msg("cli_confirm_install").strip()),
            callback=_confirmed,
        )

    def action_switch_off(self) -> None:
        uid = self._focused_uid()
        if not uid:
            return

        def _confirmed(answer: bool) -> None:
            if not answer:
                return
            self._after_switch(actions.switch_off(uid))

        self.app.push_screen(
            ConfirmModal(msg("workshop_confirm_off_modal"), danger=True),
            callback=_confirmed,
        )

    def action_refresh(self) -> None:
        self.app.data.invalidate()
        self._reload()

    def action_back(self) -> None:
        self.app.pop_screen()

    def _after_switch(self, steps) -> None:
        self.app.data.invalidate()
        self._reload()
        self.app.push_screen(
            ReportModal(msg("workshop_title"), format_steps(steps))
        )
