"""Resolve bundled asset paths in both dev and PyInstaller-frozen runs."""

from __future__ import annotations

import sys
from pathlib import Path


def asset_path(name: str) -> Path:
    """Return the path to a file in assets/, working frozen or from source."""
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:  # PyInstaller bundle: datas land under _MEIPASS/assets
        return Path(base) / "assets" / name
    return Path(__file__).resolve().parents[3] / "assets" / name
