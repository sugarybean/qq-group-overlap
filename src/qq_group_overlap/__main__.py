from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyze import analyze_memberships
from .io import InputError, load_memberships, save_snapshot
from .onebot import OneBotClient, OneBotError
from .paths import default_snapshot_path
from .report import write_reports


def _ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def resolve_group_selection(
    groups: list[dict[str, object]], selection: str
) -> list[str]:
    if selection.strip().casefold() in {"all", "全部"}:
        selected_all = [str(group["group_id"]) for group in groups]
        if len(selected_all) < 2:
            raise InputError("至少选择 2 个群才能分析重合成员")
        return selected_all

    by_id = {str(group["group_id"]): str(group["group_id"]) for group in groups}
    selected: list[str] = []
    unknown: list[str] = []
    for token in _ids(selection):
        if token in by_id:
            group_id = by_id[token]
        elif token.isdigit() and 1 <= int(token) <= len(groups):
            group_id = str(groups[int(token) - 1]["group_id"])
        else:
            unknown.append(token)
            continue
        if group_id not in selected:
            selected.append(group_id)
    if unknown:
        raise InputError("无法识别这些群序号或群号：" + "、".join(unknown))
    if len(selected) < 2:
        raise InputError("至少选择 2 个群才能分析重合成员")
    return selected


def _add_connection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api", default="http://127.0.0.1:3000", help="OneBot HTTP 地址")
    parser.add_argument("--token-env", default="ONEBOT_ACCESS_TOKEN", help="保存 Token 的环境变量名")
    parser.add_argument("--timeout", type=float, default=15, help="每个 HTTP 请求的超时秒数")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qq-group-overlap",
        description="找出同时出现在多个 QQ 群的成员。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="分析本地 JSON/CSV 成员快照")
    analyze.add_argument("input", help=".json 或 .csv 成员文件")
    analyze.add_argument("-o", "--output", default="report", help="报告输出目录")
    analyze.add_argument("--groups", default="", help="只分析这些群号，逗号分隔")
    analyze.add_argument("--exclude-users", default="", help="排除的 QQ 号，逗号分隔")
    analyze.add_argument("--min-groups", type=int, default=2, help="最少共同群数，默认 2")
    analyze.add_argument("--include-bots", action="store_true", help="不过滤机器人账号")
    analyze.add_argument("--mask-ids", action="store_true", help="报告中隐藏 QQ 号中间部分")
    analyze.add_argument("--limit", type=int, default=100, help="Markdown 报告最多展示的成员数")

    fetch = subparsers.add_parser("fetch", help="从 OneBot HTTP 拉取选定群的成员快照")
    _add_connection_arguments(fetch)
    fetch.add_argument("--groups", required=True, help="要获取的群号，逗号分隔")
    fetch.add_argument("-o", "--output", default="members.private.json", help="快照输出文件")

    live = subparsers.add_parser("live", help="连接 QQ，选群并直接生成报告")
    _add_connection_arguments(live)
    live.add_argument("--groups", default="", help="群序号、群号或 all；留空则交互选择")
    live.add_argument("--self-id", default="", help="从结果排除的自己 QQ 号；默认自动读取")
    live.add_argument(
        "--snapshot",
        default=str(default_snapshot_path()),
        help="成员快照保存路径（默认在当前用户数据目录，与运行目录无关）",
    )
    live.add_argument("-o", "--output", default="report", help="报告输出目录")
    live.add_argument("--min-groups", type=int, default=2, help="最少共同群数，默认 2")
    live.add_argument("--include-bots", action="store_true", help="不过滤机器人账号")
    live.add_argument("--mask-ids", action="store_true", help="报告中隐藏 QQ 号中间部分")
    live.add_argument("--limit", type=int, default=100, help="Markdown 报告最多展示的成员数")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "live":
            client = OneBotClient.from_environment(args.api, args.token_env, args.timeout)
            self_id = args.self_id or client.get_login_user_id()
            print(f"当前登录 QQ：{self_id}（将自动从重合结果中排除）")
            available = client.list_groups()
            if len(available) < 2:
                raise InputError("当前账号可见的 QQ 群少于 2 个")
            print("可选 QQ 群：")
            for index, group in enumerate(available, start=1):
                member_count = group.get("member_count", 0)
                print(
                    f"  [{index}] {group['group_name']} "
                    f"(群号 {group['group_id']}，{member_count} 人)"
                )
            selection = args.groups or input("请输入群序号、群号（逗号分隔）或 all：").strip()
            group_ids = resolve_group_selection(available, selection)
            snapshot = save_snapshot(args.snapshot, client.fetch_groups(group_ids))
            memberships = load_memberships(snapshot)
            excluded_users = {self_id}
            result = analyze_memberships(
                memberships,
                excluded_users=excluded_users,
                min_groups=args.min_groups,
                include_bots=args.include_bots,
            )
            report, people, pairs = write_reports(
                result,
                args.output,
                mask_ids=args.mask_ids,
                markdown_limit=max(1, args.limit),
            )
            print(
                f"已分析 {len(result.group_names)} 个群、{result.unique_people_count} 个成员；"
                f"找到 {len(result.people)} 个重复成员。"
            )
            print(f"Markdown：{report}")
            print(f"成员 CSV：{people}")
            print(f"群重合 CSV：{pairs}")
            return 0

        if args.command == "fetch":
            group_ids = _ids(args.groups)
            if len(group_ids) < 2:
                raise InputError("至少选择 2 个群才能分析重合成员")
            client = OneBotClient.from_environment(args.api, args.token_env, args.timeout)
            target = save_snapshot(args.output, client.fetch_groups(group_ids))
            print(f"已保存 {len(group_ids)} 个群的成员快照：{target}")
            return 0

        input_path = Path(args.input).expanduser()
        if not input_path.exists():
            raise InputError(
                f"找不到输入文件：{input_path}\n"
                "这个路径通常是成员快照。请先生成它：\n"
                "  · 从 NapCat 拉取：python -m qq_group_overlap fetch --groups 群号1,群号2 -o 快照.json\n"
                "  · 或用本机一键模式：python -m qq_group_overlap live\n"
                "  · 也可以先用示例数据试试：python -m qq_group_overlap analyze examples/members.example.json -o report"
            )
        memberships = load_memberships(args.input)
        selected_groups = set(_ids(args.groups)) or None
        result = analyze_memberships(
            memberships,
            selected_groups=selected_groups,
            excluded_users=set(_ids(args.exclude_users)),
            min_groups=args.min_groups,
            include_bots=args.include_bots,
        )
        report, people, pairs = write_reports(
            result,
            args.output,
            mask_ids=args.mask_ids,
            markdown_limit=max(1, args.limit),
        )
        print(
            f"已分析 {len(result.group_names)} 个群、{result.unique_people_count} 个成员；"
            f"找到 {len(result.people)} 个重复成员。"
        )
        print(f"Markdown：{report}")
        print(f"成员 CSV：{people}")
        print(f"群重合 CSV：{pairs}")
        return 0
    except (InputError, OneBotError, ValueError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
