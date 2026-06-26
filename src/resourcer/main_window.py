"""MainWindow — Phase 4: one live CPU chart fed by the worker signal."""

from __future__ import annotations

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from .metrics.models import MetricsSample
from .metrics.worker import MetricsService
from .ui.charts import TimeSeriesChart
from .util.constants import APP_NAME, APP_VERSION

CPU_COLOR = "#4ec9b0"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1100, 760)

        self._cpu_chart = TimeSeriesChart(
            "CPU %", series=[("cpu", CPU_COLOR)], y_range=(0.0, 100.0)
        )

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self._cpu_chart)
        self.setCentralWidget(central)

        self._service = MetricsService()
        self._service.worker.sample_ready.connect(self._on_sample)
        self._service.start()

    def _on_sample(self, sample: MetricsSample) -> None:
        self._cpu_chart.push({"cpu": sample.cpu_overall})

    def closeEvent(self, event: QCloseEvent) -> None:
        self._service.shutdown()
        super().closeEvent(event)
