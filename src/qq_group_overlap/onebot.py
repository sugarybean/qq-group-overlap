from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class OneBotError(RuntimeError):
    """Raised when a OneBot HTTP action fails."""


def _direct_opener() -> urllib.request.OpenerDirector:
    """Build an opener that bypasses any proxy environment variables.

    NapCat's OneBot endpoint lives on this machine (typically 127.0.0.1). If the
    user's shell exports http_proxy/https_proxy, urllib would route even these
    loopback requests through the proxy and the connection would fail (commonly
    surfacing as a 502). Forcing an empty proxy list keeps loopback traffic
    direct while leaving the rest of the system untouched.
    """

    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


class OneBotClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._opener = _direct_opener()

    @classmethod
    def from_environment(
        cls, base_url: str, token_environment: str, timeout: float = 15
    ) -> "OneBotClient":
        return cls(base_url, os.environ.get(token_environment, ""), timeout)

    def action(self, name: str, params: dict[str, Any]) -> Any:
        request = urllib.request.Request(
            f"{self.base_url}/{name.lstrip('/')}",
            data=json.dumps(params, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise OneBotError(f"OneBot 请求失败：{exc}") from exc
        if not isinstance(payload, dict) or payload.get("status") != "ok" or payload.get("retcode") != 0:
            raise OneBotError(f"OneBot {name} 返回失败：{payload!r}")
        return payload.get("data")

    def list_groups(self) -> list[dict[str, Any]]:
        available = self.action("get_group_list", {})
        if not isinstance(available, list):
            raise OneBotError("get_group_list 未返回列表")

        groups: list[dict[str, Any]] = []
        for item in available:
            if not isinstance(item, dict) or item.get("group_id") is None:
                continue
            group_id = str(item["group_id"])
            try:
                member_count = int(item.get("member_count") or 0)
            except (TypeError, ValueError):
                member_count = 0
            groups.append(
                {
                    "group_id": group_id,
                    "group_name": str(item.get("group_name") or group_id),
                    "member_count": member_count,
                }
            )
        groups.sort(key=lambda item: (item["group_name"].casefold(), item["group_id"]))
        return groups

    def get_login_user_id(self) -> str:
        login = self.action("get_login_info", {})
        if not isinstance(login, dict) or login.get("user_id") is None:
            raise OneBotError("get_login_info 未返回当前登录账号")
        return str(login["user_id"])

    def fetch_groups(self, group_ids: list[str]) -> list[dict[str, Any]]:
        group_names = {
            item["group_id"]: item["group_name"] for item in self.list_groups()
        }
        missing = [group_id for group_id in group_ids if group_id not in group_names]
        if missing:
            raise OneBotError("当前账号不在这些群中：" + "、".join(missing))

        groups: list[dict[str, Any]] = []
        for group_id in group_ids:
            members = self.action("get_group_member_list", {"group_id": int(group_id)})
            if not isinstance(members, list):
                raise OneBotError(f"群 {group_id} 的成员列表格式不正确")
            normalized_members = []
            for member in members:
                if not isinstance(member, dict) or member.get("user_id") is None:
                    continue
                normalized_members.append(
                    {
                        "user_id": str(member["user_id"]),
                        "nickname": str(member.get("nickname") or ""),
                        "card": str(member.get("card") or ""),
                        "role": str(member.get("role") or "member"),
                        "is_robot": bool(member.get("is_robot", False)),
                        "level": (
                            None
                            if member.get("level") is None
                            else str(member.get("level"))
                        ),
                    }
                )
            groups.append(
                {
                    "group_id": group_id,
                    "group_name": group_names[group_id],
                    "members": normalized_members,
                }
            )
        return groups
