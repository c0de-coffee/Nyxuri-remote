"""Contract tests for Mango WM adaptation in Nyxuri."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nyxuri.core import get_env
from nyxuri.deploy.manifest import discover_deployable_apps, discover_optional_apps, load_manifest
from nyxuri.deploy.templates import _phase_render_templates
from tests.utils import TempEnv

_REPO = Path(__file__).resolve().parents[2]


class TestMangoAdaptation(unittest.TestCase):
    def setUp(self):
        self.ctx = TempEnv()
        self.ctx.__enter__()
        self.mango_src = _REPO / "units" / "mango"

    def tearDown(self):
        self.ctx.__exit__()

    def test_mango_config_syntax_valid(self):
        """Validate config.conf syntax with mango -p if mango binary is available."""
        if not shutil.which("mango"):
            self.skipTest("mango binary not installed")
        conf_path = self.mango_src / "config.conf"
        self.assertTrue(conf_path.is_file())
        res = subprocess.run(["mango", "-c", str(conf_path), "-p"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"mango -p failed: {res.stderr}")
    def test_mango_manifest_contract(self):
        """Verify manifest.toml parameters for mango."""
        m = load_manifest(self.mango_src)
        self.assertEqual(m.name, "mango")
        self.assertEqual(m.packages_repo, ["mangowm"])
        self.assertEqual(m.packages_aur, [])
        self.assertEqual(m.detect, "mango")
        self.assertEqual(m.label, "Mango WM")
        self.assertIn("monitors.conf", m.preserve)
        self.assertIn("noctalia.conf", m.preserve)
        self.assertIn("scripts/*.sh", m.chmod)
        self.assertEqual(m.preset_reload, ["mmsg", "dispatch", "reload_config"])
        self.assertTrue(m.is_deployable)
        self.assertTrue(m.is_optional)

    def test_mango_dual_axis_discovery(self):
        """Mango must be both deployable (axis A) and optional (axis B)."""
        deployable = discover_deployable_apps()
        self.assertIn("mango", deployable)

        optional = discover_optional_apps()
        self.assertIn("mango", optional)

    def test_mango_portals_conf_exists_and_routes_wlr(self):
        """Verify mango-portals.conf configures wlr screencast/screenshot."""
        portal_conf = _REPO / "units" / "xdg-desktop-portal" / "mango-portals.conf"
        self.assertTrue(portal_conf.is_file())
        content = portal_conf.read_text(encoding="utf-8")
        self.assertIn("org.freedesktop.impl.portal.ScreenCast=wlr;", content)
        self.assertIn("org.freedesktop.impl.portal.Screenshot=wlr;", content)

    def test_mango_template_rendering(self):
        """Verify /home/user is replaced with target $HOME in config.conf."""
        env = get_env()
        dest_mango = env.config_dir / "mango"
        dest_mango.mkdir(parents=True, exist_ok=True)
        (dest_mango / "config.conf").write_text(
            "exec=/home/user/.config/mango/scripts/session-shell.sh\n",
            encoding="utf-8",
        )
        _phase_render_templates(only_app="mango")
        rendered = (dest_mango / "config.conf").read_text(encoding="utf-8")
        self.assertNotIn("/home/user", rendered)
        self.assertIn(str(env.home), rendered)

    def test_theme_sync_calls_mmsg_reload(self):
        """Theme sync should dispatch mmsg reload_config when mmsg is available."""
        from nyxuri.desktop.theme import sync

        calls = []

        def fake_timed_run(cmd, *args, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        def fake_which(cmd):
            if cmd == "mmsg":
                return "/usr/bin/mmsg"
            return None

        with patch("nyxuri.desktop.theme.timed_run", side_effect=fake_timed_run), \
             patch("nyxuri.desktop.theme.shutil.which", side_effect=fake_which):
            sync("dark")

        self.assertIn(["mmsg", "dispatch", "reload_config"], calls)

    def test_doctor_detects_running_mango(self):
        """Doctor should report mango as OK when XDG_CURRENT_DESKTOP is mango."""
        from io import StringIO
        import contextlib
        import os
        from nyxuri.sysdoctor import _check_compositor

        buf = StringIO()
        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "mango"}), \
             contextlib.redirect_stdout(buf):
            _check_compositor(self.ctx.env)

        out = buf.getvalue()
        self.assertIn("mango", out)
        self.assertIn("正在运行", out)

    def test_detect_preferred_wm(self):
        """detect_preferred_wm returns running desktop or fallback."""
        import os
        from nyxuri.core import detect_preferred_wm

        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "mango"}):
            self.assertEqual(detect_preferred_wm(), "mango")

        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "niri"}):
            self.assertEqual(detect_preferred_wm(), "niri")

    def test_component_options_selects_exactly_one_wm(self):
        """WM radio contract (T2): every WM offered, preferred one selected."""
        import os
        from nyxuri.market.data import MarketData
        from tests.utils import TempEnv

        with TempEnv() as ctx:
            src = ctx.home / "configs-src"
            for unit in ("niri", "mango", "kitty"):
                (src / unit).mkdir(parents=True)
                (src / unit / "manifest.toml").write_text("", encoding="utf-8")
                (src / unit / "config.conf").write_text("", encoding="utf-8")
            ctx.env.units_src = src
            import nyxuri.deploy.deploy as _deploy
            import nyxuri.deploy.manifest as _manifest
            _deploy._CONFIG_ITEMS_CACHE = []
            _manifest._MANIFEST_CACHE = None

            with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "mango"}), \
                 patch("nyxuri.pkg.deps.is_dep_installed", return_value=False):
                options = MarketData().component_options("full")

            names = [wm["name"] for wm in options["wms"]]
            self.assertEqual(names, ["mango", "niri"])
            selected = [wm["name"] for wm in options["wms"] if wm["selected"]]
            self.assertEqual(selected, ["mango"], "running WM wins the radio")


if __name__ == "__main__":
    unittest.main()

