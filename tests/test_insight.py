"""Tests for InsightTracker — records history and reports the strongest spike."""

from __future__ import annotations

from resourcer.metrics.history import HistoryStore
from resourcer.metrics.insight import InsightTracker
from resourcer.metrics.models import MetricsSample


def _sample(cpu: float = 5.0, mem: float = 20.0, net_recv: float = 1000.0) -> MetricsSample:
    return MetricsSample(
        ts=0.0,
        cpu_overall=cpu,
        cpu_per_core=(cpu,),
        mem_percent=mem,
        mem_used=1,
        mem_total=2,
        disk_read_rate=0.0,
        disk_write_rate=0.0,
        net_sent_rate=0.0,
        net_recv_rate=net_recv,
    )


def test_no_spike_returns_none_and_still_records() -> None:
    store = HistoryStore(":memory:")
    tracker = InsightTracker(store)
    for i in range(20):
        assert tracker.observe(_sample(cpu=5.0), ts=float(i)) is None
    assert store.count() == 20
    store.close()


def test_detects_cpu_spike_after_calm_baseline() -> None:
    store = HistoryStore(":memory:")
    tracker = InsightTracker(store)
    for i in range(20):
        tracker.observe(_sample(cpu=5.0), ts=float(i))
    spike = tracker.observe(_sample(cpu=98.0), ts=100.0)
    assert spike is not None
    assert spike.metric == "cpu"
    store.close()


def test_reports_strongest_metric_when_multiple_spike() -> None:
    store = HistoryStore(":memory:")
    tracker = InsightTracker(store)
    for i in range(20):
        tracker.observe(_sample(cpu=5.0, mem=20.0), ts=float(i))
    spike = tracker.observe(_sample(cpu=60.0, mem=99.0), ts=100.0)
    assert spike is not None
    # mem jump (20→99) is a larger robust deviation than cpu (5→60) here.
    assert spike.metric == "mem"
    store.close()
