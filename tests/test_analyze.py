from __future__ import annotations

import unittest

from qq_group_overlap.analyze import analyze_memberships
from qq_group_overlap.models import Membership


def sample_memberships() -> list[Membership]:
    return [
        Membership("g1", "摄影社", "1", "小明", "风光明"),
        Membership("g2", "徒步群", "1", "小明", "明天爬山"),
        Membership("g3", "胶片群", "1", "小明", "Ming"),
        Membership("g1", "摄影社", "2", "阿青", "青山"),
        Membership("g2", "徒步群", "2", "阿青", ""),
        Membership("g1", "摄影社", "3", "只在一群", ""),
        Membership("g2", "徒步群", "4", "机器人", "", is_robot=True),
        Membership("g3", "胶片群", "4", "机器人", "", is_robot=True),
    ]


class AnalyzeTests(unittest.TestCase):
    def test_same_qq_is_merged_across_groups_and_aliases_are_preserved(self) -> None:
        result = analyze_memberships(sample_memberships())
        self.assertEqual([person.user_id for person in result.people], ["1", "2"])
        first = result.people[0]
        self.assertEqual(first.group_count, 3)
        self.assertEqual(first.display_name, "小明")
        self.assertEqual(set(first.aliases), {"风光明", "明天爬山", "Ming"})

    def test_bots_are_excluded_by_default(self) -> None:
        result = analyze_memberships(sample_memberships())
        self.assertNotIn("4", {person.user_id for person in result.people})
        included = analyze_memberships(sample_memberships(), include_bots=True)
        self.assertIn("4", {person.user_id for person in included.people})

    def test_selected_groups_and_excluded_users_are_applied(self) -> None:
        result = analyze_memberships(
            sample_memberships(), selected_groups={"g1", "g2"}, excluded_users={"2"}
        )
        self.assertEqual([person.user_id for person in result.people], ["1"])
        self.assertEqual(set(person_group_ids(result, "1")), {"g1", "g2"})

    def test_group_pair_metrics_are_correct(self) -> None:
        result = analyze_memberships(sample_memberships())
        pair = next(
            item for item in result.pairs if {item.group_a_id, item.group_b_id} == {"g1", "g2"}
        )
        self.assertEqual(pair.common_count, 2)
        self.assertEqual(pair.union_count, 3)
        self.assertAlmostEqual(pair.jaccard, 2 / 3)
        coverage_by_group = {
            pair.group_a_id: pair.coverage_a,
            pair.group_b_id: pair.coverage_b,
        }
        self.assertAlmostEqual(coverage_by_group["g1"], 2 / 3)
        self.assertEqual(coverage_by_group["g2"], 1.0)

    def test_duplicate_row_inside_one_group_counts_once_and_keeps_card(self) -> None:
        rows = sample_memberships() + [Membership("g1", "摄影社", "2", "阿青", "更新名片")]
        result = analyze_memberships(rows)
        self.assertEqual(result.group_sizes["g1"], 3)
        person = next(item for item in result.people if item.user_id == "2")
        self.assertIn("青山", person.aliases)

    def test_rejects_unknown_selected_group(self) -> None:
        with self.assertRaisesRegex(ValueError, "找不到这些群"):
            analyze_memberships(sample_memberships(), selected_groups={"g1", "missing"})

    def test_rejects_analysis_with_only_one_group(self) -> None:
        with self.assertRaisesRegex(ValueError, "至少需要 2 个群"):
            analyze_memberships(sample_memberships(), selected_groups={"g1"})


def person_group_ids(result, user_id: str) -> tuple[str, ...]:
    return next(person.group_ids for person in result.people if person.user_id == user_id)


if __name__ == "__main__":
    unittest.main()
