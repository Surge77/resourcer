"""Tests for metrics/buffers.py — SeriesStore ring buffers + numpy export."""

import numpy as np
import pytest

from resourcer.metrics.buffers import SeriesStore


class TestSeriesStore:
    def test_unknown_series_rejected(self) -> None:
        store = SeriesStore(["cpu"], maxlen=3)
        with pytest.raises(KeyError):
            store.append("gpu", 1.0)

    def test_append_and_export(self) -> None:
        store = SeriesStore(["cpu"], maxlen=5)
        for v in (1.0, 2.0, 3.0):
            store.append("cpu", v)
        np.testing.assert_array_equal(store.as_array("cpu"), np.array([1.0, 2.0, 3.0]))

    def test_window_drops_oldest_past_maxlen(self) -> None:
        store = SeriesStore(["cpu"], maxlen=3)
        for v in (1.0, 2.0, 3.0, 4.0):
            store.append("cpu", v)
        np.testing.assert_array_equal(store.as_array("cpu"), np.array([2.0, 3.0, 4.0]))

    def test_independent_series(self) -> None:
        store = SeriesStore(["cpu", "mem"], maxlen=3)
        store.append("cpu", 1.0)
        store.append("mem", 9.0)
        assert store.as_array("cpu").tolist() == [1.0]
        assert store.as_array("mem").tolist() == [9.0]

    def test_x_axis_matches_length(self) -> None:
        store = SeriesStore(["cpu"], maxlen=3)
        store.append("cpu", 1.0)
        store.append("cpu", 2.0)
        np.testing.assert_array_equal(store.x_axis("cpu"), np.array([0.0, 1.0]))

    def test_empty_series_exports_empty_array(self) -> None:
        store = SeriesStore(["cpu"], maxlen=3)
        assert store.as_array("cpu").size == 0

    def test_len_reports_current_points(self) -> None:
        store = SeriesStore(["cpu"], maxlen=3)
        store.append("cpu", 1.0)
        assert store.length("cpu") == 1
