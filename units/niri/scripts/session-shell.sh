#!/usr/bin/env bash
# ==============================================================================
# Nyxuri session shell gateway (session-shell.sh)
# Launches desktop shell and cleans up leftover compositor session scopes.
# ==============================================================================

set -euo pipefail

systemctl --user stop 'app-niri-noctalia-*.scope' >/dev/null 2>&1 || true

state_root="${XDG_STATE_HOME:-$HOME/.local/state}"
state_file="$state_root/nyxuri/state.json"
if [ ! -r "$state_file" ] && [ -r "$state_root/NyxNiri/state.json" ]; then
    state_file="$state_root/NyxNiri/state.json"
fi
active_shell="noctalia"
if [ -r "$state_file" ]; then
    if grep -Eq '"active_shell"[[:space:]]*:[[:space:]]*"(nyxuri-shell|custom)"' "$state_file" 2>/dev/null; then
        active_shell="nyxuri-shell"
    fi
fi

if [ "$active_shell" = "nyxuri-shell" ] || [ "$active_shell" = "custom" ]; then
    custom_shell_bin="${NYXURI_CUSTOM_SHELL_BIN:-}"
    if [ -z "$custom_shell_bin" ] && [ -r "$state_file" ]; then
        custom_bin_json=$(grep -o '"custom_shell_bin"[[:space:]]*:[[:space:]]*"[^"]*"' "$state_file" 2>/dev/null | head -n 1 | sed 's/.*"[[:space:]]*:[[:space:]]*"//;s/"//' || true)
        if [ -n "$custom_bin_json" ]; then
            custom_shell_bin="$custom_bin_json"
        fi
    fi

    if [ -z "$custom_shell_bin" ] && command -v nyxuri-shell >/dev/null 2>&1; then
        custom_shell_bin=$(command -v nyxuri-shell)
    fi

    if [ -n "$custom_shell_bin" ] && [ ! -x "$custom_shell_bin" ]; then
        healed="${custom_shell_bin%/bin/nyxuri-shell}/nyxuri-shell"
        if [ -x "$healed" ]; then
            custom_shell_bin="$healed"
        fi
    fi

    if [ -n "$custom_shell_bin" ] && [ -x "$custom_shell_bin" ]; then
        exec "$custom_shell_bin"
    else
        (
            sleep 2
            notify-send -u critical -a "Nyxuri" "Nyxuri Desktop Shell" \
                "自研 Shell 启动失败，已平滑回退至 Noctalia\nNyxuri shell failed to launch, fell back to Noctalia."
        ) >/dev/null 2>&1 &
        echo "Nyxuri shell (${custom_shell_bin:-<unset>}) is not executable, falling back to Noctalia" >&2
    fi
fi
# Remote sessions (logind Remote=yes, e.g. started by remote-dm): layer the *.toml files in
# ~/.config/noctalia/remote-session__custom__/ over the normal config. Noctalia reads every *.toml in its
# config dir (not subdirs) in name order, so a per-session mirror of symlinks with the overlays
# sorted last does it. The remote-login unit uses this to turn off idle suspend, which logind
# refuses for remote sessions anyway.
noctalia_remote_overlay() {
    local cfg="${XDG_CONFIG_HOME:-$HOME/.config}/noctalia"
    local overlay="$cfg/remote-session__custom__" mirror f
    [ -n "${XDG_SESSION_ID:-}" ] && [ -n "${XDG_RUNTIME_DIR:-}" ] || return 0
    [ "$(loginctl show-session "$XDG_SESSION_ID" -p Remote --value 2>/dev/null)" = yes ] || return 0
    compgen -G "$overlay/*.toml" >/dev/null || return 0
    mirror="$XDG_RUNTIME_DIR/noctalia-session-$XDG_SESSION_ID"
    rm -rf "$mirror" && mkdir -p "$mirror/noctalia" || return 0
    for f in "$cfg"/*; do
        [ "$f" = "$overlay" ] || ln -s "$f" "$mirror/noctalia/"
    done
    for f in "$overlay"/*.toml; do
        ln -s "$f" "$mirror/noctalia/zz-remote-session-${f##*/}"
    done
    export NOCTALIA_CONFIG_HOME="$mirror"
}
noctalia_remote_overlay || true
exec noctalia
