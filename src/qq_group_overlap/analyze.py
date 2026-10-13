from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from .models import AnalysisResult, GroupPairOverlap, Membership, PersonOverlap


def _preferred_name(memberships: list[Membership]) -> str:
    candidates = [item.nickname.strip() for item in memberships if item.nickname.strip()]
    if not candidates:
        candidates = [item.card.strip() for item in memberships if item.card.strip()]
    if not candidates:
        return memberships[0].user_id
    counts = Counter(candidates)
    return sorted(counts, key=lambda name: (-counts[name], name.casefold()))[0]


def analyze_memberships(
    memberships: list[Membership],
    *,
    selected_groups: set[str] | None = None,
    excluded_users: set[str] | None = None,
    min_groups: int = 2,
    include_bots: bool = False,
) -> AnalysisResult:
    if min_groups < 2:
        raise ValueError("min_groups 不能小于 2")

    available_groups = {membership.group_id for membership in memberships}
    if selected_groups is not None:
        missing_groups = selected_groups - available_groups
        if missing_groups:
            raise ValueError("找不到这些群：" + "、".join(sorted(missing_groups)))
        active_groups = selected_groups
    else:
        active_groups = available_groups
    if len(active_groups) < 2:
        raise ValueError("至少需要 2 个群才能分析重合成员")

    excluded_users = excluded_users or set()

    deduplicated: dict[tuple[str, str], Membership] = {}
    for membership in memberships:
        if selected_groups is not None and membership.group_id not in selected_groups:
            continue
        if membership.user_id in excluded_users:
            continue
        if membership.is_robot and not include_bots:
            continue
        key = (membership.group_id, membership.user_id)
        previous = deduplicated.get(key)
        if previous is None or (not previous.card and membership.card):
            deduplicated[key] = membership

    filtered = tuple(
        sorted(deduplicated.values(), key=lambda item: (item.group_id, item.user_id))
    )
    group_names: dict[str, str] = {}
    group_members: dict[str, set[str]] = defaultdict(set)
    by_user: dict[str, list[Membership]] = defaultdict(list)
    for membership in filtered:
        group_names[membership.group_id] = membership.group_name
        group_members[membership.group_id].add(membership.user_id)
        by_user[membership.user_id].append(membership)

    people: list[PersonOverlap] = []
    for user_id, rows in by_user.items():
        group_ids = tuple(sorted({row.group_id for row in rows}, key=lambda gid: (group_names[gid], gid)))
        if len(group_ids) < min_groups:
            continue
        aliases = tuple(sorted({row.alias for row in rows if row.alias and row.alias != user_id}, key=str.casefold))
        people.append(
            PersonOverlap(
                user_id=user_id,
                display_name=_preferred_name(rows),
                group_ids=group_ids,
                group_names=tuple(group_names[group_id] for group_id in group_ids),
                aliases=aliases,
            )
        )
    people.sort(key=lambda person: (-person.group_count, person.display_name.casefold(), person.user_id))

    pairs: list[GroupPairOverlap] = []
    group_ids = sorted(group_members, key=lambda gid: (group_names[gid], gid))
    for group_a, group_b in combinations(group_ids, 2):
        members_a = group_members[group_a]
        members_b = group_members[group_b]
        common_count = len(members_a & members_b)
        union_count = len(members_a | members_b)
        pairs.append(
            GroupPairOverlap(
                group_a_id=group_a,
                group_a_name=group_names[group_a],
                group_a_size=len(members_a),
                group_b_id=group_b,
                group_b_name=group_names[group_b],
                group_b_size=len(members_b),
                common_count=common_count,
                union_count=union_count,
                jaccard=common_count / union_count if union_count else 0.0,
                coverage_a=common_count / len(members_a) if members_a else 0.0,
                coverage_b=common_count / len(members_b) if members_b else 0.0,
            )
        )
    pairs.sort(key=lambda pair: (-pair.common_count, -pair.jaccard, pair.group_a_name, pair.group_b_name))

    return AnalysisResult(
        memberships=filtered,
        people=tuple(people),
        pairs=tuple(pairs),
        group_names=group_names,
        group_sizes={group_id: len(users) for group_id, users in group_members.items()},
        unique_people_count=len(by_user),
    )
