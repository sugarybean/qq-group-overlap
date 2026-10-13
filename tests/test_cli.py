from __future__ import annotations

import unittest

from qq_group_overlap.__main__ import resolve_group_selection
from qq_group_overlap.io import InputError


GROUPS = [
    {"group_id": "10001", "group_name": "A", "member_count": 12},
    {"group_id": "10002", "group_name": "B", "member_count": 8},
    {"group_id": "10003", "group_name": "C", "member_count": 6},
]


class CliTests(unittest.TestCase):
    def test_all_selects_every_visible_group(self) -> None:
        self.assertEqual(
            resolve_group_selection(GROUPS, "all"),
            ["10001", "10002", "10003"],
        )

    def test_resolves_display_numbers_and_group_ids_without_duplicates(self) -> None:
        self.assertEqual(
            resolve_group_selection(GROUPS, "1,10003,1"),
            ["10001", "10003"],
        )

    def test_rejects_unknown_selection(self) -> None:
        with self.assertRaisesRegex(InputError, "无法识别"):
            resolve_group_selection(GROUPS, "1,99999")

    def test_requires_at_least_two_groups(self) -> None:
        with self.assertRaisesRegex(InputError, "至少选择 2 个群"):
            resolve_group_selection(GROUPS, "2")


if __name__ == "__main__":
    unittest.main()
