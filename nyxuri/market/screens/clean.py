"""Clean — the fenced cache sweeper as a checkbox screen.

Task discovery (one du walk) runs on mount; execution is the exact
engine half the CLI runs: user tasks first, then one sudo -v for the
elevated set, in a handed-off terminal.
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


def _human(size) -> str:
    if not size:
        return "—"
    x = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if x < 1024 or unit == "GiB":
            return f"{int(x)} B" if unit == "B" else f"{x:.1f} {unit}"
        x /= 1024
    return f"{x:.1f} TiB"


class CleanScreen(Screen):
    BINDINGS = [
        Binding("enter,ctrl+enter", "run", "Clean"),
        Binding("a", "all", "All"),
        Binding("n", "none", "None"),
        Binding("q,escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="clean-scroll")
        yield Static(plain(msg("clean_menu_hint").strip()), id="hint-bar")

    def on_mount(self) -> None:
        self.border_title = plain(msg("clean_menu_title").strip())
        scroll = self.query_one("#clean-scroll", VerticalScroll)
        scroll.remove_children()
        tasks, sizes, flat_roots = self.app.data.clean_tasks()
        self._tasks = tasks
        self._sizes = sizes
        self._flat_roots = flat_roots
        self._before = sum(v or 0 for v in sizes.values())
        from nyxuri.desktop.clean import DEFAULT_OFF

        for task in tasks:
            label = f"{task['label']}  {task['target']}  {_human(task['size'])}"
            if task["sudo"]:
                label += "  [sudo]"
            scroll.mount(Checkbox(label, value=task["key"] not in DEFAULT_OFF,
                                  id=f"clean-{task['key']}"))
        scroll.mount(Button(plain(msg("clean_menu_title").strip()), id="clean-run", variant="warning"))

    def _collect(self) -> list:
        return [t for t in self._tasks
                if self.query_one(f"#clean-{t['key']}", Checkbox).value]

    def on_button_pressed(self, event) -> None:
        if event.button.id == "clean-run":
            self.action_run()

    def action_all(self) -> None:
        for t in self._tasks:
            self.query_one(f"#clean-{t['key']}", Checkbox).value = True

    def action_none(self) -> None:
        for t in self._tasks:
            self.query_one(f"#clean-{t['key']}", Checkbox).value = False

    def action_run(self) -> None:
        chosen = self._collect()
        if not chosen:
            return

        def _confirmed(answer: bool) -> None:
            if not answer:
                return
            code = self.app.handoff(
                actions.clean_execute, chosen, self._before, self._sizes, self._flat_roots
            )
            self.app.data.invalidate()
            self.notify(plain(msg("clean_done" if code == 0 else "clean_failed")),
                        severity="information" if code == 0 else "warning")

        self.app.push_screen(ConfirmModal("\n".join(t["label"] for t in chosen), danger=True),
                             callback=_confirmed)

    def action_back(self) -> None:
        self.app.pop_screen()
