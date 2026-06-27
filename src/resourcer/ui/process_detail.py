"""Per-process detail dialog — a read-only snapshot pulled live from psutil.

Every field is fetched defensively: a denied or vanished attribute renders as a
placeholder rather than raising, so a single privileged value never blanks the
whole dialog.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime

import psutil
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QVBoxLayout, QWidget

from ..util.format import human_bytes, human_duration

_DENIED = "(access denied)"
_UNKNOWN = "—"


def _safe(fn: Callable[[], object]) -> str:
    try:
        return str(fn())
    except psutil.AccessDenied:
        return _DENIED
    except (psutil.Error, OSError, ValueError):
        return _UNKNOWN


class ProcessDetailDialog(QDialog):
    def __init__(self, pid: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addLayout(form)

        try:
            proc = psutil.Process(pid)
        except psutil.Error:
            self.setWindowTitle(f"Process {pid}")
            form.addRow(QLabel("Status:"), QLabel("Process is no longer running."))
            return

        name = _safe(proc.name)
        self.setWindowTitle(f"{name}  (PID {pid})")
        for label, value in _fields(proc, pid, name):
            form.addRow(QLabel(f"{label}:"), _value_label(value))


def _fields(proc: psutil.Process, pid: int, name: str) -> list[tuple[str, str]]:
    mem = _memory(proc)
    return [
        ("Name", name),
        ("PID", str(pid)),
        ("Status", _safe(proc.status)),
        ("User", _safe(proc.username)),
        ("Started", _started(proc)),
        ("CPU", _safe(lambda: f"{proc.cpu_percent():.1f}%")),
        ("Threads", _safe(proc.num_threads)),
        ("Handles", _safe(lambda: getattr(proc, "num_handles")())),
        ("Memory", mem),
        ("Open files", _safe(lambda: len(proc.open_files()))),
        ("Connections", _connections(proc)),
        ("Executable", _safe(proc.exe)),
        ("Command line", _safe(lambda: " ".join(proc.cmdline()) or _UNKNOWN)),
    ]


def _memory(proc: psutil.Process) -> str:
    try:
        info = proc.memory_info()
    except (psutil.Error, OSError):
        return _UNKNOWN
    return f"{human_bytes(info.rss)} working set  ·  {human_bytes(info.vms)} virtual"


def _started(proc: psutil.Process) -> str:
    try:
        created = proc.create_time()
    except (psutil.Error, OSError):
        return _UNKNOWN
    when = datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S")
    return f"{when}  ({human_duration(time.time() - created)} ago)"


def _connections(proc: psutil.Process) -> str:
    getter = getattr(proc, "net_connections", None) or proc.connections
    return _safe(lambda: len(getter()))


def _value_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label
