"""Sampler — thin psutil wrapper that computes rates and returns models.

Pure-ish: the only retained state is the previous I/O counters plus the last
timestamp, used to turn psutil's cumulative counters into per-second rates.
The clock is injectable so rate math is deterministic under test.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import psutil

from .models import InterfaceRates, MetricsSample, PartitionUsage, ProcessInfo

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
        self._prev_nic: dict[str, tuple[int, int]] = {}
        self._prev_nic_ts: float | None = None
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
        conn_counts = _connection_counts()
        out: list[ProcessInfo] = []
        for proc in psutil.process_iter(_PROC_ATTRS):
            try:
                info = proc.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            mem_info = info.get("memory_info")
            pid = int(info["pid"])
            out.append(
                ProcessInfo(
                    pid=pid,
                    name=info.get("name") or "?",
                    cpu_percent=float(info.get("cpu_percent") or 0.0),
                    mem_rss=int(mem_info.rss) if mem_info is not None else 0,
                    status=info.get("status") or "",
                    num_threads=int(info.get("num_threads") or 0),
                    username=_short_username(info.get("username")),
                    create_time=float(info.get("create_time") or 0.0),
                    conn_count=conn_counts.get(pid, 0),
                )
            )
        return out


    def sample_net_interfaces(self) -> list[InterfaceRates]:
        """Per-NIC send/receive rates. Keeps its own previous-counter cache and
        timestamp, independent of the aggregate metrics sample."""
        now = self._clock()
        elapsed = 0.0 if self._prev_nic_ts is None else now - self._prev_nic_ts
        per_nic = psutil.net_io_counters(pernic=True)

        out: list[InterfaceRates] = []
        new_prev: dict[str, tuple[int, int]] = {}
        for name, counters in per_nic.items():
            sent, recv = int(counters.bytes_sent), int(counters.bytes_recv)
            prev_sent, prev_recv = self._prev_nic.get(name, (sent, recv))
            out.append(
                InterfaceRates(
                    name=name,
                    sent_rate=_rate(sent, prev_sent, elapsed),
                    recv_rate=_rate(recv, prev_recv, elapsed),
                )
            )
            new_prev[name] = (sent, recv)

        self._prev_nic = new_prev
        self._prev_nic_ts = now
        return out

    def sample_partitions(self) -> list[PartitionUsage]:
        """Capacity per mounted, physical partition. Skips unreadable drives
        (empty CD/card readers raise ``PermissionError`` on Windows)."""
        out: list[PartitionUsage] = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            out.append(
                PartitionUsage(
                    mountpoint=part.mountpoint,
                    fstype=part.fstype,
                    total=int(usage.total),
                    used=int(usage.used),
                    percent=float(usage.percent),
                )
            )
        return out


def _connection_counts() -> dict[int, int]:
    """Active inet connections per PID, from one syscall. Returns {} if denied.

    A single ``net_connections`` call avoids an N+1 per-process scan. Without
    admin some rows lack a PID (reported as None) — those are skipped, not crashed.
    """
    try:
        conns = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, OSError):
        return {}
    counts: dict[int, int] = {}
    for conn in conns:
        pid = conn.pid
        if pid is not None:
            counts[pid] = counts.get(pid, 0) + 1
    return counts


def _short_username(raw: str | None) -> str:
    """Strip the Windows ``DOMAIN\\`` prefix; leave bare names untouched."""
    if not raw:
        return ""
    return raw.rsplit("\\", 1)[-1]
