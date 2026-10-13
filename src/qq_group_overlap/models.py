from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Membership:
    group_id: str
    group_name: str
    user_id: str
    nickname: str = ""
    card: str = ""
    role: str = "member"
    is_robot: bool = False
    level: int | None = None

    @property
    def alias(self) -> str:
        return self.card.strip() or self.nickname.strip() or self.user_id


@dataclass(frozen=True)
class PersonOverlap:
    user_id: str
    display_name: str
    group_ids: tuple[str, ...]
    group_names: tuple[str, ...]
    aliases: tuple[str, ...]

    @property
    def group_count(self) -> int:
        return len(self.group_ids)


@dataclass(frozen=True)
class GroupPairOverlap:
    group_a_id: str
    group_a_name: str
    group_a_size: int
    group_b_id: str
    group_b_name: str
    group_b_size: int
    common_count: int
    union_count: int
    jaccard: float
    coverage_a: float
    coverage_b: float


@dataclass(frozen=True)
class AnalysisResult:
    memberships: tuple[Membership, ...]
    people: tuple[PersonOverlap, ...]
    pairs: tuple[GroupPairOverlap, ...]
    group_names: dict[str, str]
    group_sizes: dict[str, int]
    unique_people_count: int
