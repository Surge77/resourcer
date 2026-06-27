"""Process table — model/view with numeric sort, name filter, right-click actions.

The model is rebuilt wholesale each refresh (bounded process count → cheap). A
UserRole carries raw values so the proxy sorts numerically, and the selection is
preserved by PID across rebuilds. All process control lives in ProcessActions;
this module only renders and routes.
"""

from __future__ import annotations

import os
import time
from typing import Any, Union

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..metrics.models import ProcessInfo
from ..util.format import human_bytes, human_duration
from .process_menu import ProcessActions

_Index = Union[QModelIndex, QPersistentModelIndex]

_COL_PID, _COL_NAME, _COL_CPU, _COL_MEM = 0, 1, 2, 3
_COL_STATUS, _COL_THREADS, _COL_USER, _COL_UPTIME = 4, 5, 6, 7
_HEADERS = ("PID", "Name", "CPU %", "Memory", "Status", "Threads", "User", "Uptime")
_RIGHT = {_COL_PID, _COL_CPU, _COL_MEM, _COL_THREADS, _COL_UPTIME}
_SORT_ROLE = int(Qt.ItemDataRole.UserRole)
_DASH = "—"


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
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _HEADERS[section]
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
    return human_duration(now - proc.create_time) if proc.create_time else _DASH


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
    return (now - proc.create_time) if proc.create_time else -1.0


class ProcessTableWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._actions = ProcessActions(self)
        self._model = ProcessTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(_SORT_ROLE)
        self._proxy.setFilterKeyColumn(_COL_NAME)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by name…")
        self._search.textChanged.connect(self._proxy.setFilterFixedString)

        self._per_core = QCheckBox("CPU ÷ cores")
        self._per_core.setToolTip(
            "Show each process's CPU as a share of total capacity (0–100%),\n"
            "instead of summed across cores (can exceed 100%)."
        )
        self._per_core.toggled.connect(self._on_per_core_toggled)

        self._end_button = QPushButton("End task")
        self._end_button.setEnabled(False)
        self._end_button.clicked.connect(self._on_end_clicked)

        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSortingEnabled(True)
        self._view.sortByColumn(_COL_CPU, Qt.SortOrder.DescendingOrder)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.verticalHeader().setVisible(False)
        self._view.setAlternatingRowColors(True)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._show_context_menu)
        self._view.doubleClicked.connect(self._on_end_clicked)
        header = self._view.horizontalHeader()
        header.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Stretch)
        self._view.selectionModel().selectionChanged.connect(self._sync_buttons)

        top = QHBoxLayout()
        top.addWidget(QLabel("Processes"))
        top.addWidget(self._search, 1)
        top.addWidget(self._per_core)
        top.addWidget(self._end_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(self._view)

    def update_processes(self, rows: list[ProcessInfo]) -> None:
        keep = self.selected_pid()
        self._model.set_processes(rows)
        if keep is not None:
            self._reselect(keep)
        self._sync_buttons()

    def selected_pid(self) -> int | None:
        proc = self.selected_process()
        return proc.pid if proc is not None else None

    def selected_process(self) -> ProcessInfo | None:
        index = self._view.selectionModel().currentIndex()
        if not index.isValid():
            return None
        return self._model.proc_at(self._proxy.mapToSource(index).row())

    def _on_per_core_toggled(self, checked: bool) -> None:
        divisor = float(os.cpu_count() or 1) if checked else 1.0
        self._model.set_cpu_divisor(divisor)

    def _sync_buttons(self, *args: object) -> None:
        self._end_button.setEnabled(self.selected_process() is not None)

    def _on_end_clicked(self, *args: object) -> None:
        proc = self.selected_process()
        if proc is not None:
            self._actions.end_task(proc)

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self._view.indexAt(pos)
        if index.isValid():
            self._view.selectRow(index.row())
        proc = self.selected_process()
        if proc is not None:
            self._actions.menu_for(proc).exec(self._view.viewport().mapToGlobal(pos))

    def _reselect(self, pid: int) -> None:
        for row in range(self._model.rowCount()):
            if self._model.pid_at(row) == pid:
                proxy_index = self._proxy.mapFromSource(self._model.index(row, 0))
                if proxy_index.isValid():
                    self._view.selectRow(proxy_index.row())
                return
