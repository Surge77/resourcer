"""Sampler — thin psutil wrapper that computes rates and returns models.

Pure-ish: the only retained state is the previous I/O counters plus the last
timestamp, used to turn psutil's cumulative counters into per-second rates.
The clock is injectable so rate math is deterministic under test.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import psutil

from .models import MetricsSample, ProcessInfo

_PROC_ATTRS = [
    "pid", "name", "cpu_percent", "memory_info",
    "status", "num_threads", "username", "create_time",
]


def _rate(current: float, previous: float, elapsed: float) -> float:
    """Per-second rate from cumulative counters; clamps resets/first sample to 0."""
    if elapsed <= 0:
        return 0.0
    return max(0.0, (current - previous) / elapsed)


class Sampler:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._boot_time = psutil.boot_time()
        self._prev_ts: float | None = None
        self._prev_disk_read = 0
        self._prev_disk_write = 0
        self._prev_net_sent = 0
        self._prev_net_recv = 0
        # Prime cpu_percent so the first real reading is meaningful, not 0.0.
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None, percpu=True)

    def sample_metrics(self) -> MetricsSample:
        now = self._clock()
        elapsed = 0.0 if self._prev_ts is None else now - self._prev_ts

        cpu_overall = float(psutil.cpu_percent(interval=None))
        per_core = tuple(float(c) for c in psutil.cpu_percent(interval=None, percpu=True))

        mem = psutil.virtual_memory()

        disk = psutil.disk_io_counters()
        disk_read = disk.read_bytes if disk is not None else self._prev_disk_read
        disk_write = disk.write_bytes if disk is not None else self._prev_disk_write

        net = psutil.net_io_counters()
        net_sent = net.bytes_sent
        net_recv = net.bytes_recv

        sample = MetricsSample(
            ts=now,
            cpu_overall=cpu_overall,
            cpu_per_core=per_core,
            mem_percent=float(mem.percent),
            mem_used=int(mem.used),
            mem_total=int(mem.total),
            disk_read_rate=_rate(disk_read, self._prev_disk_read, elapsed),
            disk_write_rate=_rate(disk_write, self._prev_disk_write, elapsed),
            net_sent_rate=_rate(net_sent, self._prev_net_sent, elapsed),
            net_recv_rate=_rate(net_recv, self._prev_net_recv, elapsed),
            mem_available=int(getattr(mem, "available", 0)),
            uptime=max(0.0, time.time() - self._boot_time),
        )

        self._prev_ts = now
        self._prev_disk_read = disk_read
        self._prev_disk_write = disk_write
        self._prev_net_sent = net_sent
        self._prev_net_recv = net_recv
        return sample

    def sample_processes(self) -> list[ProcessInfo]:
        out: list[ProcessInfo] = []
        for proc in psutil.process_iter(_PROC_ATTRS):
            try:
                info = proc.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            mem_info = info.get("memory_info")
            out.append(
                ProcessInfo(
                    pid=int(info["pid"]),
                    name=info.get("name") or "?",
                    cpu_percent=float(info.get("cpu_percent") or 0.0),
                    mem_rss=int(mem_info.rss) if mem_info is not None else 0,
                    status=info.get("status") or "",
                    num_threads=int(info.get("num_threads") or 0),
                    username=_short_username(info.get("username")),
                    create_time=float(info.get("create_time") or 0.0),
                )
            )
        return out


def _short_username(raw: str | None) -> str:
    """Strip the Windows ``DOMAIN\\`` prefix; leave bare names untouched."""
    if not raw:
        return ""
    return raw.rsplit("\\", 1)[-1]
