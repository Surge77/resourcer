"""Tests for robust (median/MAD) spike detection — pure, no Qt/psutil."""

from __future__ import annotations

from resourcer.metrics.anomaly import Anomaly, detect_spike


def test_returns_none_below_min_samples() -> None:
    assert detect_spike("cpu", [10.0, 12.0], 99.0, min_samples=5) is None


def test_flags_spike_against_flat_baseline() -> None:
    history = [2.0] * 30
    result = detect_spike("cpu", history, 95.0)
    assert isinstance(result, Anomaly)
    assert result.metric == "cpu"
    assert result.value == 95.0
    assert result.baseline == 2.0
    assert result.deviation > 10.0


def test_normal_variation_not_flagged() -> None:
    history = [40.0, 45.0, 38.0, 42.0, 41.0, 44.0, 39.0, 43.0, 40.0, 42.0]
    assert detect_spike("cpu", history, 46.0) is None


def test_floor_scale_suppresses_tiny_absolute_jump() -> None:
    # Idle metric hovering at 1–2%; a jump to 5% is not an incident.
    history = [1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0]
    assert detect_spike("cpu", history, 5.0, floor_scale=5.0) is None


def test_downward_change_never_flagged() -> None:
    history = [90.0] * 20
    assert detect_spike("cpu", history, 1.0) is None


def test_byte_rate_floor_allows_large_units() -> None:
    history = [1_000.0] * 20
    result = detect_spike("net_recv", history, 50_000_000.0, floor_scale=1_000_000.0)
    assert isinstance(result, Anomaly)
