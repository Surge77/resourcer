"""Sustained-threshold alert tracking — pure, no Qt. Unit-tested.

Flags a condition only after a value stays at or above a threshold continuously
for a minimum duration, so a single spike doesn't fire. Dropping below the
threshold resets the streak.
"""

from __future__ import annotations


class SustainedThreshold:
    def __init__(self, threshold: float, duration: float) -> None:
        self._threshold = threshold
        self._duration = duration
        self._since: float | None = None
        self._active = False

    def update(self, value: float, now: float) -> bool:
        """Feed the latest value + timestamp; return whether the alert is active."""
        if value >= self._threshold:
            if self._since is None:
                self._since = now
            self._active = (now - self._since) >= self._duration
        else:
            self._since = None
            self._active = False
        return self._active
