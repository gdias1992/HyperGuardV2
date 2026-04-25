"""Tests for :mod:`src.services.bcd_ops`."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from src.exceptions import BcdError
from src.services.bcd_ops import BcdOps


class _Runner:
    """Tiny wrapper collecting calls and returning configurable results."""

    def __init__(self, rc: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.calls: list[list[str]] = []
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.rc, self.stdout, self.stderr)


def test_set_hypervisor_launch_off(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner()
    monkeypatch.setattr("src.services.bcd_ops.subprocess.run", runner)
    ops = BcdOps(dry_run=False)
    result = ops.set_hypervisor_launch("off")
    assert runner.calls == [["bcdedit", "/set", "hypervisorlaunchtype", "off"]]
    assert result.requires_reboot is True


def test_set_hypervisor_launch_rejects_unsafe() -> None:
    ops = BcdOps(dry_run=False)
    with pytest.raises(BcdError):
        ops.set_hypervisor_launch("evil")


def test_dry_run_does_not_invoke_bcdedit(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner()
    monkeypatch.setattr("src.services.bcd_ops.subprocess.run", runner)
    ops = BcdOps(dry_run=True)
    ops.set_hypervisor_launch("off")
    assert runner.calls == []


def test_is_hypervisor_launch_off_parses_output(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner(
        stdout=(
            "Windows Boot Manager\n"
            "---------------------\n"
            "hypervisorlaunchtype    Off\n"
        )
    )
    monkeypatch.setattr("src.services.bcd_ops.subprocess.run", runner)
    ops = BcdOps(dry_run=False)
    assert ops.is_hypervisor_launch_off() is True


def test_bcdedit_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner(rc=1, stderr="access denied")
    monkeypatch.setattr("src.services.bcd_ops.subprocess.run", runner)
    ops = BcdOps(dry_run=False)
    with pytest.raises(BcdError):
        ops.set_hypervisor_launch("off")
