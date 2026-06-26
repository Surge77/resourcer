"""Streaming chart widgets built on pyqtgraph.

A TimeSeriesChart owns one SeriesStore (a sliding ring buffer per curve) and
redraws by reassigning the curve's data each tick — pyqtgraph's ``setData`` is
cheap and built for exactly this real-time-streaming use.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pyqtgraph as pg

from ..metrics.buffers import SeriesStore
from ..util.constants import HISTORY_POINTS


def configure_theme() -> None:
    """Dark background, light foreground, antialiased lines — global pyqtgraph state."""
    pg.setConfigOption("background", "#1e1e1e")
    pg.setConfigOption("foreground", "#d0d0d0")
    pg.setConfigOptions(antialias=True)


class TimeSeriesChart(pg.PlotWidget):
    def __init__(
        self,
        title: str,
        series: Sequence[tuple[str, str]],
        y_range: tuple[float, float] | None = None,
        maxlen: int = HISTORY_POINTS,
        y_label_format: Callable[[float], str] | None = None,
        legend: bool = False,
    ) -> None:
        super().__init__()
        self.setTitle(title, color="#d0d0d0", size="10pt")
        self.showGrid(x=False, y=True, alpha=0.15)
        self.setMenuEnabled(False)
        self.setMouseEnabled(x=False, y=False)
        self.hideAxis("bottom")
        if y_range is not None:
            self.setYRange(y_range[0], y_range[1])
            self.getViewBox().setLimits(yMin=y_range[0], yMax=y_range[1])
        if legend:
            self.addLegend(offset=(-10, 10), labelTextColor="#9a9a9a")

        self._format = y_label_format
        self._store = SeriesStore([name for name, _ in series], maxlen)
        self._curves = {
            name: self.plot(pen=pg.mkPen(color, width=2), name=name)
            for name, color in series
        }

    def push(self, values: dict[str, float]) -> None:
        for name, value in values.items():
            self._store.append(name, value)
        for name, curve in self._curves.items():
            curve.setData(self._store.x_axis(name), self._store.as_array(name))
        if self._format is not None:
            self._relabel_y_axis()

    def _relabel_y_axis(self) -> None:
        assert self._format is not None
        axis = self.getAxis("left")
        ticks = axis.tickValues(*self.getViewBox().viewRange()[1], axis.size().height())
        labelled = [
            [(value, self._format(value)) for value in spacing[1]] for spacing in ticks
        ]
        axis.setTicks(labelled)


_OVERALL = "overall"
_OVERALL_COLOR = "#ffffff"


class CpuChart(pg.PlotWidget):
    """CPU chart: a bold overall line over thin per-core lines.

    The core count is unknown until the first sample arrives, so curves are
    built lazily on the first ``push``.
    """

    def __init__(self, maxlen: int = HISTORY_POINTS) -> None:
        super().__init__()
        self.setTitle("CPU %  (overall + per-core)", color="#d0d0d0", size="10pt")
        self.showGrid(x=False, y=True, alpha=0.15)
        self.setMenuEnabled(False)
        self.setMouseEnabled(x=False, y=False)
        self.hideAxis("bottom")
        self.setYRange(0.0, 100.0)
        self.getViewBox().setLimits(yMin=0.0, yMax=100.0)

        self._maxlen = maxlen
        self._store: SeriesStore | None = None
        self._curves: dict[str, pg.PlotDataItem] = {}

    def _build(self, core_count: int) -> None:
        names = [_OVERALL] + [f"core{i}" for i in range(core_count)]
        self._store = SeriesStore(names, self._maxlen)
        for i in range(core_count):
            color = pg.intColor(i, hues=max(core_count, 1), alpha=140)
            self._curves[f"core{i}"] = self.plot(pen=pg.mkPen(color, width=1))
        # Draw overall last so it sits on top.
        self._curves[_OVERALL] = self.plot(pen=pg.mkPen(_OVERALL_COLOR, width=2))

    def push(self, overall: float, per_core: Sequence[float]) -> None:
        if self._store is None:
            self._build(len(per_core))
        assert self._store is not None
        self._store.append(_OVERALL, overall)
        for i, value in enumerate(per_core):
            self._store.append(f"core{i}", value)
        for name, curve in self._curves.items():
            curve.setData(self._store.x_axis(name), self._store.as_array(name))
