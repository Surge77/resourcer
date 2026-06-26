"""MetricsWorker + MetricsService — background sampling on a QThread.

The worker is a QObject moved onto a dedicated QThread. Its QTimers are created
*inside* the worker thread (via the ``thread.started`` slot) because a QTimer
must live in the thread whose event loop drives it. Samples cross back to the UI
through signals, which Qt delivers auto-queued — thread-safe with no locks.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QMetaObject,
    QObject,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)

from ..util.constants import POLL_INTERVAL_MS, PROCESS_INTERVAL_MS
from .sampler import Sampler

_BLOCKING = Qt.ConnectionType.BlockingQueuedConnection


class MetricsWorker(QObject):
    sample_ready = Signal(object)      # MetricsSample
    processes_ready = Signal(object)   # list[ProcessInfo]

    def __init__(self, sampler: Sampler | None = None) -> None:
        super().__init__()
        self._sampler = sampler or Sampler()
        self._metrics_timer: QTimer | None = None
        self._process_timer: QTimer | None = None

    @Slot()
    def start(self) -> None:
        self._metrics_timer = QTimer(self)
        self._metrics_timer.setInterval(POLL_INTERVAL_MS)
        self._metrics_timer.timeout.connect(self._emit_metrics)
        self._metrics_timer.start()

        self._process_timer = QTimer(self)
        self._process_timer.setInterval(PROCESS_INTERVAL_MS)
        self._process_timer.timeout.connect(self._emit_processes)
        self._process_timer.start()

        # Emit one sample immediately so the UI isn't blank for a full second.
        self._emit_metrics()
        self._emit_processes()

    @Slot()
    def stop(self) -> None:
        if self._metrics_timer is not None:
            self._metrics_timer.stop()
        if self._process_timer is not None:
            self._process_timer.stop()

    def set_metrics_interval(self, interval_ms: int) -> None:
        # No @Slot here: a queued signal delivers to a plain method by the
        # receiver's thread affinity, and PySide6's Slot stub mistypes the
        # single-int overload.
        if self._metrics_timer is not None:
            self._metrics_timer.setInterval(interval_ms)

    @Slot()
    def _emit_metrics(self) -> None:
        self.sample_ready.emit(self._sampler.sample_metrics())

    @Slot()
    def _emit_processes(self) -> None:
        self.processes_ready.emit(self._sampler.sample_processes())


class MetricsService(QObject):
    """Owns the QThread + worker lifecycle. Connect to ``worker`` signals."""

    _interval_changed = Signal(int)

    def __init__(self, sampler: Sampler | None = None) -> None:
        super().__init__()
        self._thread = QThread()
        self._worker = MetricsWorker(sampler)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        # Cross-thread, auto-queued: emitting on the UI thread delivers safely
        # to the worker thread's event loop.
        self._interval_changed.connect(self._worker.set_metrics_interval)

    @property
    def worker(self) -> MetricsWorker:
        return self._worker

    def start(self) -> None:
        self._thread.start()

    def set_metrics_interval(self, interval_ms: int) -> None:
        self._interval_changed.emit(interval_ms)

    def shutdown(self) -> None:
        """Stop timers in the worker thread, then quit + wait — no crash on exit."""
        if self._thread.isRunning():
            # PySide6's stub types `member` as bytes, but str is correct at runtime.
            QMetaObject.invokeMethod(self._worker, "stop", _BLOCKING)  # type: ignore[call-overload]
            self._thread.quit()
            self._thread.wait()
