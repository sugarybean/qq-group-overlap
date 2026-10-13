from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qq_group_overlap.io import InputError, load_memberships, merge_snapshot_groups


class InputTests(unittest.TestCase):
    def test_loads_grouped_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "members.json"
            path.write_text(
                '{"groups":[{"group_id":"10","group_name":"A","members":'
                '[{"user_id":"1","nickname":"N"}]}]}',
                encoding="utf-8",
            )
            rows = load_memberships(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].group_name, "A")
            self.assertEqual(rows[0].user_id, "1")
            self.assertIsNone(rows[0].level)

    def test_loads_group_level_as_an_integer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "members.json"
            path.write_text(
                '{"groups":[{"group_id":"10","group_name":"A","members":'
                '[{"user_id":"1","nickname":"N","level":"12"}]}]}',
                encoding="utf-8",
            )
            rows = load_memberships(path)
            self.assertEqual(rows[0].level, 12)

    def test_invalid_or_negative_group_level_is_treated_as_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "members.json"
            path.write_text(
                '{"groups":[{"group_id":"10","members":['
                '{"user_id":"1","level":"unknown"},'
                '{"user_id":"2","level":-1}]}]}',
                encoding="utf-8",
            )
            rows = load_memberships(path)
            self.assertEqual([row.level for row in rows], [None, None])

    def test_loads_csv_with_bom(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "members.csv"
            path.write_text(
                "\ufeffgroup_id,group_name,user_id,nickname,card,is_robot\n"
                "10,A,1,N,C,false\n",
                encoding="utf-8",
            )
            rows = load_memberships(path)
            self.assertEqual(rows[0].card, "C")
            self.assertFalse(rows[0].is_robot)

    def test_missing_user_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "members.json"
            path.write_text(
                '{"groups":[{"group_id":"10","members":[{"nickname":"N"}]}]}',
                encoding="utf-8",
            )
            with self.assertRaises(InputError):
                load_memberships(path)

    def test_merge_snapshot_replaces_only_refreshed_groups(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "members.private.json"
            path.write_text(
                '{"groups":['
                '{"group_id":"10","group_name":"A","members":[{"user_id":"1"}]},'
                '{"group_id":"20","group_name":"B","members":[{"user_id":"2"}]}'
                ']}',
                encoding="utf-8",
            )

            merge_snapshot_groups(
                path,
                [
                    {
                        "group_id": "10",
                        "group_name": "A",
                        "members": [{"user_id": "3", "level": "8"}],
                    }
                ],
            )

            rows = load_memberships(path)
            self.assertEqual({row.user_id for row in rows}, {"2", "3"})
            self.assertEqual(next(row.level for row in rows if row.user_id == "3"), 8)


if __name__ == "__main__":
    unittest.main()
