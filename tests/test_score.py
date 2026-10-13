from __future__ import annotations

import math
import unittest

from qq_group_overlap.models import Membership
from qq_group_overlap.score import (
    DEFAULT_SCORE_FORMULA,
    rank_selected_groups,
    rank_target_group,
    summarize_groups,
)


class WeightedScoreTests(unittest.TestCase):
    def test_selected_groups_are_symmetric_without_a_target_group(self) -> None:
        rows = [
            Membership("a", "A 群", "1", "甲", level=2),
            Membership("b", "B 群", "1", "甲", level=2),
            Membership("b", "B 群", "2", "乙", level=3),
            Membership("c", "C 群", "2", "乙", level=3),
        ]

        ranked = rank_selected_groups(
            rows,
            selected_group_ids={"a", "b", "c"},
            min_groups=2,
        )

        self.assertEqual({person.user_id for person in ranked}, {"1", "2"})

    def test_custom_formula_uses_documented_aggregate_variables(self) -> None:
        rows = [
            Membership("a", "A 群", "1", "甲", level=2),
            Membership("b", "B 群", "1", "甲", level=3),
            Membership("a", "A 群", "2", "乙", level=8),
            Membership("b", "B 群", "2", "乙"),
        ]

        ranked = rank_selected_groups(
            rows,
            selected_group_ids={"a", "b"},
            score_formula="level_sum + known_levels * 10",
        )

        self.assertEqual([person.user_id for person in ranked], ["1", "2"])
        self.assertEqual([person.score for person in ranked], [25.0, 18.0])

    def test_default_formula_preserves_the_logarithmic_score(self) -> None:
        rows = [
            Membership("a", "A 群", "1", "甲", level=7),
            Membership("b", "B 群", "1", "甲", level=3),
        ]

        ranked = rank_selected_groups(
            rows,
            selected_group_ids={"a", "b"},
            score_formula=DEFAULT_SCORE_FORMULA,
        )

        self.assertAlmostEqual(ranked[0].score, 2 + math.log2(8) + math.log2(4))

    def test_custom_formula_rejects_python_code_execution(self) -> None:
        rows = [
            Membership("a", "A 群", "1", "甲"),
            Membership("b", "B 群", "1", "甲"),
        ]

        with self.assertRaisesRegex(ValueError, "公式"):
            rank_selected_groups(
                rows,
                selected_group_ids={"a", "b"},
                score_formula="__import__('os').system('id')",
            )

    def test_score_uses_a_group_baseline_plus_logarithmic_level_bonus(self) -> None:
        rows = [
            Membership("target", "目标群", "1", "甲", level=7),
            Membership("compare", "对照群", "1", "甲", level=3),
        ]

        ranked = rank_target_group(
            rows,
            target_group_id="target",
            comparison_group_ids={"compare"},
        )

        self.assertEqual(len(ranked), 1)
        self.assertAlmostEqual(ranked[0].score, (1 + math.log2(8)) + (1 + math.log2(4)))
        self.assertEqual(ranked[0].known_level_count, 2)

    def test_every_result_must_belong_to_the_target_group(self) -> None:
        rows = [
            Membership("target", "目标群", "1", "甲", level=2),
            Membership("a", "A 群", "1", "甲", level=2),
            Membership("a", "A 群", "2", "乙", level=20),
            Membership("b", "B 群", "2", "乙", level=20),
        ]

        ranked = rank_target_group(
            rows,
            target_group_id="target",
            comparison_group_ids={"a", "b"},
        )

        self.assertEqual([person.user_id for person in ranked], ["1"])

    def test_missing_level_keeps_the_group_baseline_and_is_reported(self) -> None:
        rows = [
            Membership("target", "目标群", "1", "甲"),
            Membership("compare", "对照群", "1", "甲", level=3),
        ]

        ranked = rank_target_group(
            rows,
            target_group_id="target",
            comparison_group_ids={"compare"},
        )

        self.assertAlmostEqual(ranked[0].score, 1 + (1 + math.log2(4)))
        self.assertEqual(ranked[0].known_level_count, 1)
        self.assertEqual(ranked[0].shared_group_count, 2)

    def test_requires_a_real_target_and_at_least_one_comparison_group(self) -> None:
        rows = [Membership("target", "目标群", "1")]
        with self.assertRaisesRegex(ValueError, "对照群"):
            rank_target_group(rows, target_group_id="target", comparison_group_ids=set())
        with self.assertRaisesRegex(ValueError, "目标群"):
            rank_target_group(
                rows,
                target_group_id="missing",
                comparison_group_ids={"target"},
            )

    def test_group_summary_reports_level_coverage_without_member_names(self) -> None:
        rows = [
            Membership("g", "自动化学院", "1", level=3),
            Membership("g", "自动化学院", "2"),
        ]

        summaries = summarize_groups(rows)

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].member_count, 2)
        self.assertEqual(summaries[0].level_count, 1)
        self.assertAlmostEqual(summaries[0].level_coverage, 0.5)


if __name__ == "__main__":
    unittest.main()
