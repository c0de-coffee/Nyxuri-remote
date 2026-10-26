"""Shared by the remote-login hooks (a module, not a hook: no executable bit).

What `on` changes outside the living area, and how `off` undoes it. The first activation
records the state before any change in a root-only JSON file; `off` restores exactly that:

- /etc/remote-dm/config.toml       original content, restored (Noctalia Greeter while on)
- /etc/gnome-remote-desktop/grd.conf  original content or absence, restored
- TLS certificate                  only generated when grd had none; removed
- RDP credentials                  only set when grd had none; cleared
- gnome-remote-desktop.service, remote-dm.service  enabled while on; back to how they were

The Noctalia plugin (noctalia-plugin/remote_login: the settings panel) is the user's side: it's
copied to Noctalia's plugin data dir and enabled while on, and removed on off.

Every privileged step is `sudo` with an argv list, never a shell string.
"""
import json
import mmap
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

RDM_CONFIG = Path("/etc/remote-dm/config.toml")
RDM_GREETER = Path("/etc/remote-dm/greeter-noctalia.kdl")
STATE = Path("/etc/remote-dm/nyxuri-state.json")
GRD_CONF = Path("/etc/gnome-remote-desktop/grd.conf")
GRD_USER = "gnome-remote-desktop"
GRD_HOME = Path("/var/lib/gnome-remote-desktop")
TLS_CERT = GRD_HOME / "nyxuri-rdp-tls.crt"
TLS_KEY = GRD_HOME / "nyxuri-rdp-tls.key"
GRD_SERVICE = "gnome-remote-desktop.service"
RDM_SERVICE = "remote-dm.service"
# Owns org.gnome.DisplayManager too; remote-dm can't run next to it.
CONFLICT_DM = "gdm"

# Only a niri with remote desktop support serves this interface.
NIRI_REMOTE_DESKTOP_MARKER = b"org.gnome.Mutter.RemoteDesktop"

RDM_CONFIG_CONTENT = (
    "# Written by Nyxuri (remote-login unit); `nyxuri off remote-login` restores the original.\n"
    "# All options: /usr/share/doc/remote-dm/README.md\n"
    "\n"
    "[greeter]\n"
    f'command = "exec niri --headless --session -c {RDM_GREETER}"\n'
)

TRUSTED_EXEC_DIRS = (Path("/usr/bin"), Path("/usr/local/bin"))

PLUGIN_ID = "nyxuri/remote_login"
PLUGIN_SOURCE = Path(__file__).resolve().parent / "noctalia-plugin" / "remote_login"


def run(argv, input_text=None, capture=False):
    """Run argv; returns (ok, stdout). Never raises."""
    try:
        result = subprocess.run(
            argv, input=input_text, text=True, check=False,
            capture_output=capture,
        )
    except OSError:
        return False, ""
    return result.returncode == 0, (result.stdout or "") if capture else ""


def trusted_executable(name):
    """A root-owned regular executable in /usr/bin or /usr/local/bin, or None."""
    candidate = shutil.which(name)
    if not candidate:
        return None
    try:
        path = Path(candidate).resolve(strict=True)
        info = path.stat()
    except OSError:
        return None
    if path.parent not in TRUSTED_EXEC_DIRS or not stat.S_ISREG(info.st_mode):
        return None
    if info.st_uid != 0 or not info.st_mode & 0o111 or info.st_mode & 0o022:
        return None
    return str(path)


def niri_has_remote_desktop():
    niri = trusted_executable("niri")
    if not niri:
        return False
    try:
        with open(niri, "rb") as file, mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as data:
            return data.find(NIRI_REMOTE_DESKTOP_MARKER) != -1
    except (OSError, ValueError):
        return False


def read_root_file(path):
    """(ok, content or None when absent)."""
    ok, _ = run(["sudo", "test", "-e", str(path)])
    if not ok:
        return True, None
    ok, content = run(["sudo", "cat", "--", str(path)], capture=True)
    return ok, content if ok else None


