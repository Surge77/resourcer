"""Immutable data carriers passed across the worker→UI signal boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricsSample:
    ts: float                      # time.monotonic()
    cpu_overall: float             # 0..100
    cpu_per_core: tuple[float, ...]
    mem_percent: float
    mem_used: int                  # bytes
    mem_total: int                 # bytes
    disk_read_rate: float          # bytes/sec
    disk_write_rate: float         # bytes/sec
    net_sent_rate: float           # bytes/sec
    net_recv_rate: float           # bytes/sec
    mem_available: int = 0         # bytes free for new allocations
    uptime: float = 0.0            # seconds since boot


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    mem_rss: int                   # bytes
    status: str = ""               # running / sleeping / stopped …
    num_threads: int = 0
    username: str = ""
    create_time: float = 0.0       # epoch seconds; 0.0 = unknown
    conn_count: int = 0            # active inet connections owned by the process


@dataclass(frozen=True)
class InterfaceRates:
    name: str
    sent_rate: float               # bytes/sec
    recv_rate: float               # bytes/sec


@dataclass(frozen=True)
class PartitionUsage:
    mountpoint: str
    fstype: str
    total: int                     # bytes
    used: int                      # bytes
    percent: float                 # 0..100


@dataclass(frozen=True)
class GpuInfo:
    index: int
    name: str
    util_percent: float            # 0..100
    mem_used: int                  # bytes
    mem_total: int                 # bytes
    mem_percent: float             # 0..100
    temp_c: float | None = None    # None when the device doesn't report it
    fan_percent: float | None = None
    power_w: float | None = None


@dataclass(frozen=True)
class ProcessSummary:
    """Aggregates derived from one process-list snapshot (pure, UI-agnostic)."""

    count: int
    thread_total: int
    top_cpu: ProcessInfo | None
    top_mem: ProcessInfo | None
