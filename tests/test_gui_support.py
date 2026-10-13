from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qq_group_overlap.gui_support import (
    filter_group_summaries,
    format_level_summary,
    page_items,
    update_group_selection,
    write_top_csv,
)
from qq_group_overlap.score import GroupSummary, WeightedOverlap


def ranked_person(user_id: str, name: str) -> WeightedOverlap:
    return WeightedOverlap(
        user_id=user_id,
        display_name=name,
        score=4.0,
        shared_group_ids=("a", "b"),
        shared_group_names=("A", "B"),
        levels=(("A", 3), ("B", None)),
        known_level_count=1,
    )


class GuiSupportTests(unittest.TestCase):
    def test_filters_groups_by_name_or_id(self) -> None:
        groups = [
            GroupSummary("100", "自动化学院", 20, 10),
            GroupSummary("200", "摄影社", 10, 8),
        ]
        self.assertEqual(
            [group.group_id for group in filter_group_summaries(groups, "自动")],
            ["100"],
        )
        self.assertEqual(
            [group.group_id for group in filter_group_summaries(groups, "200")],
            ["200"],
        )

    def test_formats_missing_levels_explicitly(self) -> None:
        self.assertEqual(format_level_summary((("A", 3), ("B", None))), "A:L3 / B:缺失")

    def test_export_never_writes_beyond_the_requested_top_n(self) -> None:
        rows = [
            ranked_person("111", "甲"),
            ranked_person("222", "乙"),
            ranked_person("333", "丙"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "top.csv"
            write_top_csv(target, rows, limit=2)
            text = target.read_text(encoding="utf-8-sig")
        self.assertIn("111", text)
        self.assertIn("222", text)
        self.assertNotIn("333", text)

    def test_export_without_limit_writes_every_result(self) -> None:
        rows = [ranked_person(str(index), f"成员{index}") for index in range(150)]
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "all.csv"
            write_top_csv(target, rows, limit=None)
            text = target.read_text(encoding="utf-8-sig")
        self.assertIn("成员149", text)

    def test_pages_make_results_after_the_first_hundred_reachable(self) -> None:
        rows = [ranked_person(str(index), f"成员{index}") for index in range(205)]

        page, start, total_pages = page_items(rows, page_index=2, page_size=100)

        self.assertEqual(len(page), 5)
        self.assertEqual(start, 200)
        self.assertEqual(total_pages, 3)
        self.assertEqual(page[-1].display_name, "成员204")

    def test_group_selection_updates_visible_rows_without_losing_hidden_rows(self) -> None:
        selected = update_group_selection(
            {"hidden", "old-visible"},
            visible_group_ids={"old-visible", "new-visible"},
            selected_visible_group_ids={"new-visible"},
        )

        self.assertEqual(selected, {"hidden", "new-visible"})


if __name__ == "__main__":
    unittest.main()
