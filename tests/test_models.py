"""Tests for metrics/models.py — dataclass construction and immutability."""

import dataclasses

import pytest

from resourcer.metrics.models import MetricsSample, ProcessInfo


def _sample() -> MetricsSample:
    return MetricsSample(
        ts=1.0,
        cpu_overall=23.0,
        cpu_per_core=(10.0, 36.0),
        mem_percent=41.0,
        mem_used=8 * 1024**3,
        mem_total=16 * 1024**3,
        disk_read_rate=1024.0,
        disk_write_rate=2048.0,
        net_sent_rate=512.0,
        net_recv_rate=4096.0,
    )


class TestMetricsSample:
    def test_construction(self) -> None:
        s = _sample()
        assert s.cpu_overall == 23.0
        assert s.cpu_per_core == (10.0, 36.0)

    def test_is_frozen(self) -> None:
        s = _sample()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.cpu_overall = 99.0  # type: ignore[misc]


class TestProcessInfo:
    def test_construction(self) -> None:
        p = ProcessInfo(pid=1234, name="python.exe", cpu_percent=12.5, mem_rss=4096)
        assert p.pid == 1234
        assert p.name == "python.exe"

    def test_is_frozen(self) -> None:
        p = ProcessInfo(pid=1, name="x", cpu_percent=0.0, mem_rss=0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.pid = 2  # type: ignore[misc]
