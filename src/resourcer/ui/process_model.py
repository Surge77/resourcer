"""Process table model — Qt model plus the pure display/sort helpers.

The model is rebuilt wholesale each refresh (bounded process count → cheap). A
UserRole carries raw values so the proxy sorts numerically. Display formatting
and sort keys live in free functions here so they stay unit-testable without Qt.
"""

from __future__ import annotations

import time
from typing import Any, Union

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QBrush, QColor

from ..metrics.models import ProcessInfo
from ..util.format import human_bytes, human_duration

_Index = Union[QModelIndex, QPersistentModelIndex]

_COL_PID, _COL_NAME, _COL_CPU, _COL_MEM = 0, 1, 2, 3
_COL_STATUS, _COL_THREADS, _COL_USER, _COL_UPTIME, _COL_NET = 4, 5, 6, 7, 8
_HEADERS = (
    "PID", "Name", "CPU %", "Memory", "Status", "Threads", "User", "Uptime", "Net",
)
_RIGHT = {_COL_PID, _COL_CPU, _COL_MEM, _COL_THREADS, _COL_UPTIME, _COL_NET}
_SORT_ROLE = int(Qt.ItemDataRole.UserRole)
_DASH = "—"

_HEAT_HIGH, _HEAT_MED = 80.0, 50.0
_HEADER_TIPS = {
    _COL_PID: "Process identifier.",
    _COL_NAME: "Executable name.",
    _COL_CPU: "CPU usage. Summed across cores (can exceed 100%) unless “CPU ÷ cores” is on.",
    _COL_MEM: "Working-set memory (RAM) held by the process.",
    _COL_STATUS: "OS scheduling state — running, sleeping, stopped…",
    _COL_THREADS: "Number of threads in the process.",
    _COL_USER: "Account the process runs as.",
    _COL_UPTIME: "How long the process has been running.",
    _COL_NET: "Active network connections (TCP/UDP) the process holds. "
    "Sort to find the chattiest processes.",
}


def _heat_brush(cpu_percent: float) -> QBrush | None:
    """Tint a row by CPU load so hot processes stand out at a glance."""
    if cpu_percent >= _HEAT_HIGH:
        return QBrush(QColor(209, 105, 105, 70))
    if cpu_percent >= _HEAT_MED:
        return QBrush(QColor(209, 170, 105, 55))
    return None


class ProcessTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[ProcessInfo] = []
        self._now = time.time()
        self._cpu_divisor = 1.0

    def set_processes(self, rows: list[ProcessInfo]) -> None:
        self.beginResetModel()
        self._rows = rows
        self._now = time.time()
        self.endResetModel()

    def set_cpu_divisor(self, divisor: float) -> None:
        self._cpu_divisor = max(1.0, divisor)
        if self._rows:
            top = self.index(0, _COL_CPU)
            bottom = self.index(len(self._rows) - 1, _COL_CPU)
            self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.DisplayRole])

    def pid_at(self, row: int) -> int | None:
        proc = self.proc_at(row)
        return proc.pid if proc is not None else None

    def proc_at(self, row: int) -> ProcessInfo | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def rowCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(_HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> Any:
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return _HEADERS[section]
        if role == Qt.ItemDataRole.ToolTipRole:
            return _HEADER_TIPS.get(section)
        return None

    def data(self, index: _Index, role: int = 0) -> Any:
        if not index.isValid():
            return None
        proc = self._rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return _display(proc, col, self._now, self._cpu_divisor)
        if role == _SORT_ROLE:
            return _sort_key(proc, col, self._now)
        if role == Qt.ItemDataRole.TextAlignmentRole and col in _RIGHT:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.BackgroundRole:
            return _heat_brush(proc.cpu_percent / self._cpu_divisor)
        return None


def _display(proc: ProcessInfo, col: int, now: float, cpu_divisor: float) -> str:
    if col == _COL_PID:
        return str(proc.pid)
    if col == _COL_NAME:
        return proc.name
    if col == _COL_CPU:
        return f"{proc.cpu_percent / cpu_divisor:.1f}"
    if col == _COL_MEM:
        return human_bytes(proc.mem_rss)
    if col == _COL_STATUS:
        return proc.status or _DASH
    if col == _COL_THREADS:
        return str(proc.num_threads) if proc.num_threads else _DASH
    if col == _COL_USER:
        return proc.username or _DASH
    if col == _COL_UPTIME:
        return human_duration(now - proc.create_time) if proc.create_time else _DASH
    return str(proc.conn_count) if proc.conn_count else _DASH


def _sort_key(proc: ProcessInfo, col: int, now: float):
    if col == _COL_PID:
        return proc.pid
    if col == _COL_NAME:
        return proc.name.lower()
    if col == _COL_CPU:
        return proc.cpu_percent
    if col == _COL_MEM:
        return proc.mem_rss
    if col == _COL_STATUS:
        return proc.status
    if col == _COL_THREADS:
        return proc.num_threads
    if col == _COL_USER:
        return proc.username.lower()
    if col == _COL_UPTIME:
        return (now - proc.create_time) if proc.create_time else -1.0
    return proc.conn_count
