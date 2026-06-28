"""Insight coordinator — bridges live samples, persistent history, and detection.

Each sample is checked for a spike against the recent persisted history *before*
it is itself recorded (so the current value is judged against its own past, not
included in its baseline). The strongest spike across metrics is returned for the
UI to surface. No Qt here — unit-tested with an in-memory store.
"""

from __future__ import annotations

from .anomaly import Anomaly, detect_spike
from .history import HistoryStore
from .models import MetricsSample

# Detection window (samples) and per-metric floor scale, unit-matched: percentage
# metrics floor at 1.0, byte-rate metrics at 1 MB/s so idle noise stays quiet.
_WINDOW = 120
_PERCENT_FLOOR = 1.0
_RATE_FLOOR = 1_000_000.0

# metric column → (sample attribute, floor scale, friendly label)
_TRACKED: tuple[tuple[str, str, float, str], ...] = (
    ("cpu", "cpu_overall", _PERCENT_FLOOR, "CPU"),
    ("mem", "mem_percent", _PERCENT_FLOOR, "memory"),
    ("disk_read", "disk_read_rate", _RATE_FLOOR, "disk read"),
    ("disk_write", "disk_write_rate", _RATE_FLOOR, "disk write"),
    ("net_recv", "net_recv_rate", _RATE_FLOOR, "network down"),
    ("net_sent", "net_sent_rate", _RATE_FLOOR, "network up"),
)

_LABELS = {metric: label for metric, _, _, label in _TRACKED}


class InsightTracker:
    def __init__(self, store: HistoryStore, window: int = _WINDOW) -> None:
        self._store = store
        self._window = window

    def observe(self, sample: MetricsSample, *, ts: float | None = None) -> Anomaly | None:
        """Detect the strongest spike vs history, then persist the sample."""
        strongest: Anomaly | None = None
        for metric, attr, floor, _ in _TRACKED:
            history = self._store.series(metric, self._window)
            found = detect_spike(
                metric, history, getattr(sample, attr), floor_scale=floor
            )
            if found is not None and (strongest is None or found.deviation > strongest.deviation):
                strongest = found
        self._store.record(sample, ts=ts)
        return strongest

    @staticmethod
    def label(metric: str) -> str:
        return _LABELS.get(metric, metric)
