"""Serialize a process snapshot to CSV text — pure, unit-tested."""

from __future__ import annotations

import csv
import io

from .models import ProcessInfo

_HEADER = [
    "pid", "name", "cpu_percent", "mem_rss_bytes",
    "status", "num_threads", "username", "create_time",
]


def processes_to_csv(rows: list[ProcessInfo]) -> str:
    """Render rows as RFC-4180 CSV (always with a header line, ``\\n`` endings)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_HEADER)
    for proc in rows:
        writer.writerow([
            proc.pid,
            proc.name,
            f"{proc.cpu_percent:.1f}",
            proc.mem_rss,
            proc.status,
            proc.num_threads,
            proc.username,
            int(proc.create_time),
        ])
    return buffer.getvalue()
