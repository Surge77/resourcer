"""Process control actions beyond plain terminate: suspend, resume, kill-tree.

Kept out of the UI so the tree-walking and error mapping are unit tested without
a Qt event loop. Each function returns an ``ActionOutcome`` the UI maps to a
friendly message — never a raw psutil exception.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto

import psutil

from .killer import KillOutcome, terminate_process


class ActionOutcome(Enum):
    OK = auto()
    ALREADY_GONE = auto()
    ACCESS_DENIED = auto()
    ERROR = auto()


_KILL_MAP = {
    KillOutcome.TERMINATED: ActionOutcome.OK,
    KillOutcome.ALREADY_GONE: ActionOutcome.ALREADY_GONE,
    KillOutcome.ACCESS_DENIED: ActionOutcome.ACCESS_DENIED,
    KillOutcome.ERROR: ActionOutcome.ERROR,
}
# Worst-case precedence when collapsing many outcomes into one tree result.
_SEVERITY = (ActionOutcome.ACCESS_DENIED, ActionOutcome.ERROR, ActionOutcome.OK)


def collect_tree_pids(pid: int) -> list[int]:
    """Return ``pid`` followed by all descendant pids (children, recursive).

    Empty if the process is already gone; just ``[pid]`` if descendants can't be
    enumerated due to permissions.
    """
    try:
        proc = psutil.Process(pid)
        descendants = proc.children(recursive=True)
    except psutil.NoSuchProcess:
        return []
    except (psutil.AccessDenied, psutil.Error):
        return [pid]
    return [pid] + [child.pid for child in descendants]


def terminate_one(pid: int) -> ActionOutcome:
    """Terminate a single process (no descendants), as an ``ActionOutcome``."""
    return _KILL_MAP[terminate_process(pid)]


def terminate_tree(pid: int) -> ActionOutcome:
    """Terminate a process and every descendant, children first, parent last."""
    pids = collect_tree_pids(pid)
    if not pids:
        return ActionOutcome.ALREADY_GONE
    outcomes = {_KILL_MAP[terminate_process(p)] for p in reversed(pids)}
    for outcome in _SEVERITY:
        if outcome in outcomes:
            return outcome
    return ActionOutcome.ALREADY_GONE


def suspend_process(pid: int) -> ActionOutcome:
    """Pause a process (freeze all its threads)."""
    return _run(pid, lambda proc: proc.suspend())


def resume_process(pid: int) -> ActionOutcome:
    """Resume a previously suspended process."""
    return _run(pid, lambda proc: proc.resume())


def _run(pid: int, op: Callable[[psutil.Process], None]) -> ActionOutcome:
    try:
        op(psutil.Process(pid))
        return ActionOutcome.OK
    except psutil.NoSuchProcess:
        return ActionOutcome.ALREADY_GONE
    except psutil.AccessDenied:
        return ActionOutcome.ACCESS_DENIED
    except (OSError, psutil.Error):
        return ActionOutcome.ERROR
