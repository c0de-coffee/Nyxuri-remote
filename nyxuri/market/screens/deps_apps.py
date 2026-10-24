"""Deps apps — the catalog + optional-unit supply as a category tree.

Categories are branch nodes; apps are leaves with an installed verdict and
a Flatpak tag. Space toggles the focused leaf (or a whole category), Enter
installs the picked set through the same installer as ``nyxuri deps apps``.
"""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static, Tree

from nyxuri.core import msg
from nyxuri.market import actions
from nyxuri.market.modals import ConfirmModal, plain


class DepsAppsScreen(Screen):
    BINDINGS = [
        Binding("space", "toggle", "Toggle"),
        Binding("enter,i", "install", "Install"),
        Binding("q,escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Tree("", id="apps-tree")
        yield Static(msg("deps_apps_hint"), id="hint-bar")

    def on_mount(self) -> None:
        tree = self.query_one("#apps-tree", Tree)
        tree.border_title = plain(msg("opt_apps_menu_title").strip())
        tree.show_root = False
        tree.guide_depth = 3
        self._reload()

    def on_show(self) -> None:
        self._reload()

    def _reload(self) -> None:
        tree = self.query_one("#apps-tree", Tree)
        tree.clear()
        self._picked: set[str] = set()
        items = self.app.data.supply_apps()
        grouped: dict[str, list[dict]] = {}
        for item in items:
            grouped.setdefault(item["category"] or "other", []).append(item)
        for category in sorted(grouped):
            label = plain(msg(f"apps_cat_{category}"))
            branch = tree.root.add(label, expand=True)
            for item in grouped[category]:
                status = plain(msg("installed" if item["installed"] else "missing"))
                style = "dim" if item["installed"] else ""
                name = msg(f"app_{item['key'].replace('-', '_')}")
                node_label = Text.assemble(
                    (f"☐ {name}", style),
                    (f"  {status}", "bright_black"),
                )
                node = branch.add(node_label)
                node.data = {"key": item["key"], "installed": item["installed"]}
        tree.root.expand()

    def _refresh_label(self, node) -> None:
        item = node.data
        status = plain(msg("installed" if item["installed"] else "missing"))
        style = "dim" if item["installed"] else ""
        name_key = f"app_{item['key'].replace('-', '_')}"
        mark = "☑" if item["key"] in self._picked else "☐"
        node.set_label(Text.assemble(
            (f"{mark} {msg(name_key)}", style),
            (f"  {status}", "bright_black"),
        ))

    def on_tree_node_highlighted(self, event) -> None:
        return

    def action_toggle(self) -> None:
        tree = self.query_one("#apps-tree", Tree)
        node = tree.cursor_node
        if node is None:
            return
        if node.data is None:
            # Category branch: toggle every child leaf.
            for child in node.children:
                if child.data and not child.data["installed"]:
                    key = child.data["key"]
                    if key in self._picked:
                        self._picked.discard(key)
                    else:
                        self._picked.add(key)
                    self._refresh_label(child)
            return
        if node.data["installed"]:
            return
        key = node.data["key"]
        if key in self._picked:
            self._picked.discard(key)
        else:
            self._picked.add(key)
        self._refresh_label(node)

    def action_install(self) -> None:
        if not self._picked:
            self.notify(plain(msg("opt_apps_none_selected")))
            return
        chosen = sorted(self._picked)
        names = ", ".join(plain(msg(f"app_{k.replace('-', '_')}")) for k in chosen)

        def _confirmed(answer: bool) -> None:
            if not answer:
                return
            ok = self.app.handoff(actions.install_apps, chosen)
            self._reload()
            self.notify(
                plain(msg("opt_apps_install_done" if ok else "log_official_pkgs_partial_fail")),
                severity="information" if ok else "error",
            )

        self.app.push_screen(ConfirmModal(names), callback=_confirmed)

    def action_back(self) -> None:
        self.app.pop_screen()
