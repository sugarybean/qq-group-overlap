from __future__ import annotations

import ast
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from .analyze import analyze_memberships
from .models import Membership


DEFAULT_SCORE_FORMULA = "shared_groups + log_level_sum"
SCORE_FORMULA_PRESETS = {
    "对数等级（默认）": DEFAULT_SCORE_FORMULA,
    "只看共同群": "shared_groups",
    "线性等级": "shared_groups + level_sum",
}
SCORE_FORMULA_VARIABLES = (
    "shared_groups",
    "known_levels",
    "missing_levels",
    "level_sum",
    "level_avg",
    "level_max",
    "log_level_sum",
)

_FORMULA_FUNCTIONS: dict[str, Callable[..., float]] = {
    "abs": abs,
    "log2": math.log2,
    "max": max,
    "min": min,
    "sqrt": math.sqrt,
}
_FORMULA_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
_FORMULA_UNARYOPS = (ast.UAdd, ast.USub)


@dataclass(frozen=True)
class GroupSummary:
    group_id: str
    group_name: str
    member_count: int
    level_count: int

    @property
    def level_coverage(self) -> float:
        return self.level_count / self.member_count if self.member_count else 0.0


@dataclass(frozen=True)
class WeightedOverlap:
    user_id: str
    display_name: str
    score: float
    shared_group_ids: tuple[str, ...]
    shared_group_names: tuple[str, ...]
    levels: tuple[tuple[str, int | None], ...]
    level_aliases: tuple[tuple[str, str], ...]
    known_level_count: int

    @property
    def shared_group_count(self) -> int:
        return len(self.shared_group_ids)

    @property
    def level_coverage(self) -> float:
        return (
            self.known_level_count / self.shared_group_count
            if self.shared_group_count
            else 0.0
        )


def summarize_groups(memberships: list[Membership]) -> list[GroupSummary]:
    members: dict[str, set[str]] = defaultdict(set)
    with_level: dict[str, set[str]] = defaultdict(set)
    names: dict[str, str] = {}
    for row in memberships:
        names[row.group_id] = row.group_name
        members[row.group_id].add(row.user_id)
        if row.level is not None:
            with_level[row.group_id].add(row.user_id)
    return sorted(
        (
            GroupSummary(
                group_id=group_id,
                group_name=names[group_id],
                member_count=len(user_ids),
                level_count=len(with_level[group_id]),
            )
            for group_id, user_ids in members.items()
        ),
        key=lambda group: (group.group_name.casefold(), group.group_id),
    )


def logarithmic_membership_score(level: int | None) -> float:
    """Give every shared group one point, then add a diminishing level bonus."""
    return 1.0 + (math.log2(1 + level) if level is not None else 0.0)


def _validate_formula_node(node: ast.AST) -> None:
    if isinstance(node, ast.Expression):
        _validate_formula_node(node.body)
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _FORMULA_BINOPS):
            raise ValueError("公式只允许 +、-、*、/ 运算")
        _validate_formula_node(node.left)
        _validate_formula_node(node.right)
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _FORMULA_UNARYOPS):
            raise ValueError("公式只允许正负号")
        _validate_formula_node(node.operand)
        return
    if isinstance(node, ast.Call):
        if (
            not isinstance(node.func, ast.Name)
            or node.func.id not in _FORMULA_FUNCTIONS
            or node.keywords
        ):
            raise ValueError("公式包含不允许的函数调用")
        if not 1 <= len(node.args) <= 4:
            raise ValueError("公式函数需要 1–4 个参数")
        for argument in node.args:
            _validate_formula_node(argument)
        return
    if isinstance(node, ast.Name):
        allowed = {*SCORE_FORMULA_VARIABLES, *_FORMULA_FUNCTIONS}
        if node.id not in allowed:
            raise ValueError(f"公式包含未知变量：{node.id}")
        return
    if isinstance(node, ast.Constant):
        if (
            isinstance(node.value, bool)
            or not isinstance(node.value, (int, float))
            or not math.isfinite(float(node.value))
            or abs(float(node.value)) > 1_000_000
        ):
            raise ValueError("公式常量必须是有限数字，绝对值不超过 1000000")
        return
    raise ValueError("公式包含不允许的语法")


