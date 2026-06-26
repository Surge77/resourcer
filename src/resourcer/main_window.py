"""MainWindow — Phase 5: stat cards + full 2x2 chart grid, all live."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .metrics.models import MetricsSample, ProcessInfo
from .metrics.worker import MetricsService
from .ui.charts import CpuChart, TimeSeriesChart
from .ui.process_table import ProcessTableWidget
from .ui.widgets import StatCard
from .util.constants import APP_NAME, APP_VERSION, POLL_INTERVAL_CHOICES
from .util.format import human_bytes, human_rate
from .util.style import DARK_STYLESHEET

MEM_COLOR = "#569cd6"
DISK_READ_COLOR = "#4ec9b0"
DISK_WRITE_COLOR = "#ce9178"
NET_RECV_COLOR = "#4ec9b0"
NET_SENT_COLOR = "#ce9178"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1100, 760)
        self.setStyleSheet(DARK_STYLESHEET)
        self._build_menu()

        self._interval_combo = QComboBox()
        for label, interval_ms in POLL_INTERVAL_CHOICES:
            self._interval_combo.addItem(label, interval_ms)
        self._interval_combo.currentIndexChanged.connect(self._on_interval_changed)

        self._cpu_chart = CpuChart()
        self._mem_chart = TimeSeriesChart(
            "Memory %", series=[("mem", MEM_COLOR)], y_range=(0.0, 100.0)
        )
        self._disk_chart = TimeSeriesChart(
            "Disk  R/W  bytes/s",
            series=[("Read", DISK_READ_COLOR), ("Write", DISK_WRITE_COLOR)],
            y_label_format=human_bytes,
            legend=True,
        )
        self._net_chart = TimeSeriesChart(
            "Network  down/up  bytes/s",
            series=[("Down", NET_RECV_COLOR), ("Up", NET_SENT_COLOR)],
            y_label_format=human_bytes,
            legend=True,
        )

        self._card_cpu = StatCard("CPU")
        self._card_ram = StatCard("RAM", accent=MEM_COLOR)
        self._card_down = StatCard("NET DOWN", accent=NET_RECV_COLOR)
        self._card_up = StatCard("NET UP", accent=NET_SENT_COLOR)

        self._process_table = ProcessTableWidget()

        self.setCentralWidget(self._build_central())

        self._service = MetricsService()
        self._service.worker.sample_ready.connect(self._on_sample)
        self._service.worker.processes_ready.connect(self._on_processes)
        self._service.start()

    def _build_menu(self) -> None:
        help_menu = self.menuBar().addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> {APP_VERSION}<br><br>"
            "Live Windows system resource dashboard — CPU, memory, disk and "
            "network charts with a sortable process manager.<br><br>"
            "Built with PySide6, psutil and pyqtgraph.",
        )

    def _on_interval_changed(self, index: int) -> None:
        interval_ms = self._interval_combo.itemData(index)
        if interval_ms is not None:
            self._service.set_metrics_interval(int(interval_ms))

    def _build_central(self) -> QWidget:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(self._interval_combo)
        for card in (self._card_cpu, self._card_ram, self._card_down, self._card_up):
            toolbar.addWidget(card)
        toolbar.addStretch(1)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.addWidget(self._cpu_chart, 0, 0)
        grid.addWidget(self._mem_chart, 0, 1)
        grid.addWidget(self._disk_chart, 1, 0)
        grid.addWidget(self._net_chart, 1, 1)
        charts = QWidget()
        charts.setLayout(grid)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(charts)
        splitter.addWidget(self._process_table)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addLayout(toolbar)
        outer.addWidget(splitter, 1)
        return central

    def _on_sample(self, sample: MetricsSample) -> None:
        self._cpu_chart.push(sample.cpu_overall, sample.cpu_per_core)
        self._mem_chart.push({"mem": sample.mem_percent})
        self._disk_chart.push(
            {"Read": sample.disk_read_rate, "Write": sample.disk_write_rate}
        )
        self._net_chart.push(
            {"Down": sample.net_recv_rate, "Up": sample.net_sent_rate}
        )

        self._card_cpu.set_value(f"{sample.cpu_overall:.0f}%")
        self._card_ram.set_value(f"{sample.mem_percent:.0f}%")
        self._card_down.set_value(human_rate(sample.net_recv_rate))
        self._card_up.set_value(human_rate(sample.net_sent_rate))

    def _on_processes(self, rows: list[ProcessInfo]) -> None:
        self._process_table.update_processes(rows)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._service.shutdown()
        super().closeEvent(event)
