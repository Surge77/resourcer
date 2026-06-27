"""Tests for metrics/alerts.py — sustained-threshold state machine (pure)."""

from __future__ import annotations

from resourcer.metrics.alerts import SustainedThreshold


def _watch() -> SustainedThreshold:
    return SustainedThreshold(threshold=90.0, duration=10.0)


class TestSustainedThreshold:
    def test_below_threshold_is_inactive(self) -> None:
        watch = _watch()
        assert watch.update(50.0, now=0.0) is False
        assert watch.update(89.9, now=20.0) is False

    def test_above_but_not_long_enough_is_inactive(self) -> None:
        watch = _watch()
        watch.update(95.0, now=0.0)
        assert watch.update(95.0, now=9.0) is False  # only 9s elapsed

    def test_sustained_breach_activates(self) -> None:
        watch = _watch()
        watch.update(95.0, now=0.0)
        assert watch.update(95.0, now=10.0) is True   # 10s continuous

    def test_dropping_below_resets_the_timer(self) -> None:
        watch = _watch()
        watch.update(95.0, now=0.0)
        watch.update(50.0, now=5.0)                   # breaks the streak
        assert watch.update(95.0, now=9.0) is False   # new streak starts at t=9
        assert watch.update(95.0, now=19.0) is True   # 10s from the restart

    def test_first_breach_at_exact_now_is_inactive(self) -> None:
        watch = _watch()
        assert watch.update(95.0, now=100.0) is False  # streak just started
