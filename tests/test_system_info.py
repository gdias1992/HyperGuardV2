"""Tests for :mod:`src.services.system_info`."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from src.services.system_info import SystemInfo


class _Registry:
    def __init__(self, value: tuple[str, Any] | None = None) -> None:
        self._value = value

    def read_value(self, _key_path: str, _value_name: str) -> tuple[str, Any] | None:
        return self._value


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SystemInfo, "is_windows", staticmethod(lambda: True))


def test_virtualization_uses_firmware_property(
    windows: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = SystemInfo(registry=_Registry())  # type: ignore[arg-type]
    monkeypatch.setattr(
        info,
        "_processor_info",
        lambda: {"VirtualizationFirmwareEnabled": False},
    )
    monkeypatch.setattr(info, "hypervisor_present", lambda: True)
    monkeypatch.setattr(
        info,
        "_run_powershell",
        lambda _command, timeout=20: pytest.fail("PowerShell fallback was not expected"),
    )

    assert info.virtualization_enabled() is False


def test_virtualization_falls_back_to_canonical_powershell(
    windows: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = SystemInfo(registry=_Registry())  # type: ignore[arg-type]
    commands: list[str] = []

    def run_powershell(command: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(["powershell"], 0, "True\n", "")

    monkeypatch.setattr(info, "_processor_info", lambda: {})
    monkeypatch.setattr(info, "_run_powershell", run_powershell)

    assert info.virtualization_enabled() is True
    assert "VirtualizationFirmwareEnabled" in commands[0]
    assert "ExpandProperty" in commands[0]


def test_smart_app_control_handles_unexpected_registry_value() -> None:
    info = SystemInfo(registry=_Registry(("REG_SZ", "not-a-number")))  # type: ignore[arg-type]

    assert info.smart_app_control_state() == "Unknown"


def test_faceit_installed_checks_all_known_service_names(
    windows: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = SystemInfo(registry=_Registry())  # type: ignore[arg-type]
    checked: list[str] = []

    def sc_query(service_name: str) -> str | None:
        checked.append(service_name)
        return "STATE              : 4  RUNNING" if service_name == "FACEITService" else None

    monkeypatch.setattr(info, "_sc_query", sc_query)

    assert info.faceit_installed() is True
    assert checked == ["FACEIT", "FACEITService"]
