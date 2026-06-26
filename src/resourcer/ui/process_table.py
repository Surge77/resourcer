"""Process table — model/view with numeric sort, name filter, 2s refresh.

The model is rebuilt wholesale each refresh (bounded process count → cheap).
A separate UserRole carries raw values so the proxy sorts CPU%/memory
numerically instead of lexically, and the current selection is preserved by PID
across rebuilds so the kill action stays usable.
"""

from __future__ import annotations

from typing import Any, Union

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)

_Index = Union[QModelIndex, QPersistentModelIndex]
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..metrics.models import ProcessInfo
from ..util.format import human_bytes

_COL_PID = 0
_COL_NAME = 1
_COL_CPU = 2
_COL_MEM = 3
_HEADERS = ("PID", "Name", "CPU %", "Memory")
_SORT_ROLE = int(Qt.ItemDataRole.UserRole)


class ProcessTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[ProcessInfo] = []

    def set_processes(self, rows: list[ProcessInfo]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def pid_at(self, row: int) -> int | None:
        if 0 <= row < len(self._rows):
            return self._rows[row].pid
        return None

    def rowCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(_HEADERS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = 0
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _HEADERS[section]
        return None

    def data(self, index: _Index, role: int = 0) -> Any:
        if not index.isValid():
            return None
        proc = self._rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return _display(proc, col)
        if role == _SORT_ROLE:
            return _sort_key(proc, col)
        if role == Qt.ItemDataRole.TextAlignmentRole and col != _COL_NAME:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


def _display(proc: ProcessInfo, col: int) -> str:
    if col == _COL_PID:
        return str(proc.pid)
    if col == _COL_NAME:
        return proc.name
    if col == _COL_CPU:
        return f"{proc.cpu_percent:.1f}"
    return human_bytes(proc.mem_rss)


def _sort_key(proc: ProcessInfo, col: int):
    if col == _COL_PID:
        return proc.pid
    if col == _COL_NAME:
        return proc.name.lower()
    if col == _COL_CPU:
        return proc.cpu_percent
    return proc.mem_rss


class ProcessTableWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._model = ProcessTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(_SORT_ROLE)
        self._proxy.setFilterKeyColumn(_COL_NAME)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by name…")
        self._search.textChanged.connect(self._proxy.setFilterFixedString)

        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSortingEnabled(True)
        self._view.sortByColumn(_COL_CPU, Qt.SortOrder.DescendingOrder)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.verticalHeader().setVisible(False)
        self._view.setAlternatingRowColors(True)
        header = self._view.horizontalHeader()
        header.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Stretch)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Processes"))
        layout.addWidget(self._search)
        layout.addWidget(self._view)

    def update_processes(self, rows: list[ProcessInfo]) -> None:
        keep = self.selected_pid()
        self._model.set_processes(rows)
        if keep is not None:
            self._reselect(keep)

    def selected_pid(self) -> int | None:
        index = self._view.selectionModel().currentIndex()
        if not index.isValid():
            return None
        source = self._proxy.mapToSource(index)
        return self._model.pid_at(source.row())

    def _reselect(self, pid: int) -> None:
        for row in range(self._model.rowCount()):
            if self._model.pid_at(row) == pid:
                proxy_index = self._proxy.mapFromSource(self._model.index(row, 0))
                if proxy_index.isValid():
                    self._view.selectRow(proxy_index.row())
                return
