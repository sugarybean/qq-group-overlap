from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qq_group_overlap.napcat_runtime import (
    NapCatSession,
    RuntimeBootstrapError,
    linux_launcher,
    load_or_create_token,
    napcat_home,
    pick_asset,
    runtime_ready,
    write_napcat_config,
)


LINUX_ASSETS = [
    {"name": "QQ-53644_NapCat-v4.18.38-amd64.AppImage", "browser_download_url": "u-amd"},
    {"name": "QQ-53644_NapCat-v4.18.38-arm64.AppImage", "browser_download_url": "u-arm"},
]
WINDOWS_ASSETS = [
    {"name": "NapCat.Framework.zip", "browser_download_url": "u-fw"},
    {"name": "NapCat.Shell.Windows.OneKey.zip", "browser_download_url": "u-onekey"},
]


class AssetPickTests(unittest.TestCase):
    def test_picks_linux_arch_image(self) -> None:
        self.assertEqual(pick_asset(LINUX_ASSETS, "linux-amd64"), (LINUX_ASSETS[0]["name"], "u-amd"))
        self.assertEqual(pick_asset(LINUX_ASSETS, "linux-arm64"), (LINUX_ASSETS[1]["name"], "u-arm"))

    def test_picks_windows_onekey(self) -> None:
        self.assertEqual(pick_asset(WINDOWS_ASSETS, "windows-amd64"), ("NapCat.Shell.Windows.OneKey.zip", "u-onekey"))

    def test_raises_when_platform_asset_missing(self) -> None:
        with self.assertRaises(RuntimeBootstrapError):
            pick_asset(WINDOWS_ASSETS, "linux-amd64")


class TokenTests(unittest.TestCase):
    def test_token_is_created_once_and_reused(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            first = load_or_create_token(base)
            second = load_or_create_token(base)
            self.assertEqual(first, second)
            self.assertGreaterEqual(len(first), 24)
            mode = stat.S_IMODE((base / "napcat-token.txt").stat().st_mode)
            self.assertEqual(mode, 0o600)


class ConfigTests(unittest.TestCase):
    def test_writes_onebot_http_server_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            target = write_napcat_config("secret-token", base, port=3000)
            payload = json.loads(target.read_text(encoding="utf-8"))
        server = payload["network"]["httpServers"][0]
        self.assertTrue(server["enable"])
        self.assertEqual(server["host"], "127.0.0.1")
        self.assertEqual(server["port"], 3000)
        self.assertEqual(server["token"], "secret-token")
        self.assertFalse(server["enableWebsocket"])


class ReadinessTests(unittest.TestCase):
    def test_not_ready_when_runtime_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with patch("sys.platform", "linux"):
                self.assertFalse(runtime_ready(Path(td)))

    def test_ready_when_linux_launcher_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            launcher = linux_launcher(base)
            launcher.parent.mkdir(parents=True)
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")
            with patch("sys.platform", "linux"):
                self.assertTrue(runtime_ready(base))


class SessionTests(unittest.TestCase):
    def test_qr_path_points_into_napcat_home(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            session = NapCatSession("token", base)
            self.assertEqual(
                session.qr_path, napcat_home(base) / "cache" / "qrcode.png"
            )

    def test_current_uin_none_when_not_logged_in(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            session = NapCatSession("token", Path(td))
            with patch.object(
                session._client, "get_login_user_id", side_effect=OSError("down")
            ):
                self.assertIsNone(session.current_uin())

    def test_current_uin_returns_login(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            session = NapCatSession("token", Path(td))
            with patch.object(
                session._client, "get_login_user_id", return_value="100000001"
            ):
                self.assertEqual(session.current_uin(), "100000001")

    def test_stop_is_safe_when_never_started(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            NapCatSession("token", Path(td)).stop()


if __name__ == "__main__":
    unittest.main()
