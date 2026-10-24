# Nyxuri 活跃演进路线

> 本页只保留跨域活跃待办与长期目标；Shell 阶段台账、当前阶段与门禁见
> [shell/ROADMAP.md](shell/ROADMAP.md)。主线「插件市场化改造」KM0–KM5 已全数
> 落地收口，整卷台账冻结于 [archive/roadmap-history](llms-wiki/archive/roadmap-history.md)；
> 设计哲学与五条简洁标准见 [vision](llms-wiki/vision.md)。

## 主线收口

「桌面插件市场」产品形态成立：内核（registry · resolver · transaction · ledger）+
目录（万物皆单元）+ 市场界面（4 动词 + TUI 工坊），安装器退役为一次性引导。
术语四词（单元 / 内核 / 源 / manifest）与内核契约的唯一权威在
[unit-model](llms-wiki/unit-model.md)，此处不复述。

## 活跃路线（执行序即优先级）

| 站 | 交付 | 状态 |
| --- | --- | --- |
| T0 | 终端体验修复：复制粘贴终审 + 终端程序启动失败可见 | 进行中 |
| T1 | 上架 AUR：单包全量 nyxuri-git | 进行中 |
| T2 | TUI 重做：Textual 全量迁移 | 待开始（已定案） |
| T3 | 设置界面替换：Caelestia 式默认 + Dashboard 双轨 | 待开始 |
| T4 | Shell 可控性与透明化 | 待开始 |
| T5 | 多合成器 (Multi-WM) 架构解耦（门禁触发） | 待开始 |

### T0 终端体验修复（复制粘贴最终之战）

- **复制粘贴终审（已定案：正统方案）**：`Ctrl+Shift+C/V` 为唯一复制粘贴路径，
  零劫持——kitty 三处 Windows 式劫持（`ctrl+c` 智能中断、`ctrl+v` 粘贴、
  `ctrl+a` 全选复制）全部退役，右键粘贴随 `ctrl+v` 同块一并退役（定案扩充），
  Ctrl+C/V 还给终端程序；`copy_on_select no` 保留为显式复制语义。
  **已落地（2026-10-18）**：两份 kitty.conf + 回归护栏测试；剩 fish/vim/fzf/htop
  全矩阵实机验收。一次定案，此后不再翻烧饼。
- **终端程序启动失败可见**：msedit/micro 等 `Terminal=true` 桌面项当前无声失败
  （从启动器/文件管理打开 → 什么都没有）。实机诊断根因（xdg-terminal-exec
  在位性、默认终端登记、`gio open` 行为）→ 补终端桥与默认终端登记 →
  Shell 侧启动失败给通知反馈。终态：任何文件要么打开，要么给得出
  「为什么没打开」。**系统侧已修（2026-10-18）**：`xdg-terminal-exec` 入位
  （extra 0.14.3-2），shell 启动器 / GLib（≥2.76）/ key-cli 三条打开路径的
  汇合桥补齐；Shell 侧失败通知反馈降级为待办（现 `execDetached` 即发即忘，
  非阻塞项，留待需要时或 T4 一并做）。

### T1 上架 AUR（已定案：单包全量）

