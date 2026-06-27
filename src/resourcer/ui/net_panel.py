"""Per-interface network panel — live down/up rate for each NIC.

Rows are keyed by interface name and updated in place; the panel is only
rebuilt when the set of interfaces changes, so the 1–2 s refresh doesn't flicker.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from ..metrics.models import InterfaceRates
from ..util.format import human_rate


class NetPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(6)
        self._value_labels: dict[str, QLabel] = {}
        self._names: tuple[str, ...] = ()

    def set_interfaces(self, interfaces: list[InterfaceRates]) -> None:
        names = tuple(i.name for i in interfaces)
        if names != self._names:
            self._rebuild(names)
            self._names = names
        for iface in interfaces:
            self._value_labels[iface.name].setText(
                f"↓ {human_rate(iface.recv_rate)}    ↑ {human_rate(iface.sent_rate)}"
            )

    def _rebuild(self, names: tuple[str, ...]) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._value_labels = {}
        for row, name in enumerate(names):
            title = QLabel(name)
            title.setStyleSheet("font-weight:600;color:#d0d0d0;")
            value = QLabel("—")
            value.setStyleSheet("color:#9a9a9a;")
            self._grid.addWidget(title, row, 0)
            self._grid.addWidget(value, row, 1)
            self._value_labels[name] = value
