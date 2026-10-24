"""Market actions — every mutation rides the kernel's transaction path."""

import unittest
from unittest import mock

from nyxuri.market import actions
from tests.market import stage
from tests.utils import TempEnv


class TestSwitchOn(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("nyxuri.kernel.transaction.missing_packages", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_switch_on_returns_steps_and_lands_ledger(self):
        with TempEnv() as ctx:
            stage(ctx, {"app": {"files": {"a.conf": "a"}}})
            steps = actions.switch_on("app")
            self.assertTrue(all(s.ok for s in steps), str(steps))
            self.assertTrue((ctx.home / ".config/app/a.conf").is_file())

    def test_switch_off_wipes_and_disables(self):
        with TempEnv() as ctx:
            stage(ctx, {"app": {"files": {"a.conf": "a"}}})
            actions.switch_on("app")
            steps = actions.switch_off("app")
            self.assertTrue(all(s.ok for s in steps), str(steps))
            from nyxuri.kernel import ledger

            self.assertEqual(ledger.get_unit("app")["state"], "disabled")
            self.assertFalse((ctx.home / ".config/app/a.conf").exists())


class TestPlanOnDisclosure(unittest.TestCase):
    def test_disclosure_lists_incoming_and_missing(self):
        with TempEnv() as ctx:
            stage(ctx, {
                "app": {"manifest": 'packages = ["pkg-x"]\n', "files": {"a.conf": "a"}},
            })
            with mock.patch("nyxuri.kernel.transaction.missing_packages",
                            return_value=["pkg-x"]) as missing:
                incoming, missing_pkgs = actions.plan_on_disclosure("app")
            self.assertEqual(incoming, ["app"])
            self.assertEqual(missing_pkgs, ["pkg-x"])
            missing.assert_called()

    def test_disclosure_excludes_already_enabled_units(self):
        with TempEnv() as ctx:
            stage(ctx, {
                "app": {"manifest": 'dependencies = ["base"]\n', "files": {"a.conf": "a"}},
                "base": {"files": {"b.conf": "b"}},
            })
            with mock.patch("nyxuri.kernel.transaction.missing_packages", return_value=[]):
                actions.switch_on("base")
                incoming, missing_pkgs = actions.plan_on_disclosure("app")
            self.assertEqual(incoming, ["app"])
            self.assertEqual(missing_pkgs, [])


class TestInstallerInjection(unittest.TestCase):
    def test_switch_on_without_install_reports_missing_and_touches_nothing(self):
        with TempEnv() as ctx:
            stage(ctx, {"app": {"manifest": 'packages = ["pkg-x"]\n', "files": {"a.conf": "a"}}})
            with mock.patch("nyxuri.kernel.transaction.missing_packages",
                            return_value=["pkg-x"]):
                steps = actions.switch_on("app", install=False)
            self.assertFalse(steps[0].ok)
            self.assertIn("missing-packages", steps[0].detail)
            self.assertFalse((ctx.home / ".config/app").exists())

    def test_installer_receives_manifest_context(self):
        with TempEnv() as ctx:
            stage(ctx, {"app": {"manifest": 'packages = ["pkg-x"]\n', "files": {"a.conf": "a"}}})
            calls = []
            # unit_on re-checks missing_packages after the installer ran
            # (line: `not installed or missing_packages(manifest)`), so the
            # patch must report the gap once, then report it resolved.
            probes = {"n": 0}

            def fake_missing(manifest):
                probes["n"] += 1
                return ["pkg-x"] if probes["n"] == 1 else []

            def fake_installer(uid, missing):
                calls.append((uid, list(missing)))
                return True

            with mock.patch("nyxuri.kernel.transaction.missing_packages", fake_missing):
                with mock.patch.object(actions, "_installer", fake_installer):
                    steps = actions.switch_on("app")
            self.assertTrue(all(s.ok for s in steps), str(steps))
            self.assertEqual(calls, [("app", ["pkg-x"])])


if __name__ == "__main__":
    unittest.main()
