"""Resolve bundled asset paths and the writable user-data dir."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .constants import APP_NAME


def asset_path(name: str) -> Path:
    """Return the path to a file in assets/, working frozen or from source."""
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:  # PyInstaller bundle: datas land under _MEIPASS/assets
        return Path(base) / "assets" / name
    return Path(__file__).resolve().parents[3] / "assets" / name


def user_data_dir() -> Path:
    """Per-user writable dir for persisted state (history DB, etc.)."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def history_db_path() -> Path:
    return user_data_dir() / "history.db"
