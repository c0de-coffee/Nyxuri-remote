"""Home — the market directory: one entry per destination screen."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import OptionList

from nyxuri.core import msg


class HomeScreen(Screen):
    """The single navigation hub; every destination is one keystroke away."""

    BINDINGS = [
        Binding("q", "quit_app", "Quit"),
        Binding("L", "language", "Language"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # (label key, screen factory) — built lazily so adding a screen in a
        # later milestone is a one-line change here.
        self._entries = self._build_entries()

    def _build_entries(self):
        from nyxuri.market.screens.clean import CleanScreen
        from nyxuri.market.screens.components import ComponentsScreen
        from nyxuri.market.screens.deps_apps import DepsAppsScreen
        from nyxuri.market.screens.deps_core import DepsCoreScreen
        from nyxuri.market.screens.doctor import DoctorScreen
        from nyxuri.market.screens.presets import PresetsScreen
        from nyxuri.market.screens.snapshots import SnapshotsScreen
        from nyxuri.market.screens.uninstall import UninstallScreen
        from nyxuri.market.screens.update import UpdateScreen
        from nyxuri.market.screens.workshop import WorkshopScreen

        return [
            # 单元
            ("menu_opt_workshop", lambda: WorkshopScreen()),
            ("menu_opt_preset", lambda: PresetsScreen()),
            # 部署
            ("menu_opt1", lambda: ComponentsScreen(mode="full")),
            ("menu_opt2", lambda: DepsCoreScreen()),
            ("market_deps_apps", lambda: DepsAppsScreen()),
            # 管理
            ("menu_opt3", lambda: SnapshotsScreen()),
            ("menu_opt4", lambda: UpdateScreen()),
            ("market_clean", lambda: CleanScreen()),
            ("menu_opt7", lambda: UninstallScreen()),
            # 诊断
            ("menu_opt5", lambda: DoctorScreen()),
        ]

    def compose(self) -> ComposeResult:
        option_list = OptionList(id="home-list")
        option_list.border_title = msg("market_home_title")
        yield option_list
        yield self.hint_bar()

    def hint_bar(self):
        from textual.widgets import Static

        return Static(msg("market_home_hint"), id="hint-bar")

    def on_mount(self) -> None:
        self._reload()

    def _reload(self) -> None:
        option_list = self.query_one("#home-list", OptionList)
        previous = option_list.highlighted
        option_list.clear_options()
        from textual.widgets.option_list import Option

        for label_key, factory in self._entries:
            option_list.add_option(Option(msg(label_key), id=label_key))
        if len(self._entries):
            if previous is None or previous < 0:
                option_list.highlighted = 0
            else:
                option_list.highlighted = min(previous, len(self._entries) - 1)
        option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        for label_key, factory in self._entries:
            if event.option.id == label_key:
                self.app.push_screen(factory())
                return

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_language(self) -> None:
        from nyxuri.market.screens.language import LanguageModal

        self.app.push_screen(LanguageModal())
