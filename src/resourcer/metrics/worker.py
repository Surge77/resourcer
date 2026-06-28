"""Background sampling on two QThreads — a fast lane and a slow lane.

The crux of the app is that the UI never blocks. A full process scan
(``process_iter`` over hundreds of processes) costs 1–4s on Windows, so it runs
on its own *slow* thread. The *fast* thread samples cheap system metrics + GPU at
1 Hz, completely insulated from the slow scan — a long process scan can never
starve the charts. Each worker's QTimers are created inside its own thread (via
``thread.started``) because a QTimer must live in the thread whose event loop
drives it. Samples cross to the UI through auto-queued signals — thread-safe, no
locks.
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

from ..util.constants import (
    PARTITION_INTERVAL_MS,
    POLL_INTERVAL_MS,
    PROCESS_INTERVAL_MS,
)
from .gpu import GpuSampler
from .sampler import Sampler

_BLOCKING = Qt.ConnectionType.BlockingQueuedConnection


class MetricsWorker(QObject):
    """Fast lane: cheap system metrics + GPU at 1 Hz."""

    sample_ready = Signal(object)       # MetricsSample
    gpus_ready = Signal(object)         # list[GpuInfo]

    def __init__(self, sampler: Sampler | None = None) -> None:
        super().__init__()
        self._sampler = sampler or Sampler()
        self._gpu = GpuSampler()
        self._metrics_timer: QTimer | None = None

    @Slot()
    def start(self) -> None:
        self._metrics_timer = QTimer(self)
        self._metrics_timer.setInterval(POLL_INTERVAL_MS)
        self._metrics_timer.timeout.connect(self._emit_metrics)
        self._metrics_timer.timeout.connect(self._emit_gpus)
        self._metrics_timer.start()
        # First chart point before GPU init, so cold start isn't blocked by nvmlInit.
        self._emit_metrics()
        self._gpu.start()
        self._emit_gpus()

    @Slot()
    def stop(self) -> None:
        if self._metrics_timer is not None:
            self._metrics_timer.stop()
        self._gpu.shutdown()

    def set_metrics_interval(self, interval_ms: int) -> None:
        # No @Slot: a queued signal delivers to a plain method by the receiver's
        # thread affinity, and PySide6's Slot stub mistypes the single-int overload.
        if self._metrics_timer is not None:
            self._metrics_timer.setInterval(interval_ms)

    @Slot()
    def _emit_metrics(self) -> None:
        self.sample_ready.emit(self._sampler.sample_metrics())

    @Slot()
    def _emit_gpus(self) -> None:
        self.gpus_ready.emit(self._gpu.sample())


class ProcessWorker(QObject):
    """Slow lane: process list, per-NIC rates, and disk capacity."""

    processes_ready = Signal(object)    # list[ProcessInfo]
    interfaces_ready = Signal(object)   # list[InterfaceRates]
    partitions_ready = Signal(object)   # list[PartitionUsage]

    def __init__(self, sampler: Sampler | None = None) -> None:
        super().__init__()
        self._sampler = sampler or Sampler()
        self._process_timer: QTimer | None = None
        self._partition_timer: QTimer | None = None

    @Slot()
    def start(self) -> None:
        self._process_timer = QTimer(self)
        self._process_timer.setInterval(PROCESS_INTERVAL_MS)
        self._process_timer.timeout.connect(self._emit_interfaces)
        self._process_timer.timeout.connect(self._emit_processes)
        self._process_timer.start()

        self._partition_timer = QTimer(self)
        self._partition_timer.setInterval(PARTITION_INTERVAL_MS)
        self._partition_timer.timeout.connect(self._emit_partitions)
        self._partition_timer.start()

        # Cheap emits first so those panels aren't blank during the slow scan.
        self._emit_interfaces()
        self._emit_partitions()
        self._emit_processes()

    @Slot()
    def stop(self) -> None:
        for timer in (self._process_timer, self._partition_timer):
            if timer is not None:
                timer.stop()

    @Slot()
    def _emit_processes(self) -> None:
        self.processes_ready.emit(self._sampler.sample_processes())

    @Slot()
    def _emit_interfaces(self) -> None:
        self.interfaces_ready.emit(self._sampler.sample_net_interfaces())

    @Slot()
    def _emit_partitions(self) -> None:
        self.partitions_ready.emit(self._sampler.sample_partitions())


class MetricsService(QObject):
    """Owns both threads + workers. Connect to ``metrics`` and ``processes``."""

    _interval_changed = Signal(int)

    def __init__(self, sampler: Sampler | None = None) -> None:
        super().__init__()
        self._fast_thread = QThread()
        self._slow_thread = QThread()
        self._metrics = MetricsWorker(sampler)
        self._processes = ProcessWorker()
        self._metrics.moveToThread(self._fast_thread)
        self._processes.moveToThread(self._slow_thread)
        self._fast_thread.started.connect(self._metrics.start)
        self._slow_thread.started.connect(self._processes.start)
        # Cross-thread, auto-queued: emitting on the UI thread delivers safely
        # to the fast worker thread's event loop.
        self._interval_changed.connect(self._metrics.set_metrics_interval)

    @property
    def metrics(self) -> MetricsWorker:
        return self._metrics

    @property
    def processes(self) -> ProcessWorker:
        return self._processes

    def start(self) -> None:
        self._fast_thread.start()
        self._slow_thread.start()

    def set_metrics_interval(self, interval_ms: int) -> None:
        self._interval_changed.emit(interval_ms)

    def shutdown(self) -> None:
        """Stop timers in each worker's thread, then quit + wait — no exit crash."""
        for worker, thread in (
            (self._metrics, self._fast_thread),
            (self._processes, self._slow_thread),
        ):
            if thread.isRunning():
                # PySide6's stub types `member` as bytes, but str is correct at runtime.
                QMetaObject.invokeMethod(worker, "stop", _BLOCKING)  # type: ignore[call-overload]
                thread.quit()
                thread.wait()
