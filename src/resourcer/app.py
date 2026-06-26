"""QApplication bootstrap: high-DPI setup, window wiring, run()."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .ui.charts import configure_theme
from .util.constants import APP_NAME


def run() -> int:
    configure_theme()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    window = MainWindow()
    window.show()
    return app.exec()
