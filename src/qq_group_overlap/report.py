from __future__ import annotations

import csv
from pathlib import Path

from .models import AnalysisResult


def mask_user_id(user_id: str) -> str:
    if len(user_id) <= 4:
        return "*" * len(user_id)
    visible = 3 if len(user_id) >= 7 else 2
    return user_id[:visible] + "*" * (len(user_id) - visible * 2) + user_id[-visible:]


def _shown_id(user_id: str, mask_ids: bool) -> str:
    return mask_user_id(user_id) if mask_ids else user_id


def _markdown_cell(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def write_reports(
    result: AnalysisResult,
    output_directory: str | Path,
    *,
    mask_ids: bool = False,
    markdown_limit: int = 100,
) -> tuple[Path, Path, Path]:
    output = Path(output_directory).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "report.md"
    people_path = output / "overlap_members.csv"
    pairs_path = output / "group_pairs.csv"

    with people_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["QQ号", "常用昵称", "共同群数", "所在群", "出现过的昵称/群名片"])
        for person in result.people:
            writer.writerow(
                [
                    _shown_id(person.user_id, mask_ids),
                    person.display_name,
                    person.group_count,
                    " | ".join(person.group_names),
                    " | ".join(person.aliases),
                ]
            )

    with pairs_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "群A",
                "群A人数",
                "群B",
                "群B人数",
                "交集人数",
                "并集人数",
                "Jaccard重合率",
                "交集占群A",
                "交集占群B",
            ]
        )
        for pair in result.pairs:
            writer.writerow(
                [
                    pair.group_a_name,
                    pair.group_a_size,
                    pair.group_b_name,
                    pair.group_b_size,
                    pair.common_count,
                    pair.union_count,
                    f"{pair.jaccard:.2%}",
                    f"{pair.coverage_a:.2%}",
                    f"{pair.coverage_b:.2%}",
                ]
            )

    lines = [
        "# QQ 群重合成员报告",
        "",
        f"- 已分析群：{len(result.group_names)} 个",
        f"- 去重后成员：{result.unique_people_count} 人",
        f"- 出现在多个群的成员：{len(result.people)} 人",
        "",
        "## 重复成员排行",
        "",
        "| # | QQ号 | 常用昵称 | 共同群 | 所在群 | 其他名片 |",
        "|---:|---|---|---:|---|---|",
    ]
    for index, person in enumerate(result.people[:markdown_limit], start=1):
        aliases = _markdown_cell(" / ".join(person.aliases))
        groups = _markdown_cell(" / ".join(person.group_names))
        lines.append(
            f"| {index} | {_shown_id(person.user_id, mask_ids)} | {_markdown_cell(person.display_name)} | "
            f"{person.group_count} | {groups} | {aliases} |"
        )
    if not result.people:
        lines.append("| - | - | 没有找到符合条件的重复成员 | - | - | - |")

    lines.extend(
        [
            "",
            "## 群与群的重合度",
            "",
            "Jaccard = 交集人数 ÷ 并集人数。数值越高，两个群的成员结构越相似。",
            "",
            "| 群A | 群B | 交集 | Jaccard | 占群A | 占群B |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for pair in result.pairs:
        lines.append(
            f"| {_markdown_cell(pair.group_a_name)} | {_markdown_cell(pair.group_b_name)} | {pair.common_count} | "
            f"{pair.jaccard:.2%} | {pair.coverage_a:.2%} | {pair.coverage_b:.2%} |"
        )
    lines.extend(
        [
            "",
            "> 共同群只是兴趣圈层重合的线索，不等于对方一定与你兴趣相同。",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path, people_path, pairs_path
