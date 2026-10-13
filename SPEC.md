# Spec: QQ 群重合成员分析器

## Objective

构建一个完全本地运行的小工具，用 QQ 号识别多个对等已选群中的重合成员，并用可配置的安全公式产生可解释排名。结果没有人数硬上限，GUI 分页显示且可完整导出；结果仅用于辅助发现兴趣圈层重合，不自动加好友、不发消息、不做人格推断。

## Tech Stack

- Python 3.11+
- 仅使用标准库：`argparse`、`csv`、`json`、`urllib`、`dataclasses`、`tkinter`
- 输入：统一 JSON 快照、合并 CSV，或 OneBot HTTP 群成员接口
- 输出：本地 GUI、完整结果 CSV；旧 CLI 仍支持 Markdown + CSV

## Commands

```bash
# 运行测试
PYTHONPATH=src python3 -m unittest discover -s tests -v

# 启动本地 GUI
./scripts/start-gui.sh

# 分析本地 JSON/CSV
PYTHONPATH=src python3 -m qq_group_overlap analyze members.json -o report

# 仅选部分群，并排除自己的 QQ 号
PYTHONPATH=src python3 -m qq_group_overlap analyze members.csv -o report \
  --groups 10001,10002,10003 --exclude-users 123456789

# 从 OneBot HTTP 获取指定群的成员快照
PYTHONPATH=src python3 -m qq_group_overlap fetch \
  --api http://127.0.0.1:3000 --groups 10001,10002 -o members.json
```

## Project Structure

```text
qq-group-overlap/
├── SPEC.md
├── README.md
├── examples/members.example.json
├── src/qq_group_overlap/
└── tests/
```

## Code Style

- QQ 号在内存中使用字符串，避免整数格式化和跨平台问题。
- 使用不可变 `dataclass` 表示群和成员。
- 统计逻辑与文件/网络 I/O 分离。

```python
@dataclass(frozen=True)
class Membership:
    group_id: str
    group_name: str
    user_id: str
    nickname: str
    card: str
    level: int | None
```

## Testing Strategy

- `unittest` 覆盖 JSON/CSV 读取、QQ 号去重、别名合并、最小共同群数、群对 Jaccard 重合度、排除用户和脱敏输出。
- OneBot 网络请求用 mock，测试不访问真实 QQ。
- 最后使用示例快照生成一次真实报告文件。

## Boundaries

- Always: 以 QQ 号判定是否同一人；原始快照和报告只写本地；支持排除用户自己和机器人；GUI 分页渲染，不向终端倾倒成员名单。
- Ask first: 增加自动定时采集、跨设备同步或任何外部上传。
- Never: 根据昵称将不同 QQ 号合并成同一人；自动私聊/加好友；将 Token 写入快照或报告。

## Success Criteria

- 同一 QQ 号在不同群使用不同群名片时，仍只输出一个成员记录，并保留所有别名。
- 默认只输出出现在至少 2 个群的成员，按当前评分公式降序，共同群数作为第一并列规则。
- 每对群都输出交集人数、并集人数、Jaccard 比例和双向覆盖率。
- `report.md`、`overlap_members.csv` 和 `group_pairs.csv` 使用 UTF-8 BOM CSV，可直接用表格软件打开。
- `--mask-ids` 会在所有报告文件中隐藏 QQ 号中间部分。
- GUI 将所有已选群对等处理，Ctrl/Shift 多选立即生效，搜索过滤不会丢失隐藏的已选群。
- 默认加权分为 `shared_groups + log_level_sum`，允许使用受限变量与数学函数改写公式；任意 Python 代码必须被拒绝。
- 结果无人数硬上限，界面分页显示，完整 CSV 仅在用户明确点击导出时生成。
- 无外部依赖，所有测试通过。

## Open Questions

- 实际要比较的群和要排除的本人 QQ 号，由使用者在运行时选择。
- 共同群多只代表兴趣圈层可能重合，报告不给人打性格或关系标签。
