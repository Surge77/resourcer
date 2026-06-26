"""SeriesStore — fixed-window ring buffers per named chart series.

Each series is a ``deque(maxlen=...)``: appending past ``maxlen`` drops the
oldest point in O(1), so charts keep a sliding window with no manual trimming.
"""

from __future__ import annotations

from collections import deque

import numpy as np


class SeriesStore:
    def __init__(self, names: list[str], maxlen: int) -> None:
        self._maxlen = maxlen
        self._series: dict[str, deque[float]] = {
            name: deque(maxlen=maxlen) for name in names
        }

    def append(self, name: str, value: float) -> None:
        self._series[name].append(float(value))

    def as_array(self, name: str) -> np.ndarray:
        return np.fromiter(self._series[name], dtype=float)

    def x_axis(self, name: str) -> np.ndarray:
        return np.arange(len(self._series[name]), dtype=float)

    def length(self, name: str) -> int:
        return len(self._series[name])
