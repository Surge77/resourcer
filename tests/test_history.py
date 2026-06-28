"""Tests for the sqlite history ring buffer. In-memory + tmp file, no real psutil."""

from __future__ import annotations

import pytest

from resourcer.metrics.history import HistoryRow, HistoryStore
from resourcer.metrics.models import MetricsSample


def _sample(cpu: float = 10.0, mem: float = 20.0) -> MetricsSample:
    return MetricsSample(
        ts=0.0,
        cpu_overall=cpu,
        cpu_per_core=(cpu,),
        mem_percent=mem,
        mem_used=1,
        mem_total=2,
        disk_read_rate=100.0,
        disk_write_rate=200.0,
        net_sent_rate=300.0,
        net_recv_rate=400.0,
    )


def test_record_then_recent_round_trips_values() -> None:
    store = HistoryStore(":memory:")
    store.record(_sample(cpu=42.0, mem=55.0), ts=1000.0)
    rows = store.recent(10)
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, HistoryRow)
    assert row.ts == 1000.0
    assert row.cpu == 42.0
    assert row.mem == 55.0
    assert row.net_recv == 400.0
    store.close()


def test_ring_caps_at_max_rows() -> None:
    store = HistoryStore(":memory:", max_rows=5)
    for i in range(20):
        store.record(_sample(cpu=float(i)), ts=float(i))
    assert store.count() == 5
    # Oldest dropped: only the last five timestamps survive.
    assert [r.ts for r in store.recent(10)] == [19.0, 18.0, 17.0, 16.0, 15.0]
    store.close()


def test_series_returns_metric_values_oldest_first() -> None:
    store = HistoryStore(":memory:")
    for i in range(5):
        store.record(_sample(cpu=float(i * 10)), ts=float(i))
    assert store.series("cpu", 5) == [0.0, 10.0, 20.0, 30.0, 40.0]
    store.close()


def test_series_rejects_unknown_metric() -> None:
    store = HistoryStore(":memory:")
    with pytest.raises(ValueError):
        store.series("cpu; DROP TABLE samples", 5)
    store.close()


def test_between_filters_by_timestamp() -> None:
    store = HistoryStore(":memory:")
    for i in range(10):
        store.record(_sample(), ts=float(i))
    rows = store.between(3.0, 6.0)
    assert [r.ts for r in rows] == [3.0, 4.0, 5.0, 6.0]
    store.close()


def test_persists_across_reopen(tmp_path) -> None:
    db = tmp_path / "history.db"
    store = HistoryStore(db)
    store.record(_sample(cpu=7.0), ts=1.0)
    store.close()

    reopened = HistoryStore(db)
    assert reopened.count() == 1
    assert reopened.recent(1)[0].cpu == 7.0
    reopened.close()
