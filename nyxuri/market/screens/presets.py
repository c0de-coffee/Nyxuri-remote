"""Preset Studio — apps × (presets + part slots), actions in place.

The old dual-pane PresetSwitcher semantics, one-for-one: left = apps with
their active preset; right = the focused app's presets and collapsible part
slots. Apply / save / edit / delete ride the same engine calls as the
``nyxuri preset`` verb; ``e`` (the $EDITOR round-trip) hands the terminal
off, everything else is a light in-process call.
"""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from nyxuri.core import msg
from nyxuri.market import actions
from nyxuri.market.modals import ConfirmModal, InputModal, ReportModal, plain


class PresetsScreen(Screen):
    BINDINGS = [
        Binding("tab", "toggle_pane", "Pane"),
        Binding("right,l", "right", "Right"),
        Binding("left,h", "left", "Left"),
        Binding("s", "save", "Save"),
        Binding("e", "edit", "Edit"),
        Binding("d", "delete", "Delete"),
        Binding("i", "inspect", "Details"),
        Binding("q,escape", "back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._expanded: set[tuple[str, str]] = set()

    def compose(self) -> ComposeResult:
        yield Horizontal(
            OptionList(id="preset-apps"),
            OptionList(id="preset-items"),
            id="screen-body",
        )
        yield Static(msg("preset_hint"), id="hint-bar")

    def on_mount(self) -> None:
        self._reload()

    def on_show(self) -> None:
        self._reload()

    # -- data & rendering ---------------------------------------------------

    def _reload(self) -> None:
        data = self.app.data
        apps = data.apps()
        if not apps:
            return
        left = self.query_one("#preset-apps", OptionList)
        left.border_title = msg("preset_left_header")
        left.clear_options()
        for app in apps:
            active = data.active_preset(app)
            presets = data.presets_for(app)
            count = f" ({len(presets)})" if len(presets) > 1 else ""
            left.add_option(Option(Text.assemble(
                (app, ""), (f" {active}{count}", "bright_black"),
            )))
        if left.highlighted is None:
            left.highlighted = 0
        if not isinstance(self.focused, OptionList) or self.focused.id == "preset-apps":
            left.focus()
        self._reload_items()

    def _focused_app(self) -> str:
        left = self.query_one("#preset-apps", OptionList)
        apps = self.app.data.apps()
        if left.highlighted is None or not apps:
            return ""
        return apps[min(left.highlighted, len(apps) - 1)]

    def _reload_items(self) -> None:
        data = self.app.data
        app = self._focused_app()
        right = self.query_one("#preset-items", OptionList)
        right.border_title = f"{msg('preset_right_header')} · {app}" if app else msg("preset_right_header")
        right.clear_options()
        self._items = []
        if not app:
            return
        for row in data.presets_for(app):
            if row["active"] == "true":
                label = Text.assemble((row["name"], "bold cyan"),
                                      (f"  ({row['source']})", "bright_black"),
                                      ("  ●", "green"))
            else:
                label = Text.assemble((row["name"], ""),
                                      (f"  ({row['source']})", "bright_black"))
            right.add_option(Option(label))
            self._items.append({"type": "preset", "name": row["name"]})
        for slot, info in data.parts_for(app).items():
            active = data.active_part(app, slot)
            expanded = (app, slot) in self._expanded
            arrow = "▾" if expanded else "▸"
            right.add_option(Option(Text.assemble(
                (f"{arrow} {msg('preset_part_slot_label')} · {slot}", ""),
                (f"  {active}", "bright_black"),
            )))
            self._items.append({"type": "slot", "slot": slot})
            if expanded:
                for variant in info.get("variants", []):
                    is_active = variant == active
                    mark = " ●" if is_active else ""
                    label = Text.assemble(
                        (f"    {variant}", "bold green" if is_active else ""),
                        (mark, "green"),
                    )
                    right.add_option(Option(label))
                    self._items.append({"type": "variant", "slot": slot, "name": variant})
        if right.highlighted is None and self._items:
            right.highlighted = 0

    def _focused_item(self) -> dict:
        right = self.query_one("#preset-items", OptionList)
        if right.highlighted is None or not self._items:
            return {}
        return self._items[min(right.highlighted, len(self._items) - 1)]

    def on_option_list_option_highlighted(self, event) -> None:
        if event.option_list.id == "preset-apps":
            self._reload_items()

    # -- actions -----------------------------------------------------------

    def action_toggle_pane(self) -> None:
        if self.focused and self.focused.id == "preset-apps":
            self.query_one("#preset-items", OptionList).focus()
        else:
            self.query_one("#preset-apps", OptionList).focus()

    def action_right(self) -> None:
        if self.focused and self.focused.id != "preset-items":
            self.query_one("#preset-items", OptionList).focus()

    def action_left(self) -> None:
        if self.focused and self.focused.id == "preset-items":
            self.query_one("#preset-apps", OptionList).focus()

    def action_back(self) -> None:
        if self.focused and self.focused.id == "preset-items":
            self.query_one("#preset-apps", OptionList).focus()
        else:
            self.app.pop_screen()

    def on_option_list_option_selected(self, event) -> None:
        if event.option_list.id != "preset-items":
            self.action_right()
            return
        self._activate(self._focused_item())

    def _activate(self, item: dict) -> None:
        app = self._focused_app()
        if not app or not item:
            return
        data = self.app.data
        if item["type"] == "preset":
            ok = actions.apply_preset(app, item["name"])
            toast = (msg("preset_toast_applied", app, item["name"]) if ok
                     else msg("preset_apply_failed", app, item["name"]))
            self.notify(plain(toast), severity="information" if ok else "error")
        elif item["type"] == "slot":
            key = (app, item["slot"])
            if key in self._expanded:
                self._expanded.remove(key)
            else:
                self._expanded.add(key)
        elif item["type"] == "variant":
            ok = actions.apply_part(app, item["slot"], item["name"])
            toast = (msg("preset_part_toast_applied", app, item["slot"], item["name"]) if ok
                     else msg("preset_apply_failed", app, f"{item['slot']}:{item['name']}"))
            self.notify(plain(toast), severity="information" if ok else "error")
        data.invalidate("presets")
        self._reload()

    def action_save(self) -> None:
        app = self._focused_app()
        if not app:
            return

        def _named(name) -> None:
            if not name:
                return
            if actions.save_preset(app, name):
                self.notify(plain(msg("preset_toast_saved", app, name)))
            self.app.data.invalidate("presets")
            self._reload()

        self.app.push_screen(InputModal(msg("preset_prompt_save_name").strip()), callback=_named)

    def action_edit(self) -> None:
        app = self._focused_app()
        item = self._focused_item()
        if not app:
            return
        name = item.get("name") if item and item["type"] == "preset" else self.app.data.active_preset(app)
        info = self.app.data.preset_info(app, name)
        if info and not info.is_editable:
            self.notify(plain(msg("preset_edit_official_denied", name)), severity="warning")
            return

        def _done(_ok) -> None:
            self.app.data.invalidate("presets")
            self._reload()

        # $EDITOR owns the terminal while it runs — hand it off.
        ok = self.app.handoff(actions.edit_preset, app, name)
        _done(ok)

    def action_delete(self) -> None:
        app = self._focused_app()
        item = self._focused_item()
        if not app or not item or item["type"] != "preset":
            return
        name = item["name"]
        info = self.app.data.preset_info(app, name)
        if info and not info.is_deletable:
            self.notify(plain(msg("preset_delete_official_denied", name)), severity="warning")
            return

        def _confirmed(answer) -> None:
            if not answer:
                return
            if actions.delete_preset(app, name):
                self.notify(plain(msg("preset_toast_deleted", app, name)))
            self.app.data.invalidate("presets")
            self._reload()

        self.app.push_screen(
            ConfirmModal(plain(msg("preset_prompt_delete_confirm", name)), danger=True),
            callback=_confirmed,
        )

    def action_inspect(self) -> None:
        app = self._focused_app()
        item = self._focused_item()
        if not app:
            return
        name = item.get("name") if item and item["type"] == "preset" else self.app.data.active_preset(app)
        info = self.app.data.preset_info(app, name)
        if not info:
            return
        lines = [
            f"{msg('preset_info_source')}: {info.path}",
            f"{msg('preset_info_files')} ({len(info.files)}):",
            *([f"  · {f}" for f in info.files] or [f"  · {msg('preset_info_none')}"]),
            f"{msg('preset_info_preserve')} ({len(info.preserve)}):",
            *([f"  · {p}" for p in info.preserve] or [f"  · {msg('preset_info_none')}"]),
        ]
        if item and item["type"] in ("slot", "variant"):
            slot_info = self.app.data.parts_for(app).get(item["slot"], {})
            lines += [
                f"{msg('preset_part_target')}: ~/.config/{app}/{slot_info.get('target', '')}",
                f"{msg('preset_part_desc')}: {slot_info.get('desc', '')}",
                f"{msg('preset_part_variants')}: {' · '.join(slot_info.get('variants', [])) or msg('preset_info_none')}",
            ]
        self.app.push_screen(ReportModal(f"{app} · {name}", lines))
