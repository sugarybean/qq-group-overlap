# QQ 群重合成员分析器

找出同时出现在多个 QQ 群的人，用作发现兴趣圈层重合的线索。

它不会根据昵称猜测身份：只有 QQ 号完全相同才算同一人。同一人在不同群里使用的昵称和群名片会一起保留。

## 目录

- [它能做什么](#它能做什么)
- [打开即用：GUI 三步上手](#打开即用gui-三步上手)
- [启动 GUI](#启动-gui)
- [GUI 使用步骤](#gui-使用步骤)
- [输出内容](#输出内容)
- [常见问题](#常见问题)
- [高级：连接已经运行中的 NapCat（--api）](#高级连接已经运行中的-napcat--api)
- [附录 A：先用示例看效果](#附录-a先用示例看效果)
- [附录 B：JSON / CSV 输入格式](#附录-bjson--csv-输入格式)
- [附录 C：命令行用法（需自行先运行 NapCat）](#附录-c命令行用法需自行先运行-napcat)
- [测试](#测试)
- [隐私提醒](#隐私提醒)

## 它能做什么

- 给定若干 QQ 群，找出同时出现在多个群里的人，并按「共同群数 + 各群等级对数加分」排序。
- 群等级可选：等级越高、所在的群越活跃，加分越多。
- 结果分页显示、可完整导出 CSV，也可生成脱敏（打码）报告用于分享。
- 本地 GUI 一键操作，无需写代码；核心逻辑只用 Python 标准库，无第三方依赖。

## 打开即用：GUI 三步上手

本工具的目标是 **「打开 → 扫码 → 拿到数据」**，不需要你手动安装 NapCat、不需要打开网页管理面板、也不需要复制任何令牌。这一切由 GUI 自动完成。

> **自动下载目前支持**：Linux（amd64 / arm64）和 Windows（amd64）。**macOS 暂不支持自动安装**——请直接看 [高级：连接已经运行中的 NapCat（--api）](#高级连接已经运行中的-napcat--api)，先按 NapCat 官方文档装好并登录，再用 `--api` 启动本工具即可。

推荐用 GUI，三步：

1. **启动 GUI**（见 [启动 GUI](#启动-gui)）。
2. **首次打开自动准备连接组件**：程序在后台自动联网下载并解包 QQ 连接组件（NapCat，来自官方 GitHub 发布页，仅本机使用）。这一步只需一次——下载完成后会缓存，以后直接复用。窗口内会实时显示下载 / 解包进度。准备就绪后，窗口里会出现一个二维码。
3. **手机 QQ 扫码登录**：用手机 QQ 扫这个二维码并确认。登录成功后窗口自动进入分析界面。之后再打开本工具会**复用上次的登录状态，无需重复扫码**（只要没主动退出登录或清理数据目录）。

几点说明：

- 二维码只在本地窗口里显示，**不会写入任何报告或快照文件**。
- 登录态、访问令牌、NapCat 运行时都保存在当前用户的**数据目录**（Linux / macOS：`~/.local/share/qq-group-overlap/`；Windows：`%APPDATA%\qq-group-overlap\`），不污染系统目录，也不会随仓库提交。
- 内置的 QQ 连接组件**只监听本机**：OneBot HTTP 在 `127.0.0.1:3000`，WebUI 在 `127.0.0.1:6099`，不对局域网或公网开放。你不需要、也不应该去手动改这些端口。
- 关闭本工具时，它拉起的 QQ 连接组件也会随之关闭；下次打开会重新拉起。
- Linux 下需要正常的图形界面（桌面环境自带 `DISPLAY`），因为要弹出二维码登录窗口。

如果下载失败或很慢，程序会依次尝试直连 GitHub 与国内镜像加速（`gh-proxy.com`、`ghfast.top`）；仍失败时会提示重试，详见 [常见问题](#常见问题)。

## 启动 GUI

**Linux / macOS**，在项目目录运行：

```bash
./scripts/start-gui.sh
```

**Windows**，双击 `scripts\start-gui.bat`，或命令行进入项目目录后运行：

```bat
scripts\start-gui.bat
```

脚本会自动把 `src` 加入模块搜索路径并启动 GUI。两个脚本都支持转发额外参数，例如 `--snapshot 别的快照.json`（见下方高级用法）。

## GUI 使用步骤

1. 左上角输入群名或群号即可筛选；你的群列表已由本工具登录后**自动拉取并填充**，无需手动添加。
2. 单击选择一个群；按住 `Ctrl` 增减选择，按住 `Shift` 连续选择一段。所有已选群地位相同。
3. 选好群后，点「只刷新已选群等级」拉取成员与等级。NapCat 由本工具自动管理，只要 GUI 开着且已扫码登录即可（无需额外操作）。
4. 选择预设算法，或直接修改评分公式。
5. 点「开始评价」。结果没有人数上限，界面分页显示，并可完整导出 CSV。

### 评分公式

默认对数加权：

```text
分数 = shared_groups + log_level_sum
```

其中 `log_level_sum = Σ log₂(1 + 群等级)`，因此默认算法与逐群对数加权完全相同。还可使用 `level_sum`、`level_avg`、`level_max`、`known_levels`、`missing_levels`，以及 `abs`、`log2`、`min`、`max`、`sqrt` 函数。公式采用受限语法，不执行任意 Python 代码。

### 特别关照群

按住 `Ctrl + X` 时点选群，可把这些群设为**特别关照群**。它们会被视为「必须包含」的硬性条件：结果列表中每个人必须同时出现在所有特别关照群里。放开 `Ctrl + X` 后继续正常选择，两者叠加。每次重新标记即临时生效，下次评估重新算。

## 输出内容

- `report.md`：适合直接阅读的重复成员排行和群重合表。
- `overlap_members.csv`：所有重复成员，可用 LibreOffice/Excel 筛选。
- `group_pairs.csv`：每两个群的交集人数、Jaccard 重合率和双向覆盖率。

Jaccard 越高，两个群的成员结构越相似。「交集占群 A」更适合看一个小群是否几乎被另一个大群包含。

## 常见问题

### 首次打开要联网下载 NapCat，但下载失败 / 很慢

内置下载会依次尝试直连 GitHub 与国内镜像（`gh-proxy.com`、`ghfast.top`）。若仍失败，多半是网络环境限制：

- 确认这台机器能正常访问外网（GitHub 发布页）。
- 关闭可能拦截下载的全局代理后再试。
- 点窗口里的「重试」会重新走一遍下载流程。

> 下载只发生一次，成功后缓存到用户数据目录的 `napcat/` 子目录，后续启动直接用。

### 报错「HTTP Error 502: Bad Gateway」，但连接组件明明开着

如果你的终端设了全局代理（`http_proxy` / `https_proxy` 环境变量，或系统代理），发往 `127.0.0.1` 的本机请求可能被代理劫走，代理连不上 NapCat 就返回 502。本工具的 HTTP 客户端**已内置忽略代理、直连本机**的逻辑，正常不会触发此问题；若确认仍出现 502，请检查并临时清掉当前终端的代理变量再试：

```bash
# Linux / macOS：当前终端临时取消代理
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
```

```bat
:: Windows cmd：当前窗口临时取消代理
set http_proxy=
set https_proxy=
```

### 提示「找不到输入文件：…/members.private.json」

这是**正常现象**，不是程序坏了。`members.private.json` 是成员快照，记录从 QQ 拉到的群成员——它**不在仓库里**，首次使用必然不存在，需要你自己生成一次。

默认快照保存在**当前用户的数据目录**（Linux / macOS：`~/.local/share/qq-group-overlap/members.private.json`；Windows：`%APPDATA%\qq-group-overlap\members.private.json`），**与你在哪个目录运行命令无关**，换目录不会丢。也可用 `--snapshot` 指定别的路径。

生成它，任选一种：

- 打开 GUI → 选好群 → 点「只刷新已选群等级」（会自动写入快照）
- 命令行 `live`：`python -m qq_group_overlap live`（列出群、选序号、自动生成；需自行先运行 NapCat，见 [附录 C](#附录-c命令行用法需自行先运行-napcat)）
- 命令行 `fetch`：`python -m qq_group_overlap fetch --groups 群号1,群号2 -o 快照.json`

想先看看效果，可用内置示例数据（无需 NapCat）：

```bash
python -m qq_group_overlap analyze examples/members.example.json -o report
```

### 点「只刷新已选群等级」报错「无法连接 QQ 连接组件」

- **GUI 内置模式**：NapCat 由本工具自动管理。若弹出这个错误，通常是连接组件意外退出——**关闭窗口重开即可重新拉起**；若反复失败，多半是首次下载未完成或网络不可达（见上面的下载 FAQ）。
- **外部 / 命令行模式**（你用 `--api` 连自己的 NapCat）：请确认你启动的 NapCat 还在运行、QQ 已登录、OneBot HTTP 服务器开关是打开的，且 `--api` 地址与 `--token` / 环境变量里的令牌完全一致。

### 端口 3000 被占用

本工具内置的 QQ 连接组件固定使用本机 `127.0.0.1:3000`。若该端口被其他程序占用，连接组件会启动失败——请先关闭占用 3000 端口的程序，再打开本工具。

### 启动报「找不到 python」

Python 没装好或没加入 PATH。需要 **Python 3.11 或更新版本**：

- **Windows**：打开 <https://www.python.org/downloads/windows/> 下载 64 位安装包，运行后**务必勾选 `Add Python to PATH`** 再点 `Install Now`。
- **Linux / macOS**：一般系统已自带 Python 3，终端验证 `python3 --version` 即可。

### 二维码扫不出来 / 登录不上

NapCat 偶尔因 QQ 版本或网络问题登不上。可换扫码方式、稍等重试、更新到最新版 NapCat、或改用外部模式配合已安装的最新 QQ（见 [高级用法](#高级连接已经运行中的-napcat--api)）。

### 群成员的「等级」显示缺失

这是正常的。旧快照或某些群没有等级数据，工具会明确显示「缺失」而不是悄悄填 0。点「只刷新已选群等级」后，有等级的群会补上。

## 高级：连接已经运行中的 NapCat（--api）

默认情况下，GUI 会自动下载并管理 NapCat（内置模式）。但在以下情况，你可能想**连接一个你自己已经跑起来的 NapCat**：

- 你在 **macOS** 上（自动下载暂不支持），已按官方文档装好并登录 NapCat。
- 你已经在别的机器 / 容器里跑着 NapCat，想在本工具里连过去。
- 你想用官方 WebUI 手动管理 NapCat。

此时给 GUI 传 `--api`（以及可选的 `--token` / `--token-env`），本工具就只做「连接」，**跳过下载与扫码**，直接进入分析界面：

```bash
# Linux / macOS
./scripts/start-gui.sh --api http://127.0.0.1:3000 --token 你的token
# 或让工具从环境变量读取令牌
./scripts/start-gui.sh --api http://127.0.0.1:3000 --token-env ONEBOT_ACCESS_TOKEN

# Windows
scripts\start-gui.bat --api http://127.0.0.1:3000 --token 你的token
```

外部 NapCat 那边需要：开启一个 OneBot 11 **HTTP 服务器**，Host 填 `127.0.0.1`（不要设 `0.0.0.0`，否则对外网开放），端口与 `--api` 里的一致，并设置一个 Token 与 `--token` / 环境变量一致。Token 只存在命令行参数或环境变量里，不会写入任何快照或报告。

## 附录 A：先用示例看效果

示例数据只随仓库提供（`pip install` 后不在安装目录里），所以这条命令要**在你克隆下来的项目目录内**运行：

```bash
cd 你克隆的项目目录
PYTHONPATH=src python3 -m qq_group_overlap analyze \
  examples/members.example.json -o report
```

然后打开 `report/report.md`。如果已经 `pip install .` 装成命令了，也可以用你拉取的真实快照代替示例数据：

```bash
qq-group-overlap analyze 你的快照.json -o report
```

## 附录 B：JSON / CSV 输入格式

### JSON 输入格式

```json
{
  "groups": [
    {
      "group_id": "10001",
      "group_name": "摄影社",
      "members": [
        {
          "user_id": "123456789",
          "nickname": "小明",
          "card": "风光摄影小明",
          "role": "member",
          "is_robot": false,
          "level": 12
        }
      ]
    }
  ]
}
```

### CSV 输入格式

将多个群的成员放在一个 CSV 中，每行一个成员：

```csv
group_id,group_name,user_id,nickname,card,role,is_robot
10001,摄影社,123456789,小明,风光摄影小明,member,false
10002,徒步群,123456789,小明,明天爬山,member,false
```

`group_id` 和 `user_id` 必填，其他列可以留空。如需对数加权，可增加 `level` 列。

## 附录 C：命令行用法（需自行先运行 NapCat）

> 下面这些命令行子命令（`live` / `fetch` / `analyze`）沿用「连接一个**已在运行**的 OneBot 端点」的方式，**不会自动下载 NapCat**。适合已经用其他方式跑起 NapCat、或更喜欢命令行的用户。想「打开即用」请优先用 GUI（见上文）。

### 安装为命令（推荐）

项目根目录的 `pyproject.toml` 已配好入口，装一次之后就能直接用 `qq-group-overlap` 命令，不必每次设 `PYTHONPATH`：

```bash
cd qq-group-overlap
python3 -m pip install .
```

装好后用 `qq-group-overlap` 和 `qq-group-overlap-gui` 两个命令，效果等同于 `python3 -m qq_group_overlap` / `python3 -m qq_group_overlap.gui`。如果暂时不想安装，也可以直接用下文的 `PYTHONPATH=src` 写法，不必安装也能跑。

> **Windows 用户**：用 `python -m pip install .`（注意 Windows 上是 `python` 不是 `python3`），装好后命令名相同。

### 分析你选定的群

先用 `fetch` 或 `live` 生成一份成员快照（见下文「通过 OneBot HTTP 生成快照」），再对它分析：

```bash
PYTHONPATH=src python3 -m qq_group_overlap analyze members.private.json \
  -o report \
  --groups 10001,10002,10003 \
  --exclude-users 88888888,66666666
```

常用参数：

- `--min-groups 3`：只显示至少出现在 3 个群的人。
- `--exclude-users 123,456`：排除指定的 QQ 号，常用于排除你认识的机器人或不想出现在结果里的熟人。**注意**：`live` 命令会自动排除当前登录的自己，但 `analyze` 不会——如果你是用 `fetch` 从自己的号拉的数据再 `analyze`，记得加 `--exclude-users 你的QQ号`。
- `--include-bots`：默认过滤标记为机器人的成员；加此参数则保留。
- `--mask-ids`：生成便于分享的脱敏报告，例如 `123***789`。
- `--limit 50`：Markdown 只展示前 50 人；CSV 仍保留全部结果。

### 通过 OneBot HTTP 生成快照

若你已有可用的 OneBot HTTP 端点（由你自己启动的 NapCat 提供），可以直接拉取指定群：

```bash
export ONEBOT_ACCESS_TOKEN='你本地设置的Token'

PYTHONPATH=src python3 -m qq_group_overlap fetch \
  --api http://127.0.0.1:3000 \
  --groups 10001,10002,10003 \
  -o members.private.json
```

Token 只从环境变量读取，不会写入快照。`*.private.json`、`snapshots/` 和 `report/` 默认不进 Git。

### 本机一键模式（命令行，需自行先运行 NapCat）

当 NapCat 已在本机登录并启动后，直接运行：

```bash
./scripts/run-live-report.sh
```

工具会列出当前账号所在的所有 QQ 群。输入序号，例如 `1,3,8`，就会拉取这些群并立即生成报告。也可以非交互运行：

```bash
./scripts/run-live-report.sh --groups 10001,10002,10003
```

> **Windows 用户**：上述 `run-live-report.sh` 是 Linux 脚本。Windows 下请改用 GUI（`scripts\start-gui.bat`），或直接运行 `python -m qq_group_overlap live`。

生成报告时会自动读取当前登录的 QQ 号并从重合结果中排除，不需要手动修改账号配置。

这个项目的 OneBot HTTP 仅监听 `127.0.0.1:3000`，WebUI 仅监听 `127.0.0.1:6099`，不对局域网或公网开放。

## 测试

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

测试不访问真实 QQ 或网络。

## 隐私提醒

成员快照里有 QQ 号和群名片，应当按私密文件处理。如果要把报告发给别人，请使用 `--mask-ids`，并且不要分享原始快照。

共同群多只能说明兴趣圈层可能重合，不代表对方一定愿意被联系。