def compile_score_formula(expression: str) -> Callable[[list[Membership]], float]:
    formula = expression.strip()
    if not formula:
        raise ValueError("评分公式不能为空")
    if len(formula) > 256:
        raise ValueError("评分公式不能超过 256 个字符")
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        raise ValueError("评分公式语法错误") from exc
    if sum(1 for _node in ast.walk(tree)) > 64:
        raise ValueError("评分公式过于复杂")
    _validate_formula_node(tree)
    compiled = compile(tree, "<score-formula>", "eval")

    def evaluate(rows: list[Membership]) -> float:
        levels = [row.level for row in rows if row.level is not None]
        shared_groups = len(rows)
        known_levels = len(levels)
        values: dict[str, float] = {
            "shared_groups": float(shared_groups),
            "known_levels": float(known_levels),
            "missing_levels": float(shared_groups - known_levels),
            "level_sum": float(sum(levels)),
            "level_avg": float(sum(levels) / known_levels) if known_levels else 0.0,
            "level_max": float(max(levels)) if levels else 0.0,
            "log_level_sum": float(sum(math.log2(1 + level) for level in levels)),
        }
        try:
            result = eval(
                compiled,
                {"__builtins__": {}},
                {**_FORMULA_FUNCTIONS, **values},
            )
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise ValueError(f"评分公式无法计算：{exc}") from exc
        if isinstance(result, bool) or not isinstance(result, (int, float)):
            raise ValueError("评分公式必须得到一个数字")
        score = float(result)
        if not math.isfinite(score) or abs(score) > 1_000_000_000_000:
            raise ValueError("评分公式结果必须是有限数字，绝对值不能过大")
        return score

    return evaluate


def rank_selected_groups(
    memberships: list[Membership],
    *,
    selected_group_ids: set[str],
    min_groups: int = 2,
    excluded_users: set[str] | None = None,
    include_bots: bool = False,
    score_formula: str = DEFAULT_SCORE_FORMULA,
    required_group_ids: set[str] | None = None,
) -> list[WeightedOverlap]:
    selected_group_ids = set(selected_group_ids)
    required_group_ids = set(required_group_ids or ())
    if len(selected_group_ids) < 2:
        raise ValueError("至少选择 2 个群")
    if not 2 <= min_groups <= len(selected_group_ids):
        raise ValueError(f"最少共同群应在 2–{len(selected_group_ids)} 之间")
    if not required_group_ids.issubset(selected_group_ids):
        raise ValueError("特别关照群必须是已选择的群")

    evaluate_score = compile_score_formula(score_formula)
    result = analyze_memberships(
        memberships,
        selected_groups=selected_group_ids,
        excluded_users=excluded_users,
        min_groups=min_groups,
        include_bots=include_bots,
    )
    rows_by_user: dict[str, list[Membership]] = defaultdict(list)
    for row in result.memberships:
        rows_by_user[row.user_id].append(row)

    ranked: list[WeightedOverlap] = []
    for person in result.people:
        if not required_group_ids.issubset(person.group_ids):
            continue
        rows = sorted(
            rows_by_user[person.user_id],
            key=lambda row: (row.group_name.casefold(), row.group_id),
        )
        ranked.append(
            WeightedOverlap(
                user_id=person.user_id,
                display_name=person.display_name,
                score=evaluate_score(rows),
                shared_group_ids=tuple(row.group_id for row in rows),
                shared_group_names=tuple(row.group_name for row in rows),
                levels=tuple((row.group_name, row.level) for row in rows),
                level_aliases=tuple(
                    (row.group_name, row.alias) for row in rows
                ),
                known_level_count=sum(row.level is not None for row in rows),
            )
        )
    ranked.sort(
        key=lambda person: (
            -person.score,
            -person.shared_group_count,
            person.display_name.casefold(),
            person.user_id,
        )
    )
    return ranked


def rank_target_group(
    memberships: list[Membership],
    *,
    target_group_id: str,
    comparison_group_ids: set[str],
    min_groups: int = 2,
    excluded_users: set[str] | None = None,
    include_bots: bool = False,
) -> list[WeightedOverlap]:
    if not comparison_group_ids:
        raise ValueError("至少选择 1 个对照群")
    comparison_group_ids = set(comparison_group_ids) - {target_group_id}
    if not comparison_group_ids:
        raise ValueError("对照群不能与目标群相同")
    available = {row.group_id for row in memberships}
    if target_group_id not in available:
        raise ValueError("找不到目标群")
    if min_groups < 2:
        raise ValueError("最少共同群数不能小于 2")

    selected_groups = {target_group_id, *comparison_group_ids}
    ranked = rank_selected_groups(
        memberships,
        selected_group_ids=selected_groups,
        excluded_users=excluded_users,
        min_groups=min_groups,
        include_bots=include_bots,
    )
    return [person for person in ranked if target_group_id in person.shared_group_ids]
