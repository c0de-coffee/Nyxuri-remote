"""Components — the master checklist behind install/update deploys.

Radio for the window manager (one WM per machine), checkboxes for app
configs, the heavy wallpaper pack, and the pre-deploy snapshot. Confirming
hands the terminal off: the deploy pipeline, sudo preflight and completion
screen run exactly as on the CLI and land in scrollback.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, RadioButton, RadioSet, Static

from nyxuri.core import msg
from nyxuri.market import actions
from nyxuri.market.modals import ConfirmModal, plain


class ComponentsScreen(Screen):
    BINDINGS = [
        Binding("enter,ctrl+enter", "confirm", "Deploy"),
        Binding("q,escape", "back", "Back"),
    ]

    def __init__(self, mode: str = "full", update: bool = False) -> None:
        super().__init__()
        self._mode = mode
        self._update = update  # deploy through execute_update_deploy (carry)

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="components-scroll")
        yield Static(msg("components_hint"), id="hint-bar")

    def on_mount(self) -> None:
        self.border_title = msg("master_menu_title").strip()
        scroll = self.query_one("#components-scroll", VerticalScroll)
        self._options = self.app.data.component_options(self._mode)
        self._build(scroll)

    def _build(self, scroll) -> None:
        from rich.text import Text

        scroll.remove_children()
        if self._options["wms"]:
            scroll.mount(Static(Text(msg("master_item_wm_section").strip(), style="bold cyan")))
            radio_buttons = [
                RadioButton(
                    plain(f"{msg('master_item_config', wm['name'])} {self._wm_status(wm)}"),
                    value=wm["selected"], id=f"wm-{wm['name']}",
                )
                for wm in self._options["wms"]
            ]
            scroll.mount(RadioSet(*radio_buttons, id="wm-set"))
        scroll.mount(Static(Text(msg("master_item_apps_section").strip(), style="bold cyan")))
        for app in self._options["apps"]:
            status = ""
            if app["optional"]:
                status = plain(msg("installed" if app["installed"] else "missing"))
            scroll.mount(Checkbox(
                f"{msg('master_item_config', app['name'])}  {status}".rstrip(),
                value=app["selected"], id=f"app-{app['name']}",
            ))
        if self._options["wallpapers"]:
            status = plain(msg(
                "status_wallpapers_installed" if self._options["wallpapers_present"]
                else "status_wallpapers_missing"
            ))
            scroll.mount(Checkbox(
                msg("master_item_asset", status),
                value=not self._options["wallpapers_present"], id="assets-wallpapers",
            ))
        scroll.mount(Static(Text(msg("master_item_behavior").strip(), style="bold cyan")))
        scroll.mount(Checkbox(msg("master_item_backup"), value=True, id="behavior-backup"))
        scroll.mount(Button(msg("components_deploy"), id="components-confirm", variant="primary"))

    def _wm_status(self, wm: dict) -> str:
        if wm["running"]:
            return plain(msg("running"))
        if wm["installed"]:
            return plain(msg("installed"))
        return plain(msg("missing"))

    def _collect(self) -> dict:
        chosen_configs = []
        for wm in self._options["wms"]:
            btn = self.query(f"#wm-{wm['name']}")
            if btn and btn.first().value:
                chosen_configs.append(wm["name"])
        for app in self._options["apps"]:
            box = self.query_one(f"#app-{app['name']}", Checkbox)
            if box.value:
                chosen_configs.append(app["name"])
        wallpapers_asset = False
        try:
            wallpapers_asset = self.query_one("#assets-wallpapers", Checkbox).value
        except Exception:
            pass
        backup = self.query_one("#behavior-backup", Checkbox).value
        return {"configs": chosen_configs, "wallpapers": wallpapers_asset, "backup": backup}

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "components-confirm":
            self.action_confirm()

    def action_confirm(self) -> None:
        chosen = self._collect()
        scope = msg("components_update_scope") if self._update else msg("components_install_scope")

        def _confirmed(answer: bool) -> None:
            if not answer:
                return

            def _deploy() -> bool:
                if self._update:
                    return actions.update_deploy(chosen)
                return actions.install_configs(self._mode, chosen)

            ok = self.app.handoff(_deploy)
            self.app.data.invalidate()
            self.app.notify(
                plain(msg("components_deploy_done" if ok else "components_deploy_failed")),
                severity="information" if ok else "error",
            )

        self.app.push_screen(ConfirmModal(scope, danger=self._update), callback=_confirmed)

    def action_back(self) -> None:
        self.app.pop_screen()