- **已落地（2026-10-18，含实机冒烟）**：PKGBUILD 重构——source 加 `pkgname::` 重命名修复
  克隆目录断裂（原 PKGBUILD 从未通过 makepkg，实测实锤）；单包全量
  `shell/` 树同船（`shell.*` 单元包模式下激活，实机 `nyxuri list`/`doctor` 验证）
  + 剪枝（tests、scripts/dev、过程文档；references/ 由 .gitignore 天然隔离）+
  `CHANGELOG.md` 进包（系统模式 `get_version` 真实化）+ `/usr/bin/nyxuri-shell`
  系统入口 + 双 LICENSE + `.install` 升级提示（升级不自动重部署，`nyxuri list`
  对账、`nyxuri install full` 显式应用）。依赖策略翻转：`depends=('python')`
  引擎运行时唯一，全部单元包 + CORE/AUR 会话工具链 + `ENGINE_OPTDEPENDS`
  （quickshell）转 optdepends——pacman 不再强塞桌面，干净 chroot 从此可解；
  catalog.toml 与 PKGBUILD 脱钩（只喂 `deps apps` 菜单）。
  实机冒烟全过：`/usr/bin/nyxuri` 系统模式识别、update 拒 git pull 提示 pacman
  （顺带修复系统包无 `.git` 时误报「更新失败」的短路顺序 bug）、doctor 三态对账、
  包版 shell 冷启动 IPC ready + 零包目录写入 + qmlcache/.qsb 全落用户缓存、
  `--stop` 干净退出不扰原会话。
  key-cli 暂缓：Clavis 上游独立后端，登记 [shell/KNOWN-ISSUES](shell/KNOWN-ISSUES.md)，
  待收回仓库内化后再落依赖。
- 上架完成（2026-10-18）：AUR `nyxuri-git` 已上架（2026-10-20 更新），
  README 安装段已回填。代码与验证全数收口：makepkg 实测、干净 chroot 构建、
  namcap E 清零（假阳性定性见 [packaging/README](packaging/README.md)）。
  遗留：humans-wiki Home 顶部 AUR 安装块回填（见 packaging/README 步骤 4）。

### T2 TUI 重做（已完成：Textual，一次全搬）

- **定案（2026-10-24）**：选型 Textual，迁移范围一次全搬——市场三屏
  （工坊 / 预设 / doctor）与全部过渡交互屏（组件清单 / deps / 快照 /
  卸载 / clean / 更新选择）进同一个 App；tui.py 手搓组件层（1806 行，
  其中约 400 行是键盘字节解析与 termios 保卫，Textual 内建）全数退役。
- **TUI 与 CLI 分离（定案修订）**：两套独立界面，功能不重叠也不互相
  派发。CLI 子命令（`clean` / `uninstall` / `deps` / `doctor` …）保持
  现有参数化行式形态，不改造、不跳进 App；TUI 里卸载、清理、deps、
  快照等屏幕一个不少，只是入口只有无参 `nyxuri` 一个，进去之后走 App
  自己的导航（首页 → 各屏）。取消的是「CLI 直达动词映射到 App 屏幕」
  那套做法，不是砍功能。两套界面共享引擎与文案键，不共享控制流。
- **终态分层**：`nyxuri/ux.py` 零依赖基座（`prompt_confirm` /
  `press_any_key` / `format_steps` / 宽度三件套）+ `nyxuri/market/` 唯一
  声明依赖层（全库唯一 `import textual`），内部按职责切分：
  `app.py`（App 骨架、全局键位、`handoff()`）/ `gate.py`（缺席守卫）/
  `data.py`（只读投影）/ `actions.py`（动作走 transaction）/
  `modals.py`（确认 / 输入 / 结果）/ `screens/`（唯一接触 widget 的层）。
  `data.py`、`actions.py` 不 import textual——测试因此不依赖图形栈。
  依赖单一方向：market → ux + 引擎，引擎永不 import market。
- **投影在 App，执行交终端**：App 只接管选择与浏览；pacman、部署管线、
  diff pager、$EDITOR 通过 `app.suspend()` 交出终端跑完收回，行式进度
  与完成屏原样留在 scrollback，引擎不为 App 做输出捕获改造。装包判断
  照抄 CLI `_cmd_on` 顺序（plan → missing → 有则整事务 handoff），轻
  开关不 suspend。suspend 期间终端回到 cooked，引擎行式
  `prompt_confirm`（AUR 引导等）零改动继续工作。
  `install_configs_workflow` / `offer_overwrite_upgrade` 只拆「选择」段，
  执行段不重写。
- **投影刷新**：屏幕挂载与回栈重读账本，动作后缓存失效重读——工坊
  现有 `_audit.clear()` 语义统一成协议。
