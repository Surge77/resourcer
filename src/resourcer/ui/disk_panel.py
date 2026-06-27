"""Disks panel — one capacity bar per drive, in plain numbers.

Rebuilt wholesale on each update; a machine has only a handful of drives, so
clearing and re-adding rows is cheaper than diffing.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ..metrics.models import PartitionUsage
from ..util.format import human_bytes

_WARN_PERCENT = 90.0
_BAR_NORMAL = "#4ec9b0"
_BAR_WARN = "#d16969"


class DiskPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(12)
        self._empty = QLabel("Reading drives…")
        self._empty.setStyleSheet("color:#9a9a9a;")
        self._layout.addWidget(self._empty)

    def set_partitions(self, parts: list[PartitionUsage]) -> None:
        _clear(self._layout)
        if not parts:
            note = QLabel("No readable drives.")
            note.setStyleSheet("color:#9a9a9a;")
            self._layout.addWidget(note)
        for part in parts:
            self._layout.addWidget(_drive_row(part))


def _drive_row(part: PartitionUsage) -> QWidget:
    title = QLabel(f"{part.mountpoint}   ({part.fstype or 'unknown'})")
    title.setStyleSheet("font-weight:600;color:#d0d0d0;")

    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(int(part.percent))
    bar.setTextVisible(False)
    bar.setFixedHeight(16)
    color = _BAR_WARN if part.percent >= _WARN_PERCENT else _BAR_NORMAL
    bar.setStyleSheet(f"QProgressBar::chunk{{background:{color};border-radius:3px;}}")

    free = max(0, part.total - part.used)
    detail = QLabel(
        f"{human_bytes(part.used)} used  ·  {human_bytes(free)} free  ·  "
        f"{human_bytes(part.total)} total  ({part.percent:.0f}%)"
    )
    detail.setStyleSheet("color:#9a9a9a;")

    row = QWidget()
    box = QVBoxLayout(row)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(3)
    box.addWidget(title)
    box.addWidget(bar)
    box.addWidget(detail)
    return row


def _clear(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
