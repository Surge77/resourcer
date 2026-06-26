"""Tests for util/format.py — pure formatting helpers."""

import pytest

from resourcer.util.format import clamp_percent, human_bytes, human_rate


class TestHumanBytes:
    def test_zero(self) -> None:
        assert human_bytes(0) == "0 B"

    def test_plain_bytes_are_integers(self) -> None:
        assert human_bytes(512) == "512 B"

    def test_kilobytes_one_decimal(self) -> None:
        assert human_bytes(1536) == "1.5 KB"

    def test_exact_kilobyte(self) -> None:
        assert human_bytes(1024) == "1.0 KB"

    def test_megabyte_rollover(self) -> None:
        assert human_bytes(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabyte_rollover(self) -> None:
        assert human_bytes(3 * 1024**3) == "3.0 GB"

    def test_negative_clamps_to_zero(self) -> None:
        assert human_bytes(-100) == "0 B"


class TestHumanRate:
    def test_appends_per_second_suffix(self) -> None:
        assert human_rate(1536) == "1.5 KB/s"

    def test_zero_rate(self) -> None:
        assert human_rate(0) == "0 B/s"


class TestClampPercent:
    @pytest.mark.parametrize(
        "value,expected",
        [(-5.0, 0.0), (0.0, 0.0), (42.5, 42.5), (100.0, 100.0), (150.0, 100.0)],
    )
    def test_bounds(self, value: float, expected: float) -> None:
        assert clamp_percent(value) == expected
