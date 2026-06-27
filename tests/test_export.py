"""Tests for metrics/export.py — pure CSV serialization."""

from __future__ import annotations

from resourcer.metrics.export import processes_to_csv
from resourcer.metrics.models import ProcessInfo


def test_empty_snapshot_is_header_only() -> None:
    assert processes_to_csv([]) == (
        "pid,name,cpu_percent,mem_rss_bytes,status,num_threads,username,create_time\n"
    )


def test_row_is_serialized() -> None:
    rows = [ProcessInfo(pid=7, name="svc.exe", cpu_percent=12.34, mem_rss=2048,
                        status="running", num_threads=4, username="Tejas",
                        create_time=1700.9)]
    out = processes_to_csv(rows).splitlines()
    assert out[1] == "7,svc.exe,12.3,2048,running,4,Tejas,1700"


def test_name_with_comma_is_quoted() -> None:
    rows = [ProcessInfo(pid=1, name="a,b.exe", cpu_percent=0.0, mem_rss=0)]
    assert '"a,b.exe"' in processes_to_csv(rows)
