"""Application-wide dark theme stylesheet."""

DARK_STYLESHEET = """
QMainWindow, QWidget { background: #1e1e1e; color: #d0d0d0; }
QLabel { color: #d0d0d0; }
QLineEdit {
    background: #2d2d30; border: 1px solid #3c3c3c; border-radius: 4px;
    padding: 4px 6px; color: #d0d0d0;
}
QPushButton {
    background: #3c3c3c; border: 1px solid #4a4a4a; border-radius: 4px;
    padding: 4px 12px; color: #d0d0d0;
}
QPushButton:hover:enabled { background: #4a4a4a; }
QPushButton:disabled { color: #6a6a6a; }
QComboBox {
    background: #2d2d30; border: 1px solid #3c3c3c; border-radius: 4px;
    padding: 3px 8px; color: #d0d0d0;
}
QTableView {
    background: #1e1e1e; alternate-background-color: #252526;
    gridline-color: #2d2d30; color: #d0d0d0;
    selection-background-color: #094771; selection-color: #ffffff;
}
QHeaderView::section {
    background: #2d2d30; color: #9a9a9a; padding: 4px;
    border: none; border-right: 1px solid #1e1e1e;
}
QMenuBar { background: #2d2d30; color: #d0d0d0; }
QMenuBar::item:selected { background: #094771; }
QMenu { background: #2d2d30; color: #d0d0d0; border: 1px solid #3c3c3c; }
QMenu::item:selected { background: #094771; }
QSplitter::handle { background: #2d2d30; }
"""