- **依赖策略**：否决 vendor（拖 6 个传递包，塞进仓库就是无主文件）；
  python-textual 入 PKGBUILD `optdepends` + install.sh 引导装齐；缺席时
  交互入口提示 `pacman -S python-textual`，不留旧界面兜底。
- **契约修订**：AGENTS 不变量 3 收窄为「引擎核心零依赖，TUI 层为唯一
  声明依赖」，vision §3、tui-charter、overview、operation-map、
  testing 一并同步。
- **测试**：`data` / `actions` 用 TempEnv 纯单测；屏幕冒烟走
  `App.run_test()`，`handoff` 在无头驱动下注入 identity。未装 textual
  的机器全量单测照绿（`skipUnless` 守卫）。
- **分期**：M0 spike（kitty 下 pacman 交接、中文对齐、退出后终端干净、
  `run_test()` 可用性、Ctrl+C 语义——T0 已把 Ctrl+C 还给终端程序；有
  硬伤才回退 urwid）→ M1 骨架+契约（ux.py 拆出，旧界面照跑）→
  M2 工坊+首页（无参入口切 App）→ M3 预设+doctor → M4 过渡屏全迁 →
  M5 删 tui.py 与 menus.py、i18n 清键、契约终审。每期过全量单测、
  沙箱部署与 kitty 实机冒烟。
- **进展（2026-10-24，T2 完成）**：M1–M5 全部落地。`ux.py` 零依赖基座、
  `market/` 十屏（工坊 / 预设 / 组件清单 / 核心依赖 / 可选软件 / 快照 /
  更新 / 清理 / 卸载 / 诊断）、`python-textual` 入 optdepends、
  `tui.py` 与 `installer/menus.py` 已删、i18n 死键两轮清扫、AGENTS
  不变量与 wiki 契约同步。门禁：全量单测 + 沙箱部署 + kitty 实机冒烟。

### T3 设置界面替换（Caelestia 式）

- 以 Caelestia Shell（https://github.com/caelestia-dots/shell）的设置界面形态
  替换现 Default + Minimal 两个面板样式并成为默认；Dashboard 保留——
  `settingsPanelStyle` 轴三值收敛两值（已定案）。
- 只换皮：settings 模型、路由、搜索、动作与持久化
  （SettingsBackend / settings-routes.json）不动，不复制业务。

### T4 Shell 可控性与透明化

- 开工时立细则。方向：单元运行态可观测（进程 / 资源 / 副作用）、doctor 对账
  接入 Shell、日志与诊断直通——每样能力答得出「它为什么在这」。

### T5 多合成器解耦（门禁触发）

- 第三个合成器（Hyprland/Sway）接入前必须执行：`CompositorDriver` 驱动抽象
  收编过渡形态——`SUPPORTED_WMS` 硬编码元组、组件菜单 WM 特判、doctor 三处
  合成器字面量（债务登记见 [delayed-decisions](llms-wiki/delayed-decisions.md)）。
- 热重载、浮动便签与屏幕探测跨合成器适配，`doctor` 诊断与 `greeter` 会话自适应。

## Shell 侧

阶段台账、P4 验收与 P6 整体验收门禁唯一见 [shell/ROADMAP.md](shell/ROADMAP.md)，
此处不复述。未收口项（壁纸域取色内生、matugen 退役）随 Shell 阶段推进。

## 全局门禁（每阶段验收都过）

1. 五原则验收给可复现证据（真诚透明 / 绝对主权 / 骨架包容 / 轻盈生长 /
   通用自然，见 [vision](llms-wiki/vision.md)）。
2. 单一开关真相与单元边界不变量的唯一权威在
   [unit-model](llms-wiki/unit-model.md) 与 [AGENTS.md](AGENTS.md)，
   此处只链接不复述。
3. 架构 / 命令 / manifest 变更同步对应 wiki 页与台账（路由见 AGENTS.md）。

## 储备（不承诺）

- 第三方源信任分级与签名。
- 安全 Downdate 体系：现场快照优先还原 + Git 逆向检出的安全版本回退。
