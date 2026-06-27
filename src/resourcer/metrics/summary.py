"""Pure aggregation over a process snapshot — no Qt, no psutil. Unit-tested."""

from __future__ import annotations

from .models import ProcessInfo, ProcessSummary


def summarize(rows: list[ProcessInfo]) -> ProcessSummary:
    """Derive process count, total threads, and the top CPU/memory consumers."""
    if not rows:
        return ProcessSummary(count=0, thread_total=0, top_cpu=None, top_mem=None)
    return ProcessSummary(
        count=len(rows),
        thread_total=sum(p.num_threads for p in rows),
        top_cpu=max(rows, key=lambda p: p.cpu_percent),
        top_mem=max(rows, key=lambda p: p.mem_rss),
    )
