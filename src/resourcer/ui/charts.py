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