def write_root_file(content, destination, mode="644", owner="root"):
    """Install content through a private temp file (no shell, no partial writes)."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        ok, _ = run(["sudo", "install", "-D", "-o", owner, "-g", owner, "-m", mode,
                     temp_path, str(destination)])
        return ok
    except OSError:
        return False
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


def remove_root_file(path):
    ok, _ = run(["sudo", "rm", "-f", "--", str(path)])
    return ok


def read_state():
    """(ok, state or None when not activated)."""
    ok, content = read_root_file(STATE)
    if not ok:
        return False, None
    if content is None:
        return True, None
    try:
        state = json.loads(content)
    except ValueError:
        return False, None
    return isinstance(state, dict), state if isinstance(state, dict) else None


def write_state(state):
    return write_root_file(json.dumps(state, indent=2) + "\n", STATE, mode="600")


def service_enabled(service):
    ok, _ = run(["systemctl", "is-enabled", "--quiet", service])
    return ok


def service_active(service):
    ok, _ = run(["systemctl", "is-active", "--quiet", service])
    return ok


def grd_status():
    """`grdctl --system status` as {key: value} (credentials stay hidden)."""
    ok, out = run(["sudo", "grdctl", "--system", "status"], capture=True)
    if not ok:
        return None
    status = {}
    for line in out.splitlines():
        key, sep, value = line.strip().partition(": ")
        if sep:
            status[key] = value
    return status


def undo(state):
    """Put everything back as recorded in `state`; returns whether it all worked."""
    ok = True
    if not state.get("rdm_enabled"):
        ok &= run(["sudo", "systemctl", "disable", "--now", RDM_SERVICE])[0]
    if state.get("credentials"):
        ok &= run(["sudo", "grdctl", "--system", "rdp", "clear-credentials"])[0]
    if not state.get("grd_enabled"):
        # Stops and disables the system daemon (unless VNC still wants it).
        ok &= run(["sudo", "grdctl", "--system", "rdp", "disable"])[0]

    grd_conf = state.get("grd_conf")
    if grd_conf is None:
        ok &= remove_root_file(GRD_CONF)
    else:
        ok &= write_root_file(grd_conf, GRD_CONF, owner=GRD_USER)
    if state.get("tls"):
        ok &= remove_root_file(TLS_CERT) and remove_root_file(TLS_KEY)
    if state.get("grd_enabled"):
        ok &= run(["sudo", "systemctl", "try-restart", GRD_SERVICE])[0]

    rdm_config = state.get("rdm_config")
    if rdm_config is None:
        ok &= remove_root_file(RDM_CONFIG)
    else:
        ok &= write_root_file(rdm_config, RDM_CONFIG)

    if ok:
        ok = remove_root_file(STATE)
    return ok


def plugin_dir():
    """Noctalia's local plugin dir for ours ($XDG_DATA_HOME/noctalia/plugins/remote_login)."""
    data = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data) / "noctalia" / "plugins" / PLUGIN_SOURCE.name


def install_plugin():
    """Copy the plugin in and enable it. Returns (installed, enabled); not installed when
    Noctalia isn't."""
    if not shutil.which("noctalia"):
        return False, False
    dest = plugin_dir()
    changed = False
    try:
        wanted = set()
        for source in sorted(PLUGIN_SOURCE.rglob("*")):
            if source.is_dir() or "__pycache__" in source.parts:
                continue
            rel = source.relative_to(PLUGIN_SOURCE)
            wanted.add(rel)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            content = source.read_bytes()
            # In place, not replaced: Noctalia watches the files and reloads the plugin
            # on changes, which a new inode would escape.
            if not target.is_file() or target.read_bytes() != content:
                target.write_bytes(content)
                changed = True
        for stale in sorted(dest.rglob("*"), reverse=True):
            rel = stale.relative_to(dest)
            if stale.is_file() and rel not in wanted:
                stale.unlink()
                changed = True
            elif stale.is_dir() and not any(stale.iterdir()):
                stale.rmdir()
    except OSError:
        return False, False
    # Noctalia hot-reloads the scripts, but registers the entries (panel options, a new bar
    # widget) only when the plugin is enabled: after a change, disable it first so it picks up
    # the new manifest. Needs a running Noctalia; otherwise Settings -> Plugins does it.
    if changed:
        run(["noctalia", "msg", "plugins", "disable", PLUGIN_ID], capture=True)
    enabled, _ = run(["noctalia", "msg", "plugins", "enable", PLUGIN_ID], capture=True)
    return True, enabled


def remove_plugin():
    if shutil.which("noctalia"):
        run(["noctalia", "msg", "plugins", "disable", PLUGIN_ID], capture=True)
    shutil.rmtree(plugin_dir(), ignore_errors=True)
