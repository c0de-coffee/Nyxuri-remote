<div align="right">
  <strong>English</strong> | <a href="README.zh-CN.md">简体中文</a>
</div>

# Nyxuri with remote login

> [!NOTE]
> This is a fork of [ech678/Nyxuri](https://github.com/ech678/Nyxuri) by Echoes678, maintained by
> [c0de-coffee](https://github.com/c0de-coffee). **For what Nyxuri is, its units, keybindings and
> documentation, see the original repository:** https://github.com/ech678/Nyxuri. This README only
> covers what the fork adds and how to install the fork.
>
> Report problems with remote login here, not upstream.
>
> This fork was built with Claude.

## What the fork adds

- **`remote-login` unit**: log in to the machine over RDP, like GNOME's remote login. You get
  Noctalia Greeter as the login screen, then your own headless niri session, which keeps running
  when you disconnect. Several users can be logged in at once.
- **Remote Login panel and bar widget for Noctalia**: turn RDP on or off, see the address and
  certificate fingerprint to connect with, change the RDP username and password; the widget shows
  whether RDP is on and how many remote sessions there are.
- **Fixes for a few upstream bugs**, see [Upstream bugs fixed](#upstream-bugs-fixed).

## Install

Same as the original, with the fork's address.

### From a git checkout (recommended)

```bash
git clone --depth 1 https://github.com/c0de-coffee/Nyxuri-remote.git ~/Nyxuri
cd ~/Nyxuri && ./install.sh
```

### Standalone (online)

```bash
curl -fsSL --connect-timeout 10 https://raw.githubusercontent.com/c0de-coffee/Nyxuri-remote/remote-login/install.sh \
  | NYXURI_REPO=https://github.com/c0de-coffee/Nyxuri-remote.git bash
```

Don't leave out `NYXURI_REPO`: without it, the script pulls the original repository and installs
the original.

<details>
<summary>Mirror for China (gh-proxy)</summary>

```bash
git clone --depth 1 https://gh-proxy.org/https://github.com/c0de-coffee/Nyxuri-remote.git ~/Nyxuri
cd ~/Nyxuri && ./install.sh
```
</details>

`nyxuri-git` on the AUR is the original, without the fork's changes.

`nyxuri update` updates from the repository you installed from, that is, the fork.

## Remote login

### Prerequisites

- **niri with remote desktop support, and remote-dm**: they aren't in the Arch repositories or the
  AUR yet. Download `niri-remote-desktop` and `remote-dm` from
  [c0de-coffee/niri-remote's releases](https://github.com/c0de-coffee/niri-remote/releases) and install them with
  `sudo pacman -U` (`niri-remote-desktop` replaces the `niri` package). The unit tells you if
  they're missing.
- **No GDM**: remote-dm conflicts with it. Nyxuri's `greeter` unit (greetd + Noctalia Greeter) works
  for local logins. If GDM was just disabled and is still running, the unit asks you to reboot
  first.
- gnome-remote-desktop and noctalia-greeter are installed when the unit is turned on.

### Turning it on

```bash
nyxuri on remote-login
```

It:

1. Checks the prerequisites above.
2. Writes `/etc/remote-dm/config.toml`, with Noctalia Greeter as the remote login screen.
3. If gnome-remote-desktop has no TLS certificate, creates a self-signed one
   (`/var/lib/gnome-remote-desktop/nyxuri-rdp-tls.crt` and `.key`).
4. If there are no RDP credentials yet, asks for them once. Enter for the username means your
   account; Enter for the password generates a random one and shows it.
5. Enables RDP in gnome-remote-desktop's system mode, and enables and starts remote-dm.
6. With Noctalia installed, installs the Remote Login panel plugin.

It ends by showing the port (3389 by default). The first time, it records how the system was
before changing anything, and undoes everything if a step fails.

### Turning it off

```bash
nyxuri off remote-login
```

Removes the panel plugin, stops remote-dm (ending all remote sessions), restores remote-dm's and
gnome-remote-desktop's configuration and services to how they were before the unit was first
turned on, and removes the certificate and RDP credentials it created. Packages stay installed.

### Noctalia panel and bar widget

- **Panel**: like GNOME Settings' Remote Login page. Turn RDP on or off, see the address and
  certificate fingerprint, change the RDP username and password. Changes go through
  gnome-remote-desktop's configuration service, so Noctalia's polkit agent asks for an
  administrator password. Open it from the control center shortcut or with
  `noctalia msg panel-toggle nyxuri/remote_login:panel`.
- **Bar widget**: add it in Noctalia's bar settings. With RDP on, it shows a remote desktop icon and
  the number of remote sessions; with RDP off, a different icon.

### Connecting with a client

You enter two passwords: the RDP username and password in the client, then your system account's
password on the login screen. Windows' Remote Desktop Connection needs a changed `.rdp` file. Step
by step instructions, multiple monitors and troubleshooting are in remote-dm's README:
[Connecting](https://github.com/c0de-coffee/niri-remote/blob/remote-desktop/remote-dm/README.md#connecting),
[Troubleshooting](https://github.com/c0de-coffee/niri-remote/blob/remote-desktop/remote-dm/README.md#troubleshooting).

Known issues and limitations are in
[c0de-coffee/niri-remote's README](https://github.com/c0de-coffee/niri-remote/blob/remote-desktop/README.md#known-issues-and-limitations).

## Upstream bugs fixed

All reported upstream, and fixed in the fork:

| Problem | Upstream issue |
|---|---|
| `nyxuri on` for a single unit doesn't replace the `/home/user` placeholder in its config | [#143](https://github.com/ech678/Nyxuri/issues/143) |
| The wallpaper directory is hardcoded as `~/Pictures/Wallpapers` instead of following the XDG pictures directory (`~/图片` in Chinese, for example) | [#144](https://github.com/ech678/Nyxuri/issues/144) |
| The installer's wallpaper pack option doesn't download the pack, so it still shows as missing | [#145](https://github.com/ech678/Nyxuri/issues/145) |
| The GTK theme is set to adw-gtk3, but `adw-gtk-theme` isn't a dependency | [#146](https://github.com/ech678/Nyxuri/issues/146) |
| Turning on a hook-only unit (like greeter) warns about an invalid active preset state | [#147](https://github.com/ech678/Nyxuri/issues/147) |

## License and credits

GPL-3.0, like the original.

Thanks to Echoes678 and everyone who works on Nyxuri, which this fork only adds to, and to
[Noctalia](https://github.com/noctalia-dev), whose shell and greeter the remote login setup is
built around.
