"""Right-click process actions: end task / tree, suspend, resume, copy, reveal.

OS-touching calls (psutil control, clipboard, opening Explorer) live here, off
the table model, so the model stays a pure view of the data. Every action maps
its ActionOutcome to a friendly dialog — never a raw exception.
"""

from __future__ import annotations

import os

import psutil
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QMenu, QMessageBox, QWidget

from ..metrics.models import ProcessInfo
from ..metrics.process_actions import (
    ActionOutcome,
    resume_process,
    suspend_process,
    terminate_one,
    terminate_tree,
)
from .process_detail import ProcessDetailDialog

_DESTRUCTIVE = {ActionOutcome.ACCESS_DENIED, ActionOutcome.ERROR}


class ProcessActions:
    """Builds the context menu and runs each action against a process."""

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent

    def menu_for(self, proc: ProcessInfo) -> QMenu:
        menu = QMenu(self._parent)
        self._add(menu, "Details…", lambda: self.show_details(proc))
        menu.addSeparator()
        self._add(menu, "End task", lambda: self.end_task(proc))
        self._add(menu, "End process tree", lambda: self.end_tree(proc))
        menu.addSeparator()
        self._add(menu, "Suspend", lambda: self._simple(suspend_process, proc, "suspend"))
        self._add(menu, "Resume", lambda: self._simple(resume_process, proc, "resume"))
        menu.addSeparator()
        self._add(menu, "Copy PID", lambda: self.copy_pid(proc))
        self._add(menu, "Open file location", lambda: self.open_location(proc))
        return menu

    def _add(self, menu: QMenu, label: str, handler) -> None:
        action = QAction(label, menu)
        action.triggered.connect(handler)
        menu.addAction(action)

    def end_task(self, proc: ProcessInfo) -> None:
        if self._confirm(f"End “{proc.name}” (PID {proc.pid})?"):
            self._report(terminate_one(proc.pid), proc, "end")

    def end_tree(self, proc: ProcessInfo) -> None:
        if self._confirm(f"End “{proc.name}” and all its child processes?"):
            self._report(terminate_tree(proc.pid), proc, "end")

    def _simple(self, action, proc: ProcessInfo, verb: str) -> None:
        self._report(action(proc.pid), proc, verb)

    def show_details(self, proc: ProcessInfo) -> None:
        ProcessDetailDialog(proc.pid, self._parent).exec()

    def copy_pid(self, proc: ProcessInfo) -> None:
        QGuiApplication.clipboard().setText(str(proc.pid))

    def open_location(self, proc: ProcessInfo) -> None:
        try:
            exe = psutil.Process(proc.pid).exe()
        except (psutil.Error, OSError):
            exe = ""
        if exe and os.path.isfile(exe):
            os.startfile(os.path.dirname(exe))  # noqa: S606 — OS path, not user input
        else:
            QMessageBox.information(
                self._parent, "Open file location",
                f"The executable path for “{proc.name}” is not available.",
            )

    def _confirm(self, question: str) -> bool:
        box = QMessageBox(self._parent)
        box.setWindowTitle("Confirm")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(question)
        box.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _report(self, outcome: ActionOutcome, proc: ProcessInfo, verb: str) -> None:
        if outcome not in _DESTRUCTIVE:
            return  # OK / ALREADY_GONE — nothing to say
        if outcome is ActionOutcome.ACCESS_DENIED:
            text = f"Cannot {verb} “{proc.name}” — it needs administrator rights."
        else:
            text = f"Could not {verb} “{proc.name}”. Please try again."
        QMessageBox.information(self._parent, "Process action", text)
