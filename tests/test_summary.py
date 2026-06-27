"""Tests for metrics/summary.py — pure aggregation over a process snapshot."""

from __future__ import annotations

from resourcer.metrics.models import ProcessInfo
from resourcer.metrics.summary import summarize


def _proc(pid: int, cpu: float, rss: int, threads: int = 1) -> ProcessInfo:
    return ProcessInfo(pid=pid, name=f"p{pid}", cpu_percent=cpu, mem_rss=rss,
                       num_threads=threads)


class TestSummarize:
    def test_empty_snapshot(self) -> None:
        summary = summarize([])
        assert summary.count == 0
        assert summary.thread_total == 0
        assert summary.top_cpu is None
        assert summary.top_mem is None

    def test_counts_and_thread_total(self) -> None:
        rows = [_proc(1, 5.0, 100, threads=3), _proc(2, 1.0, 200, threads=4)]
        summary = summarize(rows)
        assert summary.count == 2
        assert summary.thread_total == 7

    def test_top_cpu_and_top_mem_can_differ(self) -> None:
        cpu_hog = _proc(1, 90.0, 100)
        mem_hog = _proc(2, 2.0, 9000)
        summary = summarize([cpu_hog, mem_hog])
        assert summary.top_cpu is cpu_hog
        assert summary.top_mem is mem_hog
