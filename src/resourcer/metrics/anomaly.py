"""Robust spike detection — pure, no Qt/psutil. Unit-tested.

Uses the median and the Median Absolute Deviation (MAD) rather than mean/stdev so
a single in-progress spike doesn't inflate the baseline it is being judged
against. ``deviation`` is a robust z-score: how many std-equivalents above the
median the current value sits. Only upward spikes are reported.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

# Scales MAD to be comparable to a standard deviation for a normal distribution.
_MAD_TO_STD = 1.4826


@dataclass(frozen=True)
class Anomaly:
    metric: str
    value: float
    baseline: float       # median of the recent history
    deviation: float      # robust z-score of value above baseline


def detect_spike(
    metric: str,
    history: Sequence[float],
    current: float,
    *,
    k: float = 3.5,
    min_samples: int = 10,
    floor_scale: float = 1.0,
) -> Anomaly | None:
    """Flag ``current`` as a spike vs ``history`` when it is ``k``+ robust-std above.

    ``floor_scale`` puts a lower bound on the scale so a flat baseline (e.g. an
    idle metric) doesn't make every tiny absolute jump look infinitely
    significant. It is unit-matched to the metric: ~1 for percentages, ~1e6 for
    byte-rate series.
    """
    if len(history) < min_samples:
        return None
    median = statistics.median(history)
    mad = statistics.median([abs(value - median) for value in history])
    scale = max(mad * _MAD_TO_STD, floor_scale)
    deviation = (current - median) / scale
    if deviation >= k:
        return Anomaly(metric, current, median, deviation)
    return None
