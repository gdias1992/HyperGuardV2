"""Tests for :mod:`src.services.bitlocker_ops`."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from src.exceptions import BitLockerError
from src.services.bitlocker_ops import BitlockerOps


class _Runner:
    def __init__(self, rc: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.calls: list[list[str]] = []
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.rc, self.stdout, self.stderr)


def test_suspend_invokes_manage_bde(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner()
    monkeypatch.setattr("src.services.bitlocker_ops.subprocess.run", runner)
    ops = BitlockerOps(dry_run=False)
    ops.suspend("C:", reboot_count=1)
    assert runner.calls == [
        ["manage-bde", "-protectors", "-disable", "C:", "-rebootcount", "1"]
    ]


def test_suspend_rejects_invalid_drive() -> None:
    ops = BitlockerOps(dry_run=False)
    with pytest.raises(BitLockerError):
        ops.suspend("C:\\Windows")


def test_is_protected_reports_status(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner(stdout="Protection Status: Protection On")
    monkeypatch.setattr("src.services.bitlocker_ops.subprocess.run", runner)
    assert BitlockerOps(dry_run=False).is_protected("C:") is True


def test_dry_run_skips_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner()
    monkeypatch.setattr("src.services.bitlocker_ops.subprocess.run", runner)
    BitlockerOps(dry_run=True).suspend("C:")
    assert runner.calls == []
