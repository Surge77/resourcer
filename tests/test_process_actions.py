"""Tests for metrics/process_actions.py — psutil monkeypatched at the boundary."""

from __future__ import annotations

import psutil
import pytest

from resourcer.metrics import process_actions as pa
from resourcer.metrics.killer import KillOutcome
from resourcer.metrics.process_actions import (
    ActionOutcome,
    collect_tree_pids,
    resume_process,
    suspend_process,
    terminate_one,
    terminate_tree,
)


class FakeProc:
    """Minimal psutil.Process stand-in recording control calls."""

    def __init__(self, pid: int, children: list["FakeProc"] | None = None,
                 raise_on: str | None = None, exc: type[Exception] = psutil.AccessDenied):
        self.pid = pid
        self._children = children or []
        self._raise_on = raise_on
        self._exc = exc
        self.calls: list[str] = []

    def children(self, recursive: bool = False) -> list["FakeProc"]:
        if self._raise_on == "children":
            raise self._exc(self.pid)
        return self._children

    def suspend(self) -> None:
        self._maybe_raise("suspend")

    def resume(self) -> None:
        self._maybe_raise("resume")

    def _maybe_raise(self, op: str) -> None:
        if self._raise_on == op:
            raise self._exc(self.pid)
        self.calls.append(op)


def _patch_process(monkeypatch: pytest.MonkeyPatch, proc: FakeProc) -> None:
    monkeypatch.setattr(psutil, "Process", lambda pid: proc)


class TestCollectTreePids:
    def test_returns_pid_and_descendants(self, monkeypatch: pytest.MonkeyPatch) -> None:
        root = FakeProc(100, children=[FakeProc(101), FakeProc(102)])
        _patch_process(monkeypatch, root)
        assert collect_tree_pids(100) == [100, 101, 102]

    def test_no_such_process_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(psutil, "Process", _raiser(psutil.NoSuchProcess))
        assert collect_tree_pids(999) == []

    def test_access_denied_returns_self_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_process(monkeypatch, FakeProc(100, raise_on="children"))
        assert collect_tree_pids(100) == [100]


class TestTerminateTree:
    def test_terminates_children_before_parent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        root = FakeProc(100, children=[FakeProc(101), FakeProc(102)])
        _patch_process(monkeypatch, root)
        order: list[int] = []
        monkeypatch.setattr(
            pa, "terminate_process",
            lambda pid: (order.append(pid), KillOutcome.TERMINATED)[1],
        )
        assert terminate_tree(100) is ActionOutcome.OK
        assert order == [102, 101, 100]  # deepest first, parent last

    def test_access_denied_dominates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_process(monkeypatch, FakeProc(100, children=[FakeProc(101)]))
        monkeypatch.setattr(
            pa, "terminate_process",
            lambda pid: KillOutcome.ACCESS_DENIED if pid == 100 else KillOutcome.TERMINATED,
        )
        assert terminate_tree(100) is ActionOutcome.ACCESS_DENIED

    def test_empty_tree_is_already_gone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(psutil, "Process", _raiser(psutil.NoSuchProcess))
        assert terminate_tree(999) is ActionOutcome.ALREADY_GONE


class TestTerminateOne:
    @pytest.mark.parametrize(
        "kill,expected",
        [
            (KillOutcome.TERMINATED, ActionOutcome.OK),
            (KillOutcome.ALREADY_GONE, ActionOutcome.ALREADY_GONE),
            (KillOutcome.ACCESS_DENIED, ActionOutcome.ACCESS_DENIED),
            (KillOutcome.ERROR, ActionOutcome.ERROR),
        ],
    )
    def test_maps_kill_outcome(
        self, monkeypatch: pytest.MonkeyPatch, kill: KillOutcome, expected: ActionOutcome
    ) -> None:
        monkeypatch.setattr(pa, "terminate_process", lambda pid: kill)
        assert terminate_one(42) is expected


class TestSuspendResume:
    def test_suspend_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        proc = FakeProc(100)
        _patch_process(monkeypatch, proc)
        assert suspend_process(100) is ActionOutcome.OK
        assert proc.calls == ["suspend"]

    def test_resume_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        proc = FakeProc(100)
        _patch_process(monkeypatch, proc)
        assert resume_process(100) is ActionOutcome.OK
        assert proc.calls == ["resume"]

    def test_suspend_access_denied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_process(monkeypatch, FakeProc(100, raise_on="suspend"))
        assert suspend_process(100) is ActionOutcome.ACCESS_DENIED

    def test_suspend_no_such_process(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_process(monkeypatch, FakeProc(100, raise_on="suspend", exc=psutil.NoSuchProcess))
        assert suspend_process(100) is ActionOutcome.ALREADY_GONE


def _raiser(exc: type[Exception]):
    def _factory(pid: int):
        raise exc(pid)
    return _factory
