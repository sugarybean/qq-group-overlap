from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from qq_group_overlap.login_window import qr_is_current


class QrLoginWindowTests(unittest.TestCase):
    def test_qr_must_be_nonempty_and_newer_than_this_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            qr_path = Path(directory) / "qrcode.png"

            self.assertFalse(qr_is_current(qr_path, not_before=100.0))

            qr_path.write_bytes(b"png")
            os.utime(qr_path, (90.0, 90.0))
            self.assertFalse(qr_is_current(qr_path, not_before=100.0))

            os.utime(qr_path, (101.0, 101.0))
            self.assertTrue(qr_is_current(qr_path, not_before=100.0))


if __name__ == "__main__":
    unittest.main()
