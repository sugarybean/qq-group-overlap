from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr

from qq_group_overlap.__main__ import main, resolve_group_selection
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

    def test_missing_snapshot_explains_how_to_create_one(self) -> None:
        # A first-time user has no snapshot yet. The CLI should explain how to
        # generate one instead of only reporting a missing path.
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(["analyze", "/tmp/definitely-missing-snapshot.json"])
        self.assertEqual(code, 2)
        message = stderr.getvalue()
        self.assertIn("找不到输入文件", message)
        self.assertIn("fetch", message)
        self.assertIn("live", message)


if __name__ == "__main__":
    unittest.main()
