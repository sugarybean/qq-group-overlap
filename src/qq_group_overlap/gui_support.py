from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TypeVar

from .score import GroupSummary, WeightedOverlap


T = TypeVar("T")


def filter_group_summaries(
    groups: list[GroupSummary], query: str
) -> list[GroupSummary]:
    needle = query.strip().casefold()
    if not needle:
        return list(groups)
    return [
        group
        for group in groups
        if needle in group.group_name.casefold() or needle in group.group_id.casefold()
    ]


def format_level_summary(levels: tuple[tuple[str, int | None], ...]) -> str:
    return " / ".join(
        f"{group_name}:L{level}" if level is not None else f"{group_name}:缺失"
        for group_name, level in levels
    )


def update_group_selection(
    selected_group_ids: set[str],
    *,
    visible_group_ids: set[str],
    selected_visible_group_ids: set[str],
) -> set[str]:
    return (set(selected_group_ids) - visible_group_ids) | selected_visible_group_ids


def page_items(
    items: list[T], *, page_index: int, page_size: int
) -> tuple[list[T], int, int]:
    if page_size < 1:
        raise ValueError("每页数量必须大于 0")
    total_pages = max(1, math.ceil(len(items) / page_size))
    bounded_index = min(max(page_index, 0), total_pages - 1)
    start = bounded_index * page_size
    return items[start : start + page_size], start, total_pages


def write_top_csv(
    path: str | Path,
    ranked: list[WeightedOverlap],
    *,
    limit: int | None,
) -> Path:
    if limit is not None and limit < 1:
        raise ValueError("导出数量必须大于 0")
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            ["排名", "QQ号", "昵称", "加权分", "共同群数", "等级覆盖", "等级明细"]
        )
        people = ranked if limit is None else ranked[:limit]
        for index, person in enumerate(people, start=1):
            writer.writerow(
                [
                    index,
                    person.user_id,
                    person.display_name,
                    f"{person.score:.3f}",
                    person.shared_group_count,
                    f"{person.known_level_count}/{person.shared_group_count}",
                    format_level_summary(person.levels),
                ]
            )
    return target
