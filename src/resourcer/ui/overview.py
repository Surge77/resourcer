"""Overview panel — an at-a-glance, plain-language system summary.

Answers "what's going on right now?" without reading charts: headline tiles,
a memory-usage bar with absolute numbers, and the single biggest CPU and memory
consumers named outright.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ..metrics.models import MetricsSample, ProcessSummary
from ..util.format import human_bytes, human_duration, human_rate
from .widgets import StatCard

_CPU = "#4ec9b0"
_RAM = "#569cd6"
_NET = "#ce9178"
_MUTED = "#9a9a9a"


class OverviewPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._cpu = StatCard("CPU", accent=_CPU)
        self._ram = StatCard("RAM", accent=_RAM)
        self._down = StatCard("NET DOWN", accent=_NET)
        self._up = StatCard("NET UP", accent=_NET)
        self._uptime = StatCard("UPTIME", accent=_MUTED)
        self._procs = StatCard("PROCESSES", accent=_MUTED)
        self._threads = StatCard("THREADS", accent=_MUTED)

        tiles = QHBoxLayout()
        tiles.setSpacing(8)
        for card in (self._cpu, self._ram, self._down, self._up,
                     self._uptime, self._procs, self._threads):
            tiles.addWidget(card)
        tiles.addStretch(1)

        self._mem_bar = QProgressBar()
        self._mem_bar.setRange(0, 100)
        self._mem_bar.setTextVisible(False)
        self._mem_bar.setFixedHeight(18)
        self._mem_detail = QLabel("—")
        self._mem_detail.setStyleSheet(f"color:{_MUTED};")

        self._top_cpu = QLabel("Top CPU: —")
        self._top_mem = QLabel("Top memory: —")

        mem_box = QVBoxLayout()
        mem_box.setSpacing(4)
        mem_box.addWidget(_heading("Memory"))
        mem_box.addWidget(self._mem_bar)
        mem_box.addWidget(self._mem_detail)

        consumers = QGridLayout()
        consumers.setVerticalSpacing(4)
        consumers.addWidget(_heading("Heaviest processes"), 0, 0)
        consumers.addWidget(self._top_cpu, 1, 0)
        consumers.addWidget(self._top_mem, 2, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(18)
        layout.addLayout(tiles)
        layout.addLayout(mem_box)
        layout.addLayout(consumers)
        layout.addStretch(1)

    def set_sample(self, sample: MetricsSample) -> None:
        self._cpu.set_value(f"{sample.cpu_overall:.0f}%")
        self._ram.set_value(f"{sample.mem_percent:.0f}%")
        self._down.set_value(human_rate(sample.net_recv_rate))
        self._up.set_value(human_rate(sample.net_sent_rate))
        self._uptime.set_value(human_duration(sample.uptime))

        self._mem_bar.setValue(int(sample.mem_percent))
        free = sample.mem_available or max(0, sample.mem_total - sample.mem_used)
        self._mem_detail.setText(
            f"{human_bytes(sample.mem_used)} used  ·  {human_bytes(free)} free  ·  "
            f"{human_bytes(sample.mem_total)} total"
        )

    def set_summary(self, summary: ProcessSummary) -> None:
        self._procs.set_value(str(summary.count))
        self._threads.set_value(str(summary.thread_total))
        if summary.top_cpu is not None:
            p = summary.top_cpu
            self._top_cpu.setText(f"Top CPU:  {p.name}  (PID {p.pid})  —  {p.cpu_percent:.0f}%")
        if summary.top_mem is not None:
            p = summary.top_mem
            self._top_mem.setText(
                f"Top memory:  {p.name}  (PID {p.pid})  —  {human_bytes(p.mem_rss)}"
            )


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-weight:600;color:#d0d0d0;")
    return label
