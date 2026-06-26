"""Tests for metrics/killer.py — terminate logic with psutil monkeypatched."""

from __future__ import annotations

import psutil
import pytest

from resourcer.metrics.killer import KillOutcome, terminate_process


class FakeProc:
    def __init__(self, *, wait_raises: bool = False) -> None:
        self.terminated = False
        self.killed = False
        self._wait_raises = wait_raises

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        if self._wait_raises:
            raise psutil.TimeoutExpired(timeout or 0.0)
        return 0


def _patch_process(monkeypatch: pytest.MonkeyPatch, factory) -> None:
    monkeypatch.setattr(psutil, "Process", factory)


class TestTerminateProcess:
    def test_graceful_terminate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        proc = FakeProc()
        _patch_process(monkeypatch, lambda pid: proc)
        assert terminate_process(123) is KillOutcome.TERMINATED
        assert proc.terminated is True
        assert proc.killed is False

    def test_force_kill_after_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        proc = FakeProc(wait_raises=True)
        _patch_process(monkeypatch, lambda pid: proc)
        assert terminate_process(123) is KillOutcome.TERMINATED
        assert proc.killed is True

    def test_already_gone_is_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def factory(pid: int):
            raise psutil.NoSuchProcess(pid)

        _patch_process(monkeypatch, factory)
        assert terminate_process(123) is KillOutcome.ALREADY_GONE

    def test_access_denied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def factory(pid: int):
            raise psutil.AccessDenied(pid)

        _patch_process(monkeypatch, factory)
        assert terminate_process(123) is KillOutcome.ACCESS_DENIED

    def test_access_denied_on_terminate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Denied(FakeProc):
            def terminate(self) -> None:
                raise psutil.AccessDenied(1)

        _patch_process(monkeypatch, lambda pid: Denied())
        assert terminate_process(123) is KillOutcome.ACCESS_DENIED

    def test_unexpected_error_maps_to_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def factory(pid: int):
            raise psutil.Error()

        _patch_process(monkeypatch, factory)
        assert terminate_process(123) is KillOutcome.ERROR
