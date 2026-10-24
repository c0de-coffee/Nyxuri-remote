"""Screen smoke tests via Textual's headless Pilot.

Guarded by ``skipUnless``: machines without python-textual still run the
whole suite green (the data/actions/architecture tests cover the logic).
"""

import unittest
from unittest import mock

try:
    import textual  # noqa: F401

    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from tests.market import stage
from tests.utils import TempEnv


@unittest.skipUnless(HAS_TEXTUAL, "python-textual not installed")
class TestAppNavigation(unittest.TestCase):
    def _app(self):
        from nyxuri.market.app import MarketApp

        return MarketApp()

    def test_home_to_workshop_and_back(self):
        import asyncio

        async def scenario():
            with TempEnv():
                app = self._app()
                async with app.run_test(size=(100, 30)) as pilot:
                    await pilot.pause()
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertEqual(type(app.screen).__name__, "WorkshopScreen")
                    await pilot.press("q")
                    await pilot.pause()
                    self.assertEqual(type(app.screen).__name__, "HomeScreen")

        asyncio.run(scenario())

    def test_language_modal_rebuilds_home(self):
        import asyncio

        async def scenario():
            with TempEnv():
                from nyxuri.core import get_lang, set_lang

                before = get_lang()
                app = self._app()
                try:
                    async with app.run_test(size=(100, 30)) as pilot:
                        await pilot.pause()
                        await pilot.press("L")
                        await pilot.pause()
                        self.assertEqual(type(app.screen).__name__, "LanguageModal")
                        await pilot.click("#zh")
                        await pilot.pause()
                        # rebuild landed on a fresh HomeScreen, language applied
                        self.assertEqual(type(app.screen).__name__, "HomeScreen")
                        self.assertEqual(get_lang(), "zh")
                        # cancel keeps the locale-derived language
                        await pilot.press("L")
                        await pilot.pause()
                        await pilot.press("q")
                        await pilot.pause()
                        self.assertEqual(type(app.screen).__name__, "HomeScreen")
                finally:
                    set_lang(before)

        asyncio.run(scenario())


@unittest.skipUnless(HAS_TEXTUAL, "python-textual not installed")
class TestWorkshopSwitch(unittest.TestCase):
    def test_on_off_roundtrip_through_the_screen(self):
        import asyncio
        from nyxuri.market import actions
        from nyxuri.market.modals import ConfirmModal, ReportModal

        async def scenario():
            with TempEnv() as ctx:
                stage(ctx, {"app": {"files": {"a.conf": "a"}}})
                with mock.patch("nyxuri.kernel.transaction.missing_packages",
                                return_value=[]):
                    app = self._app()
                    async with app.run_test(size=(100, 30)) as pilot:
                        await pilot.pause()
                        await pilot.press("enter")
                        await pilot.pause()
                        # light switch (no missing packages) runs in-process
                        await pilot.press("o")
                        await pilot.pause()
                        self.assertIsInstance(app.screen, ReportModal)
                        await pilot.press("enter")
                        await pilot.pause()
                        rows = {r["uid"]: r["state"] for r in app.data.unit_rows()}
                        self.assertEqual(rows.get("app"), "enabled")
                        self.assertTrue((ctx.home / ".config/app/a.conf").is_file())
                        # off asks first; escape keeps it enabled
                        await pilot.press("f")
                        await pilot.pause()
                        self.assertIsInstance(app.screen, ConfirmModal)
                        await pilot.press("escape")
                        await pilot.pause()
                        rows = {r["uid"]: r["state"] for r in app.data.unit_rows()}
                        self.assertEqual(rows.get("app"), "enabled")
                        # confirm → disabled, file gone
                        await pilot.press("f")
                        await pilot.pause()
                        await pilot.press("y")
                        await pilot.pause()
                        self.assertIsInstance(app.screen, ReportModal)
                        await pilot.press("enter")
                        await pilot.pause()
                        rows = {r["uid"]: r["state"] for r in app.data.unit_rows()}
                        self.assertEqual(rows.get("app"), "disabled")
                        self.assertFalse((ctx.home / ".config/app/a.conf").exists())

        asyncio.run(scenario())

    def test_on_with_missing_packages_hands_off_after_confirm(self):
        import asyncio
        from nyxuri.market.modals import ConfirmModal, ReportModal

        async def scenario():
            with TempEnv() as ctx:
                stage(ctx, {"app": {"manifest": 'packages = ["pkg-x"]\n',
                                    "files": {"a.conf": "a"}}})
                handoffs = []
                app = self._app()
                # Identity handoff: record the call, run in-process (headless
                # pilot cannot suspend a real terminal).
                app.handoff = lambda fn, *a, **kw: handoffs.append(fn.__name__) or fn(*a, **kw)
                async with app.run_test(size=(100, 30)) as pilot:
                    await pilot.pause()
                    await pilot.press("enter")
                    await pilot.pause()
                    # Disclosure (call #1) reports the gap; the transaction's
                    # own preflight (call #2+) sees it resolved by "pacman".
                    probes = {"n": 0}

                    def fake_missing(manifest):
                        probes["n"] += 1
                        return ["pkg-x"] if probes["n"] == 1 else []

                    with mock.patch("nyxuri.kernel.transaction.missing_packages",
                                    fake_missing):
                        await pilot.press("o")
                        await pilot.pause()
                        self.assertIsInstance(app.screen, ConfirmModal)
                        await pilot.press("y")
                        await pilot.pause()
                    self.assertEqual(handoffs, ["switch_on"])
                    self.assertIsInstance(app.screen, ReportModal)
                    rows = {r["uid"]: r["state"] for r in app.data.unit_rows()}
                    self.assertEqual(rows.get("app"), "enabled")

        asyncio.run(scenario())

    def _app(self):
        from nyxuri.market.app import MarketApp

        return MarketApp()


