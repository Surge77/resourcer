"""Process table widget — view, filter, selection, and action routing.

The selection is preserved by PID across model rebuilds. All process control
lives in ProcessActions; this module only renders and routes. The Qt model and
its pure display/sort helpers live in ``process_model``.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QPoint, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..metrics.export import processes_to_csv
from ..metrics.models import ProcessInfo
from .process_menu import ProcessActions
from .process_model import _COL_CPU, _COL_NAME, _SORT_ROLE, ProcessTableModel


class ProcessTableWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._actions = ProcessActions(self)
        self._rows: list[ProcessInfo] = []
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

        self._export_button = QPushButton("Export CSV")
        self._export_button.setToolTip("Save the current process list to a CSV file.")
        self._export_button.clicked.connect(self._on_export)

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
        self._view.doubleClicked.connect(self._on_double_clicked)
        header = self._view.horizontalHeader()
        header.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Stretch)
        self._view.selectionModel().selectionChanged.connect(self._sync_buttons)

        top = QHBoxLayout()
        top.addWidget(QLabel("Processes"))
        top.addWidget(self._search, 1)
        top.addWidget(self._per_core)
        top.addWidget(self._export_button)
        top.addWidget(self._end_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(self._view)

    def update_processes(self, rows: list[ProcessInfo]) -> None:
        keep = self.selected_pid()
        self._rows = rows
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

    def is_per_core(self) -> bool:
        return self._per_core.isChecked()

    def set_per_core(self, checked: bool) -> None:
        self._per_core.setChecked(checked)

    def _on_per_core_toggled(self, checked: bool) -> None:
        divisor = float(os.cpu_count() or 1) if checked else 1.0
        self._model.set_cpu_divisor(divisor)

    def _sync_buttons(self, *args: object) -> None:
        self._end_button.setEnabled(self.selected_process() is not None)

    def _on_end_clicked(self, *args: object) -> None:
        proc = self.selected_process()
        if proc is not None:
            self._actions.end_task(proc)

    def _on_double_clicked(self, *args: object) -> None:
        proc = self.selected_process()
        if proc is not None:
            self._actions.show_details(proc)

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export processes", "processes.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(processes_to_csv(self._rows))
        except OSError:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Export failed")
            box.setText("Could not write the file to that location.")
            box.exec()

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
