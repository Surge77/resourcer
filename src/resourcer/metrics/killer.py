"""Process termination — graceful terminate, force kill on timeout, safe errors.

Kept separate from the UI so the terminate/kill/error-mapping logic is unit
tested without a Qt event loop. The UI layer maps the returned outcome to a
user-facing message — never a raw exception.
"""

from __future__ import annotations

from enum import Enum, auto

import psutil

from ..util.constants import KILL_WAIT_SECONDS


class KillOutcome(Enum):
    TERMINATED = auto()      # process is gone (terminated or force-killed)
    ALREADY_GONE = auto()    # nothing to do — already exited
    ACCESS_DENIED = auto()   # needs elevation
    ERROR = auto()           # unexpected failure


def terminate_process(pid: int) -> KillOutcome:
    """Terminate ``pid``; force-kill if it doesn't exit within the grace window."""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=KILL_WAIT_SECONDS)
        except psutil.TimeoutExpired:
            proc.kill()
        return KillOutcome.TERMINATED
    except psutil.NoSuchProcess:
        return KillOutcome.ALREADY_GONE
    except psutil.AccessDenied:
        return KillOutcome.ACCESS_DENIED
    except (OSError, psutil.Error):
        return KillOutcome.ERROR