@unittest.skipUnless(HAS_TEXTUAL, "python-textual not installed")
class TestPresetAndDoctorScreens(unittest.TestCase):
    def _app(self):
        from nyxuri.market.app import MarketApp

        return MarketApp()

    def _stage_kitty(self, ctx):
        from tests.market import stage

        stage(ctx, {
            "kitty": {
                "files": {"kitty.conf": "base\n"},
                # a real preset dir: stage() writes files, so nest it in
                # files under __presets__
            },
        })
        preset_dir = ctx.env.units_src / "kitty" / "__presets__" / "transparent"
        preset_dir.mkdir(parents=True)
        (preset_dir / "kitty.conf").write_text("transparent\n", encoding="utf-8")

    def test_preset_apply_through_screen(self):
        import asyncio

        async def scenario():
            with TempEnv() as ctx:
                self._stage_kitty(ctx)
                app = self._app()
                async with app.run_test(size=(110, 32)) as pilot:
                    await pilot.pause()
                    await pilot.press("enter")  # workshop? no: home order is workshop, presets, doctor
                    await pilot.press("q")
                    await pilot.pause()
                    # home entries: [workshop, presets, doctor]
                    await pilot.press("down")
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertEqual(type(app.screen).__name__, "PresetsScreen")
                    # default + transparent
                    self.assertEqual(app.screen.query_one("#preset-items").option_count, 2)
                    await pilot.press("tab")  # right pane
                    await pilot.pause()
                    await pilot.press("down")  # transparent
                    await pilot.press("enter")  # apply
                    await pilot.pause(0.05)
                    self.assertEqual(app.data.active_preset("kitty"), "transparent")
                    await pilot.press("q")  # right pane → left pane
                    await pilot.pause()
                    await pilot.press("q")  # left pane → home
                    await pilot.pause()
                    self.assertEqual(type(app.screen).__name__, "HomeScreen")

        asyncio.run(scenario())

    def test_doctor_screen_shows_verdicts(self):
        import asyncio

        async def scenario():
            with TempEnv() as ctx:
                stage(ctx, {"app": {"files": {"a.conf": "a"}}})
                with mock.patch("nyxuri.kernel.transaction.missing_packages",
                                return_value=[]):
                    from nyxuri.kernel import transaction

                    transaction.unit_on("app")
                    (ctx.home / ".config/app/a.conf").write_text("drift\n", encoding="utf-8")
                    app = self._app()
                    async with app.run_test(size=(110, 32)) as pilot:
                        await pilot.pause()
                        from textual.widgets import OptionList

                        home_list = app.screen.query_one("#home-list", OptionList)
                        home_list.highlighted = 9  # 系统诊断
                        await pilot.press("enter")
                        await pilot.pause()
                        self.assertEqual(type(app.screen).__name__, "DoctorScreen")
                        from textual.widgets import DataTable

                        table = app.screen.query_one("#doctor-table", DataTable)
                        self.assertEqual(table.row_count, 1)
                        await pilot.press("q")
                        await pilot.pause()
                        self.assertEqual(type(app.screen).__name__, "HomeScreen")

        asyncio.run(scenario())


@unittest.skipUnless(HAS_TEXTUAL, "python-textual not installed")
class TestM4Screens(unittest.TestCase):
    def _app(self):
        from nyxuri.market.app import MarketApp

        return MarketApp()

    def test_every_home_entry_mounts_and_returns(self):
        import asyncio

        async def scenario():
            with TempEnv() as ctx:
                stage(ctx, {"kitty": {"files": {"kitty.conf": "k"}}})
                with mock.patch("shutil.which", return_value=None):
                    app = self._app()
                    async with app.run_test(size=(110, 34)) as pilot:
                        await pilot.pause()
                        from textual.widgets import OptionList

                        home_list = app.screen.query_one("#home-list", OptionList)
                        seen = []
                        for i in range(home_list.option_count):
                            home_list.highlighted = i
                            await pilot.press("enter")
                            await pilot.pause(0.05)
                            seen.append(type(app.screen).__name__)
                            await pilot.press("q")
                            await pilot.pause()
                        self.assertEqual(len(set(seen)), len(seen), seen)
                        self.assertIn("UninstallScreen", seen)
                        self.assertIn("CleanScreen", seen)

        asyncio.run(scenario())

    def test_components_screen_collects_wm_radio_and_checks(self):
        import asyncio
        from nyxuri.market.screens.components import ComponentsScreen

        async def scenario():
            with TempEnv() as ctx:
                stage(ctx, {
                    "niri": {"files": {"config.kdl": "n"}},
                    "kitty": {"files": {"kitty.conf": "k"}},
                })
                with mock.patch("nyxuri.pkg.deps.is_dep_installed", return_value=False), \
                     mock.patch("nyxuri.deploy.deploy.wallpapers_pack_present", return_value=True):
                    app = self._app()
                    async with app.run_test(size=(110, 34)) as pilot:
                        await pilot.pause()
                        app.push_screen(ComponentsScreen(mode="full"))
                        await pilot.pause(0.05)
                        screen = app.screen
                        chosen = screen._collect()
                        # one WM (niri), apps checked, wallpapers off (pack
                        # present), backup on
                        self.assertIn("niri", chosen["configs"])
                        self.assertIn("kitty", chosen["configs"])
                        self.assertFalse(chosen["wallpapers"])
                        self.assertTrue(chosen["backup"])

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
