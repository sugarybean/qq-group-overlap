from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qq_group_overlap.analyze import analyze_memberships
from qq_group_overlap.models import Membership
from qq_group_overlap.report import mask_user_id, write_reports


class ReportTests(unittest.TestCase):
    def test_masks_middle_of_qq_number(self) -> None:
        self.assertEqual(mask_user_id("123456789"), "123***789")
        self.assertEqual(mask_user_id("1234"), "****")

    def test_writes_all_reports_and_masks_ids(self) -> None:
        result = analyze_memberships(
            [
                Membership("g1", "A|B", "123456789", "小明", "名片A"),
                Membership("g2", "C", "123456789", "小明", "名片B"),
            ]
        )
        with tempfile.TemporaryDirectory() as temporary:
            report, people, pairs = write_reports(result, temporary, mask_ids=True)
            self.assertTrue(report.exists())
            self.assertTrue(people.exists())
            self.assertTrue(pairs.exists())
            markdown = report.read_text(encoding="utf-8")
            self.assertIn("123***789", markdown)
            self.assertNotIn("123456789", markdown)
            self.assertIn("A\\|B", markdown)
            self.assertTrue(people.read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()

