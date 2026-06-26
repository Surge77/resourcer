"""MainWindow — bare shell for Phase 0; charts and table land in later phases."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from .util.constants import APP_NAME, APP_VERSION


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1100, 760)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("resourcer — starting up…"))
        self.setCentralWidget(central)
