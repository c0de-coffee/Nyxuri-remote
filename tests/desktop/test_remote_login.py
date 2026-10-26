"""Behavior contracts for the remote-login unit hooks (KM3).

The hooks run against a fake machine: every `sudo`/`systemctl`/`grdctl`/`openssl` call goes to
`FakeMachine.run`, which keeps root files under the temp HOME, service enablement and grd's
settings, and records each argv for shape assertions.
"""

import importlib.util
import os
import sys
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.utils import TempEnv

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / "units" / "remote-login" / "hooks"


def _load_hook(name: str):
    """Import a hook without writing bytecode into the read-only blueprint."""
    path = HOOKS / name
    mod_name = f"remote_login_hook_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, path, loader=SourceFileLoader(mod_name, str(path)))
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


class FakeMachine:
    def __init__(self, root: Path):
        self.root = root
        self.enabled = set()
        self.active = set()
        self.credentials = None
        self.tls = None
        self.calls = []
        self.inputs = []
        self.fail = set()  # argv tuples (or prefixes) that fail
        self.noctalia_running = True

    def _result(self, ok=True, stdout=""):
        return SimpleNamespace(returncode=0 if ok else 1, stdout=stdout, stderr="")

    def _fails(self, argv):
        return any(tuple(argv[: len(prefix)]) == prefix for prefix in self.fail)

    def status(self):
        cert, key = self.tls or ("(null)", "(null)")
        return (
            "RDP:\n"
            "\tStatus: enabled\n"
            "\tPort: 3389\n"
            f"\tTLS certificate: {cert}\n"
            f"\tTLS key: {key}\n"
            f"\tUsername: {'(hidden)' if self.credentials else '(empty)'}\n"
            f"\tPassword: {'(hidden)' if self.credentials else '(empty)'}\n"
        )

    def run(self, argv, input=None, **kwargs):
        self.calls.append(list(argv))
        if input is not None:
            self.inputs.append((list(argv), input))
        if self._fails(argv):
            return self._result(False)
        cmd = argv[1:] if argv[0] == "sudo" else argv
        if cmd[:1] == ["test"]:
            return self._result(Path(cmd[-1]).exists())
        if cmd[:1] == ["cat"]:
            return self._result(True, Path(cmd[-1]).read_text(encoding="utf-8"))
        if cmd[:2] == ["install", "-D"]:
            dest = Path(cmd[-1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(Path(cmd[-2]).read_bytes())
            return self._result()
        if cmd[:2] == ["rm", "-f"]:
            Path(cmd[-1]).unlink(missing_ok=True)
            return self._result()
        if cmd[:1] == ["systemctl"]:
            service = cmd[-1]
            if cmd[1] == "is-enabled":
                return self._result(service in self.enabled)
            if cmd[1] == "is-active":
                return self._result(service in self.active)
            if cmd[1] == "enable":
                self.enabled.add(service)
            if cmd[1] == "disable":
                self.enabled.discard(service)
            return self._result()
        if cmd[:2] == ["grdctl", "--system"]:
            sub = cmd[2:]
            if sub == ["status"]:
                return self._result(True, self.status())
            if sub[:2] == ["rdp", "set-credentials"]:
                # Like grdctl: answers after the first line of a pipe are lost.
                answers = sub[2:] + input.splitlines()[:1]
                self.credentials = tuple(answers) if len(answers) == 2 else None
            elif sub[:2] == ["rdp", "clear-credentials"]:
                self.credentials = None
            elif sub[:2] == ["rdp", "set-tls-cert"]:
                self.tls = (sub[2], (self.tls or (None, "(null)"))[1])
            elif sub[:2] == ["rdp", "set-tls-key"]:
                self.tls = ((self.tls or ("(null)", None))[0], sub[2])
            elif sub[:2] == ["rdp", "enable"]:
                self.enabled.add("gnome-remote-desktop.service")
                self._grd_conf().write_text("[RDP]\nenabled=true\n", encoding="utf-8")
            elif sub[:2] == ["rdp", "disable"]:
                self.enabled.discard("gnome-remote-desktop.service")
            return self._result()
        if argv[:3] == ["noctalia", "msg", "plugins"]:
            return self._result(self.noctalia_running)
        if cmd[:1] == ["openssl"]:
            Path(cmd[cmd.index("-keyout") + 1]).write_text("key", encoding="utf-8")
            Path(cmd[cmd.index("-out") + 1]).write_text("cert", encoding="utf-8")
            return self._result()
        raise AssertionError(f"unexpected command: {argv}")

    def _grd_conf(self):
        path = self.root / "etc" / "gnome-remote-desktop" / "grd.conf"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class RemoteLoginHookTest(unittest.TestCase):
    def setUp(self):
        self._ctx = TempEnv()
        self._ctx.__enter__()
        self.root = self._ctx.env.home / "root"
        self.machine = FakeMachine(self.root)
        self.activate = _load_hook("activate")
        self.deactivate = _load_hook("deactivate")
        self.common = self.activate.common
        self.assertIs(self.deactivate.common, self.common)

        paths = {
            "RDM_CONFIG": self.root / "etc" / "remote-dm" / "config.toml",
            "STATE": self.root / "etc" / "remote-dm" / "nyxuri-state.json",
            "GRD_CONF": self.root / "etc" / "gnome-remote-desktop" / "grd.conf",
            "TLS_CERT": self.root / "var" / "grd" / "nyxuri-rdp-tls.crt",
            "TLS_KEY": self.root / "var" / "grd" / "nyxuri-rdp-tls.key",
        }
        for name, path in paths.items():
            setattr(self, name.lower(), path)
        self.rdm_config.parent.mkdir(parents=True)
        self.rdm_config.write_text("# packaged defaults\n", encoding="utf-8")

        self._patches = [patch.object(self.common, name, path) for name, path in paths.items()]
        self._patches += [
            patch.object(self.common.subprocess, "run", side_effect=self.machine.run),
            patch.object(self.common, "trusted_executable", return_value="/usr/bin/x"),
            patch.object(self.common, "niri_has_remote_desktop", return_value=True),
            patch.object(self.activate.sys.stdin, "isatty", return_value=False),
            patch.dict(os.environ, {"XDG_DATA_HOME": str(self._ctx.env.home / "data")}),
            # No Noctalia unless a test says so.
            patch.object(self.common.shutil, "which", return_value=None),
            patch("builtins.print"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._ctx.__exit__()
        sys.modules.pop("remote_login_common", None)

    def _state(self):
        import json
        return json.loads(self.state.read_text(encoding="utf-8"))


class TestActivate(RemoteLoginHookTest):
    def test_first_activation_records_state_then_sets_everything_up(self):
        self.assertEqual(self.activate.main(), 0)

        state = self._state()
        self.assertEqual(state["rdm_config"], "# packaged defaults\n")
        self.assertIsNone(state["grd_conf"])
        self.assertFalse(state["grd_enabled"])
        self.assertFalse(state["rdm_enabled"])
        self.assertTrue(state["tls"])
        self.assertTrue(state["credentials"])

        self.assertIn("greeter-noctalia.kdl", self.rdm_config.read_text(encoding="utf-8"))
        self.assertTrue(self.tls_cert.is_file() and self.tls_key.is_file())
        self.assertEqual(self.machine.tls, (str(self.tls_cert), str(self.tls_key)))
        self.assertIsNotNone(self.machine.credentials)
        self.assertEqual(self.machine.enabled, {"gnome-remote-desktop.service", "remote-dm.service"})
        self.assertIn(["sudo", "systemctl", "enable", "--now", "remote-dm.service"], self.machine.calls)

    def test_password_goes_through_stdin_not_argv(self):
        self.assertEqual(self.activate.main(), 0)

        (argv, given), = [(a, i) for a, i in self.machine.inputs if "set-credentials" in a]
        username, password = self.machine.credentials
        self.assertEqual(argv, ["sudo", "grdctl", "--system", "rdp", "set-credentials", username])
        self.assertEqual(given, f"{password}\n")
        self.assertTrue(all(password not in arg for call in self.machine.calls for arg in call))

    def test_typed_credentials_are_used(self):
        with patch.object(self.activate.sys.stdin, "isatty", return_value=True), \
             patch("builtins.input", return_value="door"), \
             patch.object(self.activate.getpass, "getpass", return_value="s3cret"):
            self.assertEqual(self.activate.main(), 0)
        self.assertEqual(self.machine.credentials, ("door", "s3cret"))

    def test_replay_keeps_existing_tls_credentials_and_recorded_state(self):
        self.assertEqual(self.activate.main(), 0)
        recorded = self.state.read_text(encoding="utf-8")
        credentials = self.machine.credentials
        self.machine.calls.clear()

        self.assertEqual(self.activate.main(), 0)

        self.assertEqual(self.state.read_text(encoding="utf-8"), recorded)
        self.assertEqual(self.machine.credentials, credentials)
        self.assertFalse(any(call[:1] == ["openssl"] for call in self.machine.calls))
        self.assertFalse(any("set-credentials" in call for call in self.machine.calls))

    def test_existing_grd_setup_is_left_alone(self):
        own = self._ctx.env.home / "own.crt", self._ctx.env.home / "own.key"
        for path in own:
            path.write_text("mine", encoding="utf-8")
        self.machine.tls = tuple(map(str, own))
        self.machine.credentials = ("mine", "pw")

        self.assertEqual(self.activate.main(), 0)

        state = self._state()
        self.assertFalse(state["tls"])
        self.assertFalse(state["credentials"])
        self.assertEqual(self.machine.credentials, ("mine", "pw"))
        self.assertEqual(self.machine.tls, tuple(map(str, own)))
        self.assertFalse(any(call[:1] == ["openssl"] for call in self.machine.calls))

        self.assertEqual(self.deactivate.main(), 0)
        self.assertEqual(self.machine.credentials, ("mine", "pw"))
        self.assertTrue(all(path.is_file() for path in own))

    def test_credentials_that_did_not_stick_fail_the_activation(self):
        real_run = self.machine.run

        def lossy(argv, input=None, **kwargs):
            if "set-credentials" in argv:
                self.machine.calls.append(list(argv))
                return SimpleNamespace(returncode=0, stdout="", stderr="")  # exits 0, stores nothing
            return real_run(argv, input=input, **kwargs)

        with patch.object(self.common.subprocess, "run", side_effect=lossy):
            self.assertEqual(self.activate.main(), 1)
        self.assertFalse(self.state.exists())

    def test_gdm_blocks_activation_without_changes(self):
        self.machine.enabled.add("gdm")
        self.assertEqual(self.activate.main(), 1)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.rdm_config.read_text(encoding="utf-8"), "# packaged defaults\n")
        self.assertFalse(any(call[:1] == ["sudo"] for call in self.machine.calls))

    def test_running_gdm_blocks_activation_until_reboot(self):
        self.machine.active.add("gdm")
        self.assertEqual(self.activate.main(), 1)
        self.assertFalse(self.state.exists())
        self.assertFalse(any(call[:1] == ["sudo"] for call in self.machine.calls))

    def test_missing_packages_block_activation(self):
        with patch.object(self.common, "niri_has_remote_desktop", return_value=False):
            self.assertEqual(self.activate.main(), 1)
        self.assertFalse(self.state.exists())

    def test_failed_first_activation_rolls_everything_back(self):
        self.machine.fail.add(("sudo", "systemctl", "enable", "--now", "remote-dm.service"))

        self.assertEqual(self.activate.main(), 1)

        self.assertFalse(self.state.exists())
        self.assertEqual(self.rdm_config.read_text(encoding="utf-8"), "# packaged defaults\n")
        self.assertFalse(self.grd_conf.exists())
        self.assertFalse(self.tls_cert.exists() or self.tls_key.exists())
        self.assertIsNone(self.machine.credentials)
        self.assertNotIn("gnome-remote-desktop.service", self.machine.enabled)


class TestDeactivate(RemoteLoginHookTest):
    def test_off_restores_the_machine(self):
        self.assertEqual(self.activate.main(), 0)
        self.assertEqual(self.deactivate.main(), 0)

        self.assertFalse(self.state.exists())
        self.assertEqual(self.rdm_config.read_text(encoding="utf-8"), "# packaged defaults\n")
        self.assertFalse(self.grd_conf.exists())
        self.assertFalse(self.tls_cert.exists() or self.tls_key.exists())
        self.assertIsNone(self.machine.credentials)
        self.assertEqual(self.machine.enabled, set())

    def test_off_keeps_a_grd_that_was_already_running(self):
        self.grd_conf.parent.mkdir(parents=True)
        self.grd_conf.write_text("[RDP]\nport=3390\n", encoding="utf-8")
        self.machine.enabled.add("gnome-remote-desktop.service")
        self.assertEqual(self.activate.main(), 0)

        self.assertEqual(self.deactivate.main(), 0)

        self.assertEqual(self.grd_conf.read_text(encoding="utf-8"), "[RDP]\nport=3390\n")
        self.assertIn("gnome-remote-desktop.service", self.machine.enabled)
        self.assertNotIn("remote-dm.service", self.machine.enabled)
        self.assertNotIn(["sudo", "grdctl", "--system", "rdp", "disable"], self.machine.calls)

    def test_off_without_record_changes_nothing(self):
        self.assertEqual(self.deactivate.main(), 0)
        self.assertFalse(any(call[:1] == ["sudo"] and call[1] != "test" for call in self.machine.calls))

    def test_failed_undo_keeps_the_record_for_another_try(self):
        self.assertEqual(self.activate.main(), 0)
        self.machine.fail.add(("sudo", "grdctl", "--system", "rdp", "clear-credentials"))

        self.assertEqual(self.deactivate.main(), 1)

        self.assertTrue(self.state.exists())


class TestNoctaliaPlugin(RemoteLoginHookTest):
    PLUGIN = ["noctalia", "msg", "plugins"]

    def setUp(self):
        super().setUp()
        self.dest = self._ctx.env.home / "data" / "noctalia" / "plugins" / "remote_login"
        self.source = HOOKS / "noctalia-plugin" / "remote_login"

    def _with_noctalia(self):
        return patch.object(self.common.shutil, "which",
                            side_effect=lambda name: "/usr/bin/noctalia" if name == "noctalia" else None)

    def test_on_copies_and_enables_the_plugin(self):
        with self._with_noctalia():
            self.assertEqual(self.activate.main(), 0)

        for name in ("plugin.toml", "panel.luau", "shortcut.luau", "grd.luau", "translations/en.json"):
            self.assertEqual((self.dest / name).read_bytes(), (self.source / name).read_bytes(), name)
        self.assertIn(self.PLUGIN + ["enable", "nyxuri/remote_login"], self.machine.calls)

    def test_update_rewrites_in_place_and_drops_stale_files(self):
        with self._with_noctalia():
            self.assertEqual(self.activate.main(), 0)
            panel = self.dest / "panel.luau"
            inode = panel.stat().st_ino
            panel.write_text("old", encoding="utf-8")
            (self.dest / "gone.luau").write_text("x", encoding="utf-8")

            self.assertEqual(self.activate.main(), 0)

        self.assertEqual(panel.read_bytes(), (self.source / "panel.luau").read_bytes())
        self.assertEqual(panel.stat().st_ino, inode)  # Noctalia's file watch keeps working
        self.assertFalse((self.dest / "gone.luau").exists())

    def test_noctalia_not_running_still_installs(self):
        self.machine.noctalia_running = False
        with self._with_noctalia():
            self.assertEqual(self.activate.main(), 0)
        self.assertTrue((self.dest / "plugin.toml").is_file())

    def test_without_noctalia_nothing_is_installed(self):
        self.assertEqual(self.activate.main(), 0)
        self.assertFalse(self.dest.exists())
        self.assertFalse(any(call[:1] == ["noctalia"] for call in self.machine.calls))

    def test_off_disables_and_removes_the_plugin(self):
        with self._with_noctalia():
            self.assertEqual(self.activate.main(), 0)
            self.assertEqual(self.deactivate.main(), 0)
        self.assertFalse(self.dest.exists())
        self.assertIn(self.PLUGIN + ["disable", "nyxuri/remote_login"], self.machine.calls)


class TestPackaging(unittest.TestCase):
    def test_hooks_are_executable_and_the_module_is_not(self):
        for name in ("activate", "deactivate"):
            self.assertTrue((HOOKS / name).stat().st_mode & 0o111, name)
        self.assertFalse((HOOKS / "remote_login_common.py").stat().st_mode & 0o111)


if __name__ == "__main__":
    unittest.main()
