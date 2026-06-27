"""MainWindow — Phase 10: tabbed shell (Overview / Performance / Processes)."""

from __future__ import annotations

from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .metrics.models import MetricsSample, ProcessInfo
from .metrics.summary import summarize
from .metrics.worker import MetricsService
from .ui.charts import CpuChart, TimeSeriesChart
from .ui.disk_panel import DiskPanel
from .ui.net_panel import NetPanel
from .ui.overview import OverviewPanel
from .ui.process_table import ProcessTableWidget
from .util.constants import APP_NAME, APP_VERSION, POLL_INTERVAL_CHOICES
from .util.format import human_bytes, human_rate
from .util.style import DARK_STYLESHEET

MEM_COLOR = "#569cd6"
DISK_READ_COLOR = "#4ec9b0"
DISK_WRITE_COLOR = "#ce9178"
NET_RECV_COLOR = "#4ec9b0"
NET_SENT_COLOR = "#ce9178"
WARN_PERCENT = 80.0  # threshold line on CPU/memory charts


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

        self._overview = OverviewPanel()
        self._cpu_chart = CpuChart(warn_at=WARN_PERCENT)
        self._mem_chart = TimeSeriesChart(
            "Memory %", series=[("mem", MEM_COLOR)], y_range=(0.0, 100.0),
            warn_at=WARN_PERCENT,
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
        self._process_table = ProcessTableWidget()
        self._disk_panel = DiskPanel()
        self._net_panel = NetPanel()

        self.setCentralWidget(self._build_central())

        self._service = MetricsService()
        self._service.worker.sample_ready.connect(self._on_sample)
        self._service.worker.processes_ready.connect(self._on_processes)
        self._service.worker.partitions_ready.connect(self._disk_panel.set_partitions)
        self._service.worker.interfaces_ready.connect(self._net_panel.set_interfaces)
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
            "Live Windows system resource dashboard — overview, performance "
            "charts, and a process manager with end / suspend / resume.<br><br>"
            "Built with PySide6, psutil and pyqtgraph.",
        )

    def _on_interval_changed(self, index: int) -> None:
        interval_ms = self._interval_combo.itemData(index)
        if interval_ms is not None:
            self._service.set_metrics_interval(int(interval_ms))

    def _build_central(self) -> QWidget:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(QLabel("Refresh"))
        toolbar.addWidget(self._interval_combo)
        toolbar.addStretch(1)

        tabs = QTabWidget()
        tabs.addTab(self._overview, "Overview")
        tabs.addTab(self._build_performance_tab(), "Performance")
        tabs.addTab(self._process_table, "Processes")
        tabs.addTab(self._build_storage_tab(), "Disks & Network")

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addLayout(toolbar)
        outer.addWidget(tabs, 1)
        return central

    def _build_storage_tab(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(12, 12, 12, 12)
        box.setSpacing(10)
        box.addWidget(_section("Drives"))
        box.addWidget(self._disk_panel)
        box.addSpacing(8)
        box.addWidget(_section("Network interfaces"))
        box.addWidget(self._net_panel)
        box.addStretch(1)
        return page

    def _build_performance_tab(self) -> QWidget:
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.addWidget(self._cpu_chart, 0, 0)
        grid.addWidget(self._mem_chart, 0, 1)
        grid.addWidget(self._disk_chart, 1, 0)
        grid.addWidget(self._net_chart, 1, 1)
        page = QWidget()
        page.setLayout(grid)
        return page

    def _on_sample(self, sample: MetricsSample) -> None:
        self._cpu_chart.push(sample.cpu_overall, sample.cpu_per_core)
        self._mem_chart.push({"mem": sample.mem_percent})
        self._disk_chart.push(
            {"Read": sample.disk_read_rate, "Write": sample.disk_write_rate}
        )
        self._net_chart.push(
            {"Down": sample.net_recv_rate, "Up": sample.net_sent_rate}
        )

        self._cpu_chart.set_readout(
            f"now {sample.cpu_overall:.0f}%  ·  peak {self._cpu_chart.overall_peak():.0f}%"
        )
        self._mem_chart.set_readout(
            f"now {sample.mem_percent:.0f}%  ·  "
            f"{human_bytes(sample.mem_used)} / {human_bytes(sample.mem_total)}"
        )
        self._disk_chart.set_readout(
            f"↓ {human_rate(sample.disk_read_rate)}   ↑ {human_rate(sample.disk_write_rate)}"
        )
        self._net_chart.set_readout(
            f"↓ {human_rate(sample.net_recv_rate)}   ↑ {human_rate(sample.net_sent_rate)}"
        )

        self._overview.set_sample(sample)

    def _on_processes(self, rows: list[ProcessInfo]) -> None:
        self._process_table.update_processes(rows)
        self._overview.set_summary(summarize(rows))

    def closeEvent(self, event: QCloseEvent) -> None:
        self._service.shutdown()
        super().closeEvent(event)


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-weight:600;font-size:13px;color:#d0d0d0;")
    return label
