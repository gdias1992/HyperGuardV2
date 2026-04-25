"""Tests for :mod:`src.services.service_ops`."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from src.exceptions import ServiceControlError
from src.services import service_ops
from src.services.service_ops import ServiceOps


class _Runner:
    def __init__(self, rc: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.calls: list[list[str]] = []
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.rc, self.stdout, self.stderr)


@pytest.fixture(autouse=True)
def _no_win32(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the sc.exe fallback path regardless of host OS."""
    monkeypatch.setattr(service_ops, "win32service", None, raising=False)
    monkeypatch.setattr(service_ops, "win32serviceutil", None, raising=False)


def test_stop_uses_sc_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner()
    monkeypatch.setattr(service_ops.subprocess, "run", runner)
    ServiceOps(dry_run=False).stop("FooService")
    assert runner.calls == [["sc", "stop", "FooService"]]


def test_disable_uses_sc_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner()
    monkeypatch.setattr(service_ops.subprocess, "run", runner)
    ServiceOps(dry_run=False).disable("FooService")
    assert runner.calls == [["sc", "config", "FooService", "start=", "disabled"]]


def test_set_start_type_validates_value() -> None:
    with pytest.raises(ServiceControlError):
        ServiceOps(dry_run=False).set_start_type("Foo", "delayed-evil")


def test_disable_faceit_skips_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def exists(_self: Any, _name: str) -> bool:
        return False

    monkeypatch.setattr(ServiceOps, "exists", exists)
    results = ServiceOps(dry_run=False).disable_faceit()
    assert all(r.status.name == "SKIPPED" for r in results)


def test_sc_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _Runner(rc=5, stderr="access denied")
    monkeypatch.setattr(service_ops.subprocess, "run", runner)
    with pytest.raises(ServiceControlError):
        ServiceOps(dry_run=False).stop("FooService")
