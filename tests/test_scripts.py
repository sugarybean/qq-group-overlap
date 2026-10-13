from __future__ import annotations

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LauncherScriptTests(unittest.TestCase):
    def test_napcat_launches_qq_directly_on_the_desktop_display(self) -> None:
        script = (PROJECT_ROOT / "scripts" / "start-napcat.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("exec bwrap", script)
        self.assertIn("LD_LIBRARY_PATH=", script)
        self.assertIn("GSETTINGS_SCHEMA_DIR=", script)
        self.assertNotIn("NAPCAT_QUICK_ACCOUNT", script)
        self.assertIn("qq_group_overlap.login_window", script)
        self.assertRegex(
            script,
            re.compile(
                r"/mnt/runtime/napcat/squashfs-root/qq\s+\\\s+--no-sandbox"
            ),
        )
        self.assertNotRegex(
            script,
            re.compile(
                r"/mnt/runtime/napcat/squashfs-root/AppRun\s+\\\s+--no-sandbox"
            ),
        )


if __name__ == "__main__":
    unittest.main()
