"""Pure formatting helpers — no Qt, no psutil. Fully unit-tested."""

from __future__ import annotations

from .constants import BYTE_SUFFIXES, BYTE_UNIT, PERCENT_MAX, PERCENT_MIN


def human_bytes(num_bytes: float) -> str:
    """Format a byte count as a human-readable string.

    Bytes render as integers ("512 B"); KB and above use one decimal
    ("1.5 KB"). Negative inputs clamp to zero.
    """
    value = max(0.0, float(num_bytes))
    if value < BYTE_UNIT:
        return f"{int(value)} B"

    unit_index = 0
    while value >= BYTE_UNIT and unit_index < len(BYTE_SUFFIXES) - 1:
        value /= BYTE_UNIT
        unit_index += 1
    return f"{value:.1f} {BYTE_SUFFIXES[unit_index]}"


def human_rate(bytes_per_second: float) -> str:
    """Format a byte rate, e.g. ``1.5 KB/s``."""
    return f"{human_bytes(bytes_per_second)}/s"


def clamp_percent(value: float) -> float:
    """Clamp a percentage to the inclusive 0..100 range."""
    return max(PERCENT_MIN, min(PERCENT_MAX, float(value)))
