"""Persistent metric history — a sqlite ring buffer keyed on wall-clock time.

Unlike the in-memory chart buffers (monotonic, 60s), this survives restarts and
spans hours/days so the UI can answer "what spiked, and when". Each insert
trims the table back to ``max_rows`` newest rows by primary key — O(1)-ish, no
manual sweep. Metric column names are validated against a whitelist before being
interpolated into SQL.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from .models import MetricsSample

# Column name → MetricsSample attribute. The keys double as the SQL-safe whitelist.
_METRICS: dict[str, str] = {
    "cpu": "cpu_overall",
    "mem": "mem_percent",
    "disk_read": "disk_read_rate",
    "disk_write": "disk_write_rate",
    "net_sent": "net_sent_rate",
    "net_recv": "net_recv_rate",
}

# 24h at 1Hz — bounded so an always-on dashboard can't grow the DB without limit.
DEFAULT_MAX_ROWS = 86_400


@dataclass(frozen=True)
class HistoryRow:
    ts: float
    cpu: float
    mem: float
    disk_read: float
    disk_write: float
    net_sent: float
    net_recv: float


class HistoryStore:
    def __init__(self, path: Union[str, Path] = ":memory:", max_rows: int = DEFAULT_MAX_ROWS) -> None:
        self._max_rows = max(1, max_rows)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS samples ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, "
            "cpu REAL, mem REAL, disk_read REAL, disk_write REAL, "
            "net_sent REAL, net_recv REAL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts)")
        self._conn.commit()

    def record(self, sample: MetricsSample, *, ts: float | None = None) -> None:
        """Persist one sample at wall-clock ``ts`` (defaults to now), then trim."""
        wall_ts = time.time() if ts is None else ts
        self._conn.execute(
            "INSERT INTO samples (ts, cpu, mem, disk_read, disk_write, net_sent, net_recv)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                wall_ts,
                sample.cpu_overall,
                sample.mem_percent,
                sample.disk_read_rate,
                sample.disk_write_rate,
                sample.net_sent_rate,
                sample.net_recv_rate,
            ),
        )
        self._conn.execute(
            "DELETE FROM samples WHERE id <= (SELECT MAX(id) - ? FROM samples)",
            (self._max_rows,),
        )
        self._conn.commit()

    def recent(self, limit: int) -> list[HistoryRow]:
        """Most recent rows, newest first."""
        cursor = self._conn.execute(
            "SELECT ts, cpu, mem, disk_read, disk_write, net_sent, net_recv "
            "FROM samples ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [HistoryRow(*row) for row in cursor.fetchall()]

    def series(self, metric: str, limit: int) -> list[float]:
        """Values for one metric, oldest first (chart-ready order)."""
        if metric not in _METRICS:
            raise ValueError(f"unknown metric: {metric!r}")
        cursor = self._conn.execute(
            f"SELECT {metric} FROM samples ORDER BY id DESC LIMIT ?",  # noqa: S608 - metric whitelisted
            (limit,),
        )
        return [row[0] for row in reversed(cursor.fetchall())]

    def between(self, start_ts: float, end_ts: float) -> list[HistoryRow]:
        """Rows with ``start_ts <= ts <= end_ts``, oldest first."""
        cursor = self._conn.execute(
            "SELECT ts, cpu, mem, disk_read, disk_write, net_sent, net_recv "
            "FROM samples WHERE ts >= ? AND ts <= ? ORDER BY ts ASC",
            (start_ts, end_ts),
        )
        return [HistoryRow(*row) for row in cursor.fetchall()]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0])

    def close(self) -> None:
        self._conn.close()
