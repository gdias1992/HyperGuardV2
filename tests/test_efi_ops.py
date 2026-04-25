"""Tests for :mod:`src.services.efi_ops`."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from src.exceptions import EfiError
from src.services.efi_ops import EfiOps


class _Runner:
    def __init__(self, rc: int = 0) -> None:
        self.calls: list[list[str]] = []
        self.rc = rc

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.rc, "", "")


def test_mount_efi_runs_mountvol(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner()
    monkeypatch.setattr("src.services.efi_ops.subprocess.run", runner)
    EfiOps(dry_run=False).mount_efi("Y:")
    assert runner.calls == [["mountvol", "Y:", "/s"]]


def test_mount_efi_rejects_bad_letter() -> None:
    with pytest.raises(EfiError):
        EfiOps(dry_run=False).mount_efi("C:\\evil")


def test_delete_hello_container_runs_certutil(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner()
    monkeypatch.setattr("src.services.efi_ops.subprocess.run", runner)
    result = EfiOps(dry_run=False).delete_hello_container()
    assert runner.calls == [["certutil", "-DeleteHelloContainer"]]
    assert result.requires_reboot is True


def test_stage_secconfig_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(EfiError):
        EfiOps(dry_run=False).stage_secconfig(tmp_path / "nope.efi")


def test_stage_secconfig_dry_run(tmp_path: Path) -> None:
    result = EfiOps(dry_run=True).stage_secconfig(tmp_path / "nope.efi")
    assert result.status.value == "dry_run"
