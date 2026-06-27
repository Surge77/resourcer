"""QApplication bootstrap: high-DPI setup, window wiring, run()."""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .ui.charts import configure_theme
from .util.constants import APP_NAME
from .util.paths import asset_path


def run() -> int:
    configure_theme()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)  # gives QSettings a stable storage location
    QApplication.setWindowIcon(QIcon(str(asset_path("icon.ico"))))

    window = MainWindow()
    window.show()
    return app.exec()
