from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from qq_group_overlap.paths import default_data_dir, default_snapshot_path


class PathsTests(unittest.TestCase):
    def test_snapshot_is_inside_data_dir(self) -> None:
        snapshot = default_snapshot_path()
        self.assertEqual(snapshot.name, "members.private.json")
        self.assertEqual(snapshot.parent, default_data_dir())

    def test_linux_uses_xdg_data_home(self) -> None:
        with patch("sys.platform", "linux"), patch.dict(
            "os.environ", {"XDG_DATA_HOME": "/custom/xdg"}, clear=True
        ):
            self.assertEqual(
                default_data_dir(), Path("/custom/xdg/qq-group-overlap")
            )

    def test_linux_falls_back_to_dot_local_share(self) -> None:
        with patch("sys.platform", "linux"), patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                default_data_dir(),
                Path.home() / ".local" / "share" / "qq-group-overlap",
            )

    def test_windows_uses_appdata(self) -> None:
        with patch("sys.platform", "win32"), patch.dict(
            "os.environ", {"APPDATA": r"C:\Users\x\AppData\Roaming"}, clear=True
        ):
            self.assertEqual(
                default_data_dir(),
                Path(r"C:\Users\x\AppData\Roaming") / "qq-group-overlap",
            )

    def test_path_is_absolute_and_independent_of_cwd(self) -> None:
        # The whole point: resolving the default must not depend on cwd.
        self.assertTrue(default_snapshot_path().is_absolute())


if __name__ == "__main__":
    unittest.main()
