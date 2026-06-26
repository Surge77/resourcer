"""Launcher: `python main.py`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from resourcer.app import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run())
