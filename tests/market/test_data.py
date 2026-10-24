"""MarketData projections — headless, no Textual imports anywhere near."""

import unittest
from unittest import mock

from nyxuri.market.data import MarketData
from tests.market import stage
from tests.utils import TempEnv


class TestUnitRows(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("nyxuri.kernel.transaction.missing_packages", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rows_reflect_ledger_and_registry_union(self):
        with TempEnv() as ctx:
            stage(ctx, {
                "kitty": {"files": {"kitty.conf": "k"}},
                "ghost-only": {"files": {"g.conf": "g"}},
            })
            from nyxuri.kernel import transaction

            transaction.unit_on("kitty")
            # A ledger record whose unit left the registry still shows up.
            from nyxuri.kernel import ledger

            ledger.set_unit("ghost-unit", state="enabled", preset="default")
            data = MarketData()
            rows = {r["uid"]: r for r in data.unit_rows()}
            self.assertEqual(rows["kitty"]["state"], "enabled")
            self.assertEqual(rows["kitty"]["preset"], "default")
            self.assertEqual(rows["ghost-unit"]["state"], "enabled")
            self.assertEqual(rows["ghost-only"]["state"], "-")

    def test_rows_reread_after_invalidate_is_not_required_but_stay_honest(self):
        """Ledger rows are re-read on every call (cheap state.json read)."""
        with TempEnv() as ctx:
            stage(ctx, {"kitty": {"files": {"kitty.conf": "k"}}})
            from nyxuri.kernel import transaction

            data = MarketData()
            self.assertEqual(data.unit_rows()[0]["state"], "-")
            transaction.unit_on("kitty")
            self.assertEqual(data.unit_rows()[0]["state"], "enabled")


class TestUnitDetail(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("nyxuri.kernel.transaction.missing_packages", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_detail_joins_manifest_and_ledger(self):
        with TempEnv() as ctx:
            stage(ctx, {
                "app": {
                    "manifest": 'label = "Appy"\ncategory = "tool"\npackages = ["pkg-a"]\ndependencies = ["base"]\n',
                    "files": {"a.conf": "a"},
                },
                "base": {"files": {"b.conf": "b"}},
            })
            from nyxuri.kernel import transaction

            transaction.unit_on("app")
            data = MarketData()
            detail = data.unit_detail("app")
            self.assertTrue(detail.known)
            self.assertEqual(detail.state, "enabled")
            self.assertEqual(detail.label, "Appy")
            self.assertEqual(detail.category, "tool")
            self.assertEqual(detail.packages, ["pkg-a"])
            self.assertEqual(detail.dependencies, ["base"])
            self.assertEqual(detail.audit, "Synced")

    def test_detail_of_unknown_unit_degrades_to_ledger_facts(self):
        with TempEnv() as ctx:
            from nyxuri.kernel import ledger

            ledger.set_unit("leftover", state="enabled", preset="default")
            detail = MarketData().unit_detail("leftover")
            self.assertFalse(detail.known)
            self.assertEqual(detail.state, "enabled")
            self.assertEqual(detail.packages, [])


class TestPresetProjections(unittest.TestCase):
    def _stage_kitty(self, ctx):
        src = ctx.home / "configs-src"
        (src / "kitty" / "__presets__" / "transparent").mkdir(parents=True)
        (src / "kitty" / "kitty.conf").write_text("base\n", encoding="utf-8")
        (src / "kitty" / "__presets__" / "transparent" / "kitty.conf").write_text(
            "transparent\n", encoding="utf-8")
        ctx.env.units_src = src

    def test_presets_for_lists_default_first_with_active_flag(self):
        with TempEnv() as ctx:
            self._stage_kitty(ctx)
            data = MarketData()
            rows = data.presets_for("kitty")
            self.assertEqual([r["name"] for r in rows], ["default", "transparent"])
            self.assertEqual(data.active_preset("kitty"), "default")
            self.assertEqual([r["active"] for r in rows], ["true", "false"])

    def test_preset_cache_invalidates(self):
        with TempEnv() as ctx:
            self._stage_kitty(ctx)
            with mock.patch("nyxuri.kernel.transaction.missing_packages",
                            return_value=[]):
                from nyxuri.kernel import transaction

                transaction.unit_on("kitty")  # save snapshots the living area
            data = MarketData()
            self.assertEqual(data.presets_for("kitty")[0]["name"], "default")
            from nyxuri.desktop.presets import save_preset

            self.assertTrue(save_preset("kitty", "mine"))
            self.assertEqual(len(data.presets_for("kitty")), 2, "cache must hold")
            data.invalidate("presets")
            self.assertEqual(len(data.presets_for("kitty")), 3)


class TestAuditCacheProtocol(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("nyxuri.kernel.transaction.missing_packages", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_audit_cached_until_invalidated(self):
        with TempEnv() as ctx:
            stage(ctx, {"app": {"files": {"a.conf": "a"}}})
            from nyxuri.kernel import transaction

            data = MarketData()
            transaction.unit_on("app")
            self.assertEqual(data.audit_for("app"), "Synced")
            # Drift the living area behind the cache's back.
            (ctx.home / ".config/app/a.conf").write_text("drifted", encoding="utf-8")
            self.assertEqual(data.audit_for("app"), "Synced", "cache must hold")
            data.invalidate()
            self.assertEqual(data.audit_for("app"), "Drifted", "invalidate drops the verdict")


if __name__ == "__main__":
    unittest.main()
