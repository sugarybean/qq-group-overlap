from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .models import Membership


class InputError(ValueError):
    """Raised when an input snapshot is missing required fields."""


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _group_level(value: object) -> int | None:
    text = _text(value)
    if not text:
        return None
    try:
        level = int(text)
    except (TypeError, ValueError):
        return None
    return level if level >= 0 else None


def _membership_from_row(row: dict[str, Any], defaults: dict[str, str] | None = None) -> Membership:
    defaults = defaults or {}
    group_id = _text(row.get("group_id") or defaults.get("group_id"))
    user_id = _text(row.get("user_id") or row.get("qq") or row.get("uin"))
    if not group_id or not user_id:
        raise InputError("每条成员记录都必须包含 group_id 和 user_id")
    robot_value = row.get("is_robot", False)
    is_robot = robot_value is True or _text(robot_value).lower() in {"1", "true", "yes", "y"}
    return Membership(
        group_id=group_id,
        group_name=_text(row.get("group_name") or defaults.get("group_name")) or f"QQ群 {group_id}",
        user_id=user_id,
        nickname=_text(row.get("nickname") or row.get("nick")),
        card=_text(row.get("card") or row.get("card_name")),
        role=_text(row.get("role")) or "member",
        is_robot=is_robot,
        level=_group_level(row.get("level")),
    )


def load_json(path: Path) -> list[Membership]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"无法读取 JSON：{exc}") from exc

    memberships: list[Membership] = []
    if isinstance(data, dict) and isinstance(data.get("groups"), list):
        for group in data["groups"]:
            if not isinstance(group, dict):
                raise InputError("groups 里的每项必须是对象")
            group_id = _text(group.get("group_id"))
            group_name = _text(group.get("group_name")) or f"QQ群 {group_id}"
            members = group.get("members", [])
            if not group_id or not isinstance(members, list):
                raise InputError("每个群必须包含 group_id 和 members 数组")
            for member in members:
                if not isinstance(member, dict):
                    raise InputError("members 里的每项必须是对象")
                memberships.append(
                    _membership_from_row(member, {"group_id": group_id, "group_name": group_name})
                )
        return memberships

    rows = data.get("memberships") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise InputError("JSON 必须是 groups 快照或成员记录数组")
    for row in rows:
        if not isinstance(row, dict):
            raise InputError("成员记录必须是对象")
        memberships.append(_membership_from_row(row))
    return memberships


def load_csv(path: Path) -> list[Membership]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise InputError(f"无法读取 CSV：{exc}") from exc
    if not rows:
        raise InputError("CSV 里没有成员数据")
    return [_membership_from_row(row) for row in rows]


def load_memberships(path: str | Path) -> list[Membership]:
    source = Path(path).expanduser().resolve()
    if not source.exists():
        raise InputError(f"找不到输入文件：{source}")
    if source.suffix.lower() == ".json":
        return load_json(source)
    if source.suffix.lower() == ".csv":
        return load_csv(source)
    raise InputError("只支持 .json 或 .csv 输入")


def save_snapshot(path: str | Path, groups: list[dict[str, Any]]) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"format": "qq-group-overlap/v1", "groups": groups}
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def merge_snapshot_groups(
    path: str | Path, replacements: list[dict[str, Any]]
) -> Path:
    """Replace fetched groups in a snapshot while preserving every other group."""
    target = Path(path).expanduser().resolve()
    existing_groups: list[dict[str, Any]] = []
    if target.exists():
        try:
            payload = json.loads(target.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InputError(f"无法读取现有快照：{exc}") from exc
        raw_groups = payload.get("groups") if isinstance(payload, dict) else None
        if not isinstance(raw_groups, list) or not all(
            isinstance(group, dict) for group in raw_groups
        ):
            raise InputError("现有快照不是有效的 groups 格式")
        existing_groups = raw_groups

    replacement_by_id: dict[str, dict[str, Any]] = {}
    for group in replacements:
        group_id = _text(group.get("group_id"))
        if not group_id or not isinstance(group.get("members"), list):
            raise InputError("刷新结果中的群缺少 group_id 或 members")
        replacement_by_id[group_id] = group

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in existing_groups:
        group_id = _text(group.get("group_id"))
        if group_id in replacement_by_id:
            merged.append(replacement_by_id[group_id])
            seen.add(group_id)
        else:
            merged.append(group)
    for group_id, group in replacement_by_id.items():
        if group_id not in seen:
            merged.append(group)
    return save_snapshot(target, merged)
