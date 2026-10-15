from __future__ import annotations

import os
import sys
from pathlib import Path

_APP_DIR_NAME = "qq-group-overlap"


def default_data_dir() -> Path:
    """Return the per-user data directory for snapshots and reports.

    Snapshots must NOT depend on the current working directory: a user who
    installs the package and runs the tool from a random folder should still
    see the same snapshot every time. We follow platform conventions:

    - Windows: %APPDATA%\\qq-group-overlap (falls back to ~/AppData/Roaming)
    - macOS / Linux and other Unix: $XDG_DATA_HOME/qq-group-overlap,
      defaulting to ~/.local/share/qq-group-overlap
    """

    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / _APP_DIR_NAME
        return Path.home() / "AppData" / "Roaming" / _APP_DIR_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / _APP_DIR_NAME
    return Path.home() / ".local" / "share" / _APP_DIR_NAME


def default_snapshot_path() -> Path:
    """Default location of the member snapshot, independent of cwd."""

    return default_data_dir() / "members.private.json"
