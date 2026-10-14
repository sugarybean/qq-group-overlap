# QQ 群重合成员分析器

找出同时出现在多个 QQ 群的人，用作发现兴趣圈层重合的线索。

它不会根据昵称猜测身份：只有 QQ 号完全相同才算同一人。同一人在不同群里使用的昵称和群名片会一起保留。

## 目录

- [它能做什么](#它能做什么)
- [安装与连接 NapCat（必读）](#安装与连接-napcat必读)
- [每次使用前：确认 NapCat 还在运行](#每次使用前确认-napcat-还在运行)
- [启动 GUI](#启动-gui)
- [GUI 使用步骤](#gui-使用步骤)
- [输出内容](#输出内容)
- [常见问题](#常见问题)
- [附录 A：先用示例看效果](#附录-a先用示例看效果)
- [附录 B：JSON / CSV 输入格式](#附录-bjson--csv-输入格式)
- [附录 C：命令行完整用法](#附录-c命令行完整用法)
- [测试](#测试)
- [隐私提醒](#隐私提醒)

## 它能做什么

- 给定若干 QQ 群，找出同时出现在多个群里的人，并按「共同群数 + 各群等级对数加分」排序。
- 群等级可选：等级越高、所在的群越活跃，加分越多。
- 结果分页显示、可完整导出 CSV，也可生成脱敏（打码）报告用于分享。
- 本地 GUI 一键操作，无需写代码；核心逻辑只用 Python 标准库，无第三方依赖。

## 安装与连接 NapCat（必读）

本工具通过 **NapCat（OneBot 11 协议）** 读取你所在 QQ 群的成员名单。用之前需要先装好 NapCat、扫码登录 QQ、开启 OneBot HTTP 服务。下面按 Windows / Linux / macOS 分平台说明，全程 5 步。官方仓库是 [NapNeko/NapCatQQ](https://github.com/NapNeko/NapCatQQ)，文档见 <https://doc.napneko.icu/>。

### 第一步：安装 Python

本工具用 Python 编写，只用标准库，无需额外依赖。需要 **Python 3.11 或更新版本**。

- **Windows**：打开 <https://www.python.org/downloads/windows/>，下载 64 位安装包（如 `python-3.12.x-amd64.exe`），运行后**务必勾选 `Add Python to PATH`** 再点 `Install Now`。
- **Linux / macOS**：一般系统已自带 Python 3，无需额外安装。

安装后在命令行验证：

```bash
python --version
```

看到 `Python 3.11.x` 或更高版本即成功（Linux/macOS 若 `python` 不存在，试 `python3 --version`）。

### 第二步：下载并安装 NapCat

#### Windows

推荐官方一键安装包（无需预先装 QQ）：

1. 打开 Releases 页面：<https://github.com/NapNeko/NapCatQQ/releases>
2. 下载 **`NapCat.Shell.Windows.OneKey.zip`**，解压。
3. 双击 `NapCatInstaller.exe`，等待自动完成配置。
4. 完成后进入生成的 `NapCat.XXXX.Shell` 目录。

> 一键包适合新手。如果你电脑已装新版 NTQQ（腾讯 QQ），也可改用 **Shell 版**（`NapCat.Shell.zip`），让 NapCat 去调用已装的 QQ。

#### Linux

官方一键安装脚本，支持基于 apt / dnf 的 amd64、arm64 系统，安装到当前用户的 `~/Napcat`：

```bash
curl -fL --connect-timeout 20 --max-time 1800 \
  -o napcat.sh https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/install.sh &&
bash napcat.sh --docker n --cli y --github-proxy 0
```

装完后用 `napcat` 命令管理服务。命令行不可用时，把上面的 `--cli y` 换成 `--tui` 走交互界面。国内网络下载慢，可给 `--github-proxy` 传 GitHub 加速地址。

#### macOS

支持 macOS 12+（Intel 和 Apple Silicon）：

1. 先把腾讯 QQ 装到 `/Applications/QQ.app`。
2. 下载并打开 [NapCat-Mac-Installer](https://github.com/NapNeko/NapCat-Mac-Installer/releases/latest)，按提示选择下载方式并安装。
3. 按提示授权修改 QQ 入口，切换到 NapCat 后启动。

FFmpeg 已随 NapCat 提供，无需另装。

### 第三步：扫码登录 QQ

按你的平台启动 NapCat：

- **Windows**：在 `NapCat.XXXX.Shell` 目录里双击 `napcat.bat`。
- **Linux**：终端运行 `napcat`（或按安装脚本提示的启动方式）。
- **macOS**：按安装器提示启动 NapCat。

启动后，控制台会弹出二维码（或自动拉起 QQ 登录窗口），用手机 QQ 扫码登录。登录成功后，日志里会出现类似一行：

```text
[WebUi] WebUi User Panel Url: http://127.0.0.1:6099/webui?token=XXXX
```

记下这个地址——这是 NapCat 的 WebUI（网页管理面板）。

### 第四步：开启 OneBot 11 HTTP 服务（最关键）

本工具通过 **HTTP 接口**（不是 WebSocket）访问 NapCat，所以要在 WebUI 里开一个 HTTP 服务。

1. 浏览器打开上一步记下的 WebUI 地址（形如 `http://127.0.0.1:6099/webui?token=XXXX`）。
2. 在左侧找到 **「网络配置」**（或 `Network Config`）。
3. 点 **「新建」**，选择 **「HTTP 服务器」**（OneBot 11 / HTTP Server）。
4. 按下表填写：

| 配置项 | 填什么 | 说明 |
| --- | --- | --- |
| 名称 / Name | `qq-overlap` | 随便起，方便辨认 |
| Host / 地址 | `127.0.0.1` | 只监听本机，安全 |
| Port / 端口 | `3000` | 默认端口，可改成别的 |
| Token / 鉴权 | （自定义一串） | 如 `你的token`，下一步要用 |

5. 点 **「保存」**，并确认这个 HTTP 服务器右上角开关是 **打开** 状态。
6. 保存后 NapCat 日志应出现类似 `HTTP 服务: 127.0.0.1:3000 已启动` 的提示。

> **关于端口和 Host**：`3000` 只是本工具的**默认**端口，不是唯一值——你完全可以在 WebUI 里把它改成 `3001`、`8080` 等任意空闲端口。关键是 NapCat 这边填的端口，要和你启动本工具时用的 `--api` 地址一致（见下文「启动 GUI」）。**Host 一定要是 `127.0.0.1`**，不要设成 `0.0.0.0`——那会对外网开放，非常危险，`127.0.0.1` 就够本机用了。

### 第五步：连接本工具并启动 GUI

连接靠环境变量 `ONEBOT_ACCESS_TOKEN`，把你在第四步设置的 token 填进去。

**Windows**（打开 `cmd` 进入项目目录）：

```bat
cd /d C:\你的路径\qq-group-overlap
set ONEBOT_ACCESS_TOKEN=你的token
scripts\start-gui.bat
```

**Linux / macOS**（打开终端进入项目目录）：

```bash
cd /你的路径/qq-group-overlap
export ONEBOT_ACCESS_TOKEN=你的token
./scripts/start-gui.sh
```

也可以一劳永逸地把 `ONEBOT_ACCESS_TOKEN` 设进系统环境变量（Windows：`Win + R` → `sysdm.cpl` →「高级」→「环境变量」→ 用户变量新建；Linux/macOS：写进 `~/.bashrc` 或 `~/.zshrc` 里的 `export ONEBOT_ACCESS_TOKEN=你的token`）。设好后重开终端生效。

> **如果你改了端口**（例如从 3000 改成了 3001），启动本工具时要加 `--api` 指向新地址：
>
> ```bash
> # Windows
> scripts\start-gui.bat --api http://127.0.0.1:3001
> # Linux / macOS
> ./scripts/start-gui.sh --api http://127.0.0.1:3001
> ```
>
> 命令行同理：`python -m qq_group_overlap live --api http://127.0.0.1:3001`。

> **Token 只存在环境变量里**：本工具不会把 token 写进任何快照或报告文件，只从环境变量 `ONEBOT_ACCESS_TOKEN` 读取，发到 GitHub 的公开仓库也不会泄露。

## 每次使用前：确认 NapCat 还在运行

NapCat 不是「装一次就能一直用」——它是常驻程序，**必须保持运行**，本工具才能连上它。以下几种情况它可能已经不在了：

- 电脑重启后，NapCat 不会自动启动，需要重新启动它（Windows 双击 `napcat.bat`，Linux 运行 `napcat`，macOS 按安装器提示）并确认 QQ 已在线。
- 你手动关掉了 NapCat 的窗口或进程。
- QQ 掉线 / 被挤下线，NapCat 虽然还开着，但已经拉不到成员了。

**怎么确认 NapCat 已就绪**：打开 WebUI（`http://127.0.0.1:6099/webui?token=XXXX`），能看到登录的 QQ 账号、在线状态正常即可。更直接的办法是跑一遍下面这条命令，能返回你的 QQ 信息就说明连通了：

```bash
curl -X POST http://127.0.0.1:3000/get_login_info -H "Content-Type: application/json" -H "Authorization: Bearer 你的token" -d "{}"
```

一句话记住：**先开 NapCat（确认在线），再开本工具**。连不上时十有八九是 NapCat 没在跑或 QQ 掉了。

## 启动 GUI

**Linux / macOS**，在项目目录运行：

```bash
./scripts/start-gui.sh
```

**Windows**，双击 `scripts\start-gui.bat`，或命令行进入项目目录后运行：

```bat
scripts\start-gui.bat
```

## GUI 使用步骤

1. 左上角输入群名或群号，例如「自动化」。
2. 单击选择一个群；按住 `Ctrl` 增减选择，按住 `Shift` 连续选择一段。所有已选群地位相同。
3. 首次做等级打分前，点「只刷新已选群等级」。NapCat 必须已启动且 QQ 已登录。
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

### 报错「HTTP Error 502: Bad Gateway」，但 NapCat 明明开着

如果你的终端设了全局代理（`http_proxy` / `https_proxy` 环境变量，或系统代理），发往 `127.0.0.1` 的本机请求可能被代理劫走，代理连不上 NapCat 就返回 502。本工具的 HTTP 客户端**已内置忽略代理、直连本机**的逻辑，正常不会触发此问题；若你用的是旧版本，或确认仍出现 502，请检查并临时清掉当前终端的代理变量再试：

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

这是**正常现象**，不是程序坏了。`members.private.json` 是成员快照（默认路径 `runtime/data/members.private.json`），记录从 NapCat 拉到的群成员——它**不在仓库里**（`runtime/` 已被 `.gitignore` 排除），所以首次使用必然不存在。

生成它，任选一种：

- 打开 GUI → 选好群 → 点「只刷新已选群等级」（会自动写入快照）
- 命令行 `live`：`python -m qq_group_overlap live`（列出群、选序号、自动生成）
- 命令行 `fetch`：`python -m qq_group_overlap fetch --groups 群号1,群号2 -o 快照.json`

想先看看效果，可用内置示例数据（无需 NapCat）：

```bash
python -m qq_group_overlap analyze examples/members.example.json -o report
```

### 点「只刷新已选群等级」报错「无法连接 NapCat」

- 先确认 NapCat 还在运行、QQ 已登录，方法见 [每次使用前：确认 NapCat 还在运行](#每次使用前确认-napcat-还在运行)。
- 确认 WebUI 里 HTTP 服务器开关是打开的，端口和你启动本工具时用的 `--api` 一致。
- 确认环境变量 `ONEBOT_ACCESS_TOKEN` 的值和 WebUI 里设置的 token 完全一致。

### 端口 3000 被占用

在 WebUI 里把 HTTP 服务器端口改成别的（如 `3001`），启动本工具时加 `--api` 参数：

```bat
scripts\start-gui.bat --api http://127.0.0.1:3001
```

### 启动报「找不到 python」

Python 没装好或没加入 PATH。回到第一步重装，勾选 `Add Python to PATH`，装完重开命令行。

### 二维码扫不出来 / 登录不上

NapCat 偶尔因 QQ 版本或网络问题登不上。可换扫码方式、稍等重试、更新到最新版 NapCat、或改用 Shell 版配合已安装的最新 QQ。

### 群成员的「等级」显示缺失

这是正常的。旧快照或某些群没有等级数据，工具会明确显示「缺失」而不是悄悄填 0。点「只刷新已选群等级」后，有等级的群会补上。

## 附录 A：先用示例看效果

```bash
cd qq-group-overlap
PYTHONPATH=src python3 -m qq_group_overlap analyze \
  examples/members.example.json -o report
```

然后打开 `report/report.md`。

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

## 附录 C：命令行完整用法

### 安装为命令（推荐）

项目根目录的 `pyproject.toml` 已配好入口，装一次之后就能直接用 `qq-group-overlap` 命令，不必每次设 `PYTHONPATH`：

```bash
cd qq-group-overlap
python3 -m pip install .
```

装好后用 `qq-group-overlap` 和 `qq-group-overlap-gui` 两个命令，效果等同于 `python3 -m qq_group_overlap` / `python3 -m qq_group_overlap.gui`。如果暂时不想安装，也可以直接用下文的 `PYTHONPATH=src` 写法，不必安装也能跑。

> **Windows 用户**：用 `python -m pip install .`（注意 Windows 上是 `python` 不是 `python3`），装好后命令名相同。

### 分析你选定的群

```bash
PYTHONPATH=src python3 -m qq_group_overlap analyze members.private.json \
  -o report \
  --groups 10001,10002,10003 \
  --exclude-users 88888888,66666666
```

常用参数：

- `--min-groups 3`：只显示至少出现在 3 个群的人。
- `--exclude-users 123,456`：排除指定的 QQ 号，常用于排除你认识的机器人或不想出现在结果里的熟人（`live` 命令会自动排除当前登录的自己）。
- `--include-bots`：默认过滤标记为机器人的成员；加此参数则保留。
- `--mask-ids`：生成便于分享的脱敏报告，例如 `123***789`。
- `--limit 50`：Markdown 只展示前 50 人；CSV 仍保留全部结果。

### 通过 OneBot HTTP 生成快照

若你已有可用的 OneBot HTTP 端点，可以直接拉取指定群：

```bash
export ONEBOT_ACCESS_TOKEN='你本地设置的Token'

PYTHONPATH=src python3 -m qq_group_overlap fetch \
  --api http://127.0.0.1:3000 \
  --groups 10001,10002,10003 \
  -o members.private.json
```

Token 只从环境变量读取，不会写入快照。`*.private.json`、`snapshots/` 和 `report/` 默认不进 Git。

### 本机一键模式

当 NapCat 已在本机登录并启动后，直接运行：

```bash
./scripts/run-live-report.sh
```

工具会列出当前账号所在的所有 QQ 群。输入序号，例如 `1,3,8`，就会拉取这些群并立即生成报告。也可以非交互运行：

```bash
./scripts/run-live-report.sh --groups 10001,10002,10003
```

> **注意**：`scripts/start-napcat.sh` 是本项目作者本机的专用部署脚本（基于 AppImage 解包 + bubblewrap 沙箱），依赖 `runtime/` 下的文件，**不随仓库分发，普通用户无法直接运行**。请按前文 [第二步](#第二步下载并安装-napcat) 用官方方式安装 NapCat。

本机 WebUI 地址是 `http://127.0.0.1:6099/webui?token=XXXX`，面板密钥在 NapCat 配置里自行设置。这是 NapCat 本机面板的登录密钥，不是 QQ 密码。

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
