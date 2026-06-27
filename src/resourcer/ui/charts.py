"""Streaming chart widgets built on pyqtgraph.

A TimeSeriesChart owns one SeriesStore (a sliding ring buffer per curve) and
redraws by reassigning the curve's data each tick — pyqtgraph's ``setData`` is
cheap and built for exactly this real-time-streaming use.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pyqtgraph as pg
from PySide6.QtCore import Qt

from ..metrics.buffers import SeriesStore
from ..util.constants import HISTORY_POINTS


def configure_theme() -> None:
    """Dark background, light foreground, antialiased lines — global pyqtgraph state."""
    pg.setConfigOption("background", "#1e1e1e")
    pg.setConfigOption("foreground", "#d0d0d0")
    pg.setConfigOptions(antialias=True)


_WARN_PEN = pg.mkPen("#d16969", width=1, style=Qt.PenStyle.DashLine)


class TimeSeriesChart(pg.PlotWidget):
    def __init__(
        self,
        title: str,
        series: Sequence[tuple[str, str]],
        y_range: tuple[float, float] | None = None,
        maxlen: int = HISTORY_POINTS,
        y_label_format: Callable[[float], str] | None = None,
        legend: bool = False,
        warn_at: float | None = None,
    ) -> None:
        super().__init__()
        self._base_title = title
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
        if warn_at is not None:
            self.addLine(y=warn_at, pen=_WARN_PEN)

        self._format = y_label_format
        self._store = SeriesStore([name for name, _ in series], maxlen)
        self._curves = {
            name: self.plot(pen=pg.mkPen(color, width=2), name=name)
            for name, color in series
        }

    def set_readout(self, text: str) -> None:
        """Append a live current/peak summary to the chart title."""
        self.setTitle(f"{self._base_title}   {text}", color="#d0d0d0", size="10pt")

    def series_peak(self, name: str) -> float:
        array = self._store.as_array(name)
        return float(array.max()) if array.size else 0.0

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

    def __init__(self, maxlen: int = HISTORY_POINTS, warn_at: float | None = None) -> None:
        super().__init__()
        self._base_title = "CPU %  (overall + per-core)"
        self.setTitle(self._base_title, color="#d0d0d0", size="10pt")
        self.showGrid(x=False, y=True, alpha=0.15)
        self.setMenuEnabled(False)
        self.setMouseEnabled(x=False, y=False)
        self.hideAxis("bottom")
        self.setYRange(0.0, 100.0)
        self.getViewBox().setLimits(yMin=0.0, yMax=100.0)
        if warn_at is not None:
            self.addLine(y=warn_at, pen=_WARN_PEN)

        self._maxlen = maxlen
        self._store: SeriesStore | None = None
        self._curves: dict[str, pg.PlotDataItem] = {}

    def set_readout(self, text: str) -> None:
        self.setTitle(f"{self._base_title}   {text}", color="#d0d0d0", size="10pt")

    def overall_peak(self) -> float:
        if self._store is None:
            return 0.0
        array = self._store.as_array(_OVERALL)
        return float(array.max()) if array.size else 0.0

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
