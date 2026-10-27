<div align="right">
  <a href="README.md">English</a> | <strong>简体中文</strong>
</div>

# Nyxuri 远程登录 fork

> [!NOTE]
> 这是 [ech678/Nyxuri](https://github.com/ech678/Nyxuri)（作者 Echoes678）的 fork，由
> [c0de-coffee](https://github.com/c0de-coffee) 维护。**Nyxuri 本身的介绍、单元说明、快捷键和文档请看原仓库**：
> https://github.com/ech678/Nyxuri 。这里只写 fork 新增的内容，以及从 fork 安装的方法。
>
> 远程登录相关的问题请在本仓库提，不要报给原仓库。
>
> 这个 fork 的工作是用 Claude 完成的。

## fork 新增了什么

- **`remote-login` 单元**：像 GNOME 一样用 RDP 远程登录这台电脑。连上后先看到 Noctalia Greeter 登录界面，登录后进入自己独立的无头 niri 会话。断开后会话继续运行，可以多人同时登录。
- **Noctalia 的"远程登录"面板和顶栏组件**：开关 RDP、查看连接地址和证书指纹、修改 RDP 用户名和密码；顶栏显示 RDP 是否开启、当前有几个远程会话。
- **修复了原仓库的几个问题**，见[修复的原仓库问题](#修复的原仓库问题)。

## 安装

从 fork 安装，用法和原版一样，只是地址换成 fork。

### 从 git 仓库安装（推荐）

```bash
git clone --depth 1 https://github.com/c0de-coffee/Nyxuri-remote.git ~/Nyxuri
cd ~/Nyxuri && ./install.sh
```

### 在线安装

```bash
curl -fsSL --connect-timeout 10 https://raw.githubusercontent.com/c0de-coffee/Nyxuri-remote/remote-login/install.sh \
  | NYXURI_REPO=https://github.com/c0de-coffee/Nyxuri-remote.git bash
```

`NYXURI_REPO` 不能省：不设的话，安装脚本会去拉原仓库，装上的就是原版。

<details>
<summary>国内网络（gh-proxy）</summary>

```bash
git clone --depth 1 https://gh-proxy.org/https://github.com/c0de-coffee/Nyxuri-remote.git ~/Nyxuri
cd ~/Nyxuri && ./install.sh
```
</details>

AUR 上的 `nyxuri-git` 是原版，不包含 fork 的改动。

以后执行 `nyxuri update`，会从你安装时用的仓库（也就是 fork）更新。

## 远程登录

### 前置条件

- **带远程桌面支持的 niri 和 remote-dm**：Arch 官方源和 AUR 里都还没有，要从
  [c0de-coffee/niri 的 Releases](https://github.com/c0de-coffee/niri/releases) 下载
  `niri-remote-desktop` 和 `remote-dm` 两个包，用 `sudo pacman -U` 安装（会替换官方的 `niri` 包）。缺了它们，单元会提示你去下载。
- **不能用 GDM**：remote-dm 和 GDM 冲突。用 Nyxuri 的 `greeter` 单元（greetd + Noctalia Greeter）做本机登录就行。如果刚停用 GDM 还没重启，单元会提示先重启。
- gnome-remote-desktop 和 noctalia-greeter 会在开启单元时自动安装。

### 开启

```bash
nyxuri on remote-login
```

它会依次：

1. 检查上面的前置条件。
2. 写入 `/etc/remote-dm/config.toml`，让远程登录界面使用 Noctalia Greeter。
3. 如果 gnome-remote-desktop 还没有 TLS 证书，生成一个自签名证书（`/var/lib/gnome-remote-desktop/nyxuri-rdp-tls.crt` 和 `.key`）。
4. 如果还没有 RDP 用户名和密码，问你一次。用户名直接回车就是当前账户；密码直接回车会生成一个随机密码并显示出来。
5. 开启 gnome-remote-desktop 系统模式的 RDP，启用并启动 remote-dm。
6. 装了 Noctalia 的话，安装"远程登录"面板插件。

完成后会显示端口（默认 3389）。第一次开启时会先记下系统原来的状态，中途有一步失败就自动还原。

### 关闭

```bash
nyxuri off remote-login
```

删掉面板插件，停止 remote-dm（会结束所有远程会话），把 remote-dm 和 gnome-remote-desktop 的配置和服务状态还原成第一次开启之前的样子，并删掉开启时生成的证书和 RDP 用户名密码。软件包不会卸载。

### Noctalia 面板和顶栏组件

- **面板**：和 GNOME 设置里的"远程登录"页面类似，可以开关 RDP，查看连接地址和证书指纹，修改 RDP 用户名和密码。修改要通过 gnome-remote-desktop 的配置服务，Noctalia 的 polkit 代理会弹窗要管理员密码。从控制中心的快捷按钮打开，或者执行
  `noctalia msg panel-toggle nyxuri/remote_login:panel`。
- **顶栏组件**：在 Noctalia 的顶栏设置里添加。RDP 开着时显示远程桌面图标和当前远程会话数，关着时显示另一个图标。

### 用客户端连接

连接时要输入两次密码：先是客户端问的 RDP 用户名和密码，再是登录界面里的系统账户密码。Windows 自带的远程桌面连接要先改 `.rdp` 文件。详细步骤、多显示器和排错见 remote-dm 的说明：
[客户端连接](https://github.com/c0de-coffee/niri/blob/remote-desktop/remote-dm/README.zh-CN.md#客户端连接)、
[排错](https://github.com/c0de-coffee/niri/blob/remote-desktop/remote-dm/README.zh-CN.md#排错)。

已知问题和限制见 [c0de-coffee/niri 的 README](https://github.com/c0de-coffee/niri/blob/remote-desktop/README.zh-CN.md#已知问题和限制)。

## 修复的原仓库问题

这些问题都已经在原仓库提了 issue，fork 里已经修好：

| 问题 | 原仓库 issue |
|---|---|
| 单独执行 `nyxuri on` 某个单元时，配置里的 `/home/user` 占位符不会被替换 | [#143](https://github.com/ech678/Nyxuri/issues/143) |
| 壁纸目录写死为 `~/Pictures/Wallpapers`，和中文环境的 `~/图片` 等 XDG 图片目录不一致 | [#144](https://github.com/ech678/Nyxuri/issues/144) |
| 安装器勾选"壁纸包"后不会下载壁纸包，装完仍然显示缺少 | [#145](https://github.com/ech678/Nyxuri/issues/145) |
| GTK 主题设成 adw-gtk3，但 `adw-gtk-theme` 没有列进依赖 | [#146](https://github.com/ech678/Nyxuri/issues/146) |
| 开启只有钩子的单元（比如 greeter）时，误报"活动预设状态无效" | [#147](https://github.com/ech678/Nyxuri/issues/147) |

## 许可证和致谢

和原版一样使用 GPL-3.0。

感谢 Echoes678 和 Nyxuri 的所有贡献者，这个 fork 只是在 Nyxuri 上加了一些东西；也感谢 [Noctalia](https://github.com/noctalia-dev)，远程登录的设置面板和登录界面都是围绕它的桌面和登录界面做的。
