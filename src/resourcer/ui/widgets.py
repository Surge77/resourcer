"""Small reusable widgets — the toolbar stat card."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatCard(QFrame):
    """A compact label-over-value tile shown in the top toolbar."""

    def __init__(self, label: str, accent: str = "#4ec9b0") -> None:
        super().__init__()
        self.setObjectName("statCard")
        self.setStyleSheet(
            "#statCard{background:#252526;border-radius:6px;}"
            f"#statCard QLabel#value{{color:{accent};font-size:18px;font-weight:600;}}"
            "#statCard QLabel#caption{color:#9a9a9a;font-size:10px;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(0)

        self._caption = QLabel(label)
        self._caption.setObjectName("caption")
        self._value = QLabel("—")
        self._value.setObjectName("value")
        self._value.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self._caption)
        layout.addWidget(self._value)

    def set_value(self, text: str) -> None:
        self._value.setText(text)
