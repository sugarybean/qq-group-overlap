# QQ 群重合成员分析器

找出同时出现在多个 QQ 群的人，用作发现兴趣圈层重合的线索。

它不会根据昵称猜测身份：只有 QQ 号完全相同才算同一人。同一人在不同群里使用的昵称和群名片会一起保留。

## 推荐：用本地 GUI

**Linux / macOS**，在项目目录运行：

```bash
./scripts/start-gui.sh
```

**Windows**，双击 `scripts\start-gui.bat`，或在命令行进入项目目录后运行：

```bat
scripts\start-gui.bat
```

Windows 用户需要先安装并配置 NapCat（OneBot 11），完整图文教程见 [docs/windows-setup.html](docs/windows-setup.html)（双击即可在浏览器打开）。

使用步骤：

1. 在左上角输入群名或群号，例如“自动化”。
2. 单击选择一个群；按住 `Ctrl` 增减选择，按住 `Shift` 连续选择一段。所有已选群地位相同。
3. 首次做等级打分前，点“只刷新已选群等级”。NapCat 必须已启动且 QQ 已登录。
4. 选择预设算法，或直接修改评分公式。
5. 点“开始评价”。结果没有人数上限，界面分页显示，并可完整导出 CSV。

对数加权分为：

```text
分数 = shared_groups + log_level_sum
```

其中 `log_level_sum = Σ log₂(1 + 群等级)`，因此默认算法与原先的逐群对数加权完全相同。还可使用 `level_sum`、`level_avg`、`level_max`、`known_levels`、`missing_levels`，以及 `abs`、`log2`、`min`、`max`、`sqrt` 函数。公式采用受限语法，不执行任意 Python 代码。

界面只渲染当前页，不会向终端打印完整名单；点击“导出全部结果”时才会写出完整 CSV。

## 输出内容

- `report.md`：适合直接阅读的重复成员排行和群重合表。
- `overlap_members.csv`：所有重复成员，可用 LibreOffice/Excel 筛选。
- `group_pairs.csv`：每两个群的交集人数、Jaccard 重合率和双向覆盖率。

Jaccard 越高，两个群的成员结构越相似。“交集占群 A”更适合看一个小群是否几乎被另一个大群包含。

## 先用示例看效果

```bash
cd qq-group-overlap
PYTHONPATH=src python3 -m qq_group_overlap analyze \
  examples/members.example.json -o report
```

然后打开 `report/report.md`。

## JSON 输入格式

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

## CSV 输入格式

将多个群的成员放在一个 CSV 中，每行一个成员：

```csv
group_id,group_name,user_id,nickname,card,role,is_robot
10001,摄影社,123456789,小明,风光摄影小明,member,false
10002,徒步群,123456789,小明,明天爬山,member,false
```

`group_id` 和 `user_id` 必填，其他列可以留空。如需对数加权，可增加 `level` 列。

## 分析你选定的群

```bash
PYTHONPATH=src python3 -m qq_group_overlap analyze members.private.json \
  -o report \
  --groups 10001,10002,10003 \
  --exclude-users 你自己的QQ号
```

常用参数：

- `--min-groups 3`：只显示至少出现在 3 个群的人。
- `--exclude-users 123,456`：排除自己、熟知机器人等 QQ 号。
- `--include-bots`：默认过滤标记为机器人的成员；加此参数则保留。
- `--mask-ids`：生成便于分享的脱敏报告，例如 `123***789`。
- `--limit 50`：Markdown 只展示前 50 人；CSV 仍保留全部结果。

## 通过 OneBot HTTP 生成快照

若你已有可用的 OneBot HTTP 端点，可以直接拉取指定群：

```bash
export ONEBOT_ACCESS_TOKEN='你本地设置的Token'

PYTHONPATH=src python3 -m qq_group_overlap fetch \
  --api http://127.0.0.1:3000 \
  --groups 10001,10002,10003 \
  -o members.private.json
```

Token 只从环境变量读取，不会写入快照。`*.private.json`、`snapshots/` 和 `report/` 默认不进 Git。

## 本机一键模式

当 NapCat 已在本机登录并启动后，直接运行：

```bash
./scripts/run-live-report.sh
```

工具会列出当前账号所在的所有 QQ 群。输入序号，例如 `1,3,8`，就会拉取这些群并立即生成报告。也可以非交互运行：

```bash
./scripts/run-live-report.sh --groups 10001,10002,10003
```

本地 NapCat 启动入口是：

```bash
./scripts/start-napcat.sh
```

本机 WebUI 地址是 `http://127.0.0.1:6099/webui/`，面板密钥在 NapCat 配置里自行设置。这是 NapCat 本机面板的登录密钥，不是 QQ 密码。

> **Windows 用户**：上述 `run-live-report.sh` 是 Linux 脚本。Windows 下请改用 GUI（`scripts\start-gui.bat`），或直接运行 `python -m qq_group_overlap live`。NapCat 的安装与连接方式见 [docs/windows-setup.html](docs/windows-setup.html)。

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
