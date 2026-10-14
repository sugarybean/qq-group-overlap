from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from qq_group_overlap.onebot import OneBotClient


class FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class OneBotTests(unittest.TestCase):
    def test_reads_the_current_login_account(self) -> None:
        response = FakeResponse(
            {
                "status": "ok",
                "retcode": 0,
                "data": {"user_id": 100000001, "nickname": "测试账号"},
            }
        )
        client = OneBotClient("http://127.0.0.1:3000")
        with patch("urllib.request.urlopen", return_value=response):
            self.assertEqual(client.get_login_user_id(), "100000001")

    def test_lists_groups_in_a_stable_human_friendly_order(self) -> None:
        response = FakeResponse(
            {
                "status": "ok",
                "retcode": 0,
                "data": [
                    {"group_id": 20, "group_name": "Zulu", "member_count": 8},
                    {"group_id": 10, "group_name": "Alpha", "member_count": 12},
                ],
            }
        )
        client = OneBotClient("http://127.0.0.1:3000")
        with patch("urllib.request.urlopen", return_value=response):
            groups = client.list_groups()

        self.assertEqual(
            groups,
            [
                {"group_id": "10", "group_name": "Alpha", "member_count": 12},
                {"group_id": "20", "group_name": "Zulu", "member_count": 8},
            ],
        )

    def test_fetches_selected_groups_and_normalizes_members(self) -> None:
        responses = [
            FakeResponse(
                {
                    "status": "ok",
                    "retcode": 0,
                    "data": [
                        {"group_id": 10, "group_name": "A"},
                        {"group_id": 20, "group_name": "B"},
                    ],
                }
            ),
            FakeResponse(
                {
                    "status": "ok",
                    "retcode": 0,
                    "data": [
                        {
                            "user_id": 1,
                            "nickname": "N",
                            "card": "C",
                            "role": "member",
                            "level": "12",
                        }
                    ],
                }
            ),
            FakeResponse(
                {
                    "status": "ok",
                    "retcode": 0,
                    "data": [{"user_id": 1, "nickname": "N", "card": ""}],
                }
            ),
        ]
        client = OneBotClient("http://127.0.0.1:3000", token="secret")
        with patch("urllib.request.urlopen", side_effect=responses) as urlopen:
            groups = client.fetch_groups(["10", "20"])
        self.assertEqual([group["group_name"] for group in groups], ["A", "B"])
        self.assertEqual(groups[0]["members"][0]["user_id"], "1")
        self.assertEqual(groups[0]["members"][0]["level"], "12")
        request = urlopen.call_args_list[0].args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")


if __name__ == "__main__":
    unittest.main()
