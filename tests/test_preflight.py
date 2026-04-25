"""Tests for :mod:`src.services.preflight`."""

from __future__ import annotations

from src.services.preflight import Preflight, PreflightReport


class _FakeSystemInfo:
    def __init__(
        self,
        virt: bool = True,
        wmi: bool = True,
        sac: str = "Off",
    ) -> None:
        self._virt = virt
        self._wmi = wmi
        self._sac = sac

    def virtualization_enabled(self) -> bool:
        return self._virt

    def wmi_healthy(self) -> bool:
        return self._wmi

    def smart_app_control_state(self) -> str:
        return self._sac


def test_report_ok_requires_admin_wmi_virt(monkeypatch) -> None:
    monkeypatch.setattr(Preflight, "is_admin", staticmethod(lambda: True))
    monkeypatch.setattr(Preflight, "os_build", staticmethod(lambda: 22000))
    report = Preflight(_FakeSystemInfo()).run()
    assert isinstance(report, PreflightReport)
    assert report.ok is True
    assert report.warnings == []


def test_warnings_populate_when_checks_fail(monkeypatch) -> None:
    monkeypatch.setattr(Preflight, "is_admin", staticmethod(lambda: False))
    monkeypatch.setattr(Preflight, "os_build", staticmethod(lambda: 17000))
    report = Preflight(_FakeSystemInfo(virt=False, wmi=False, sac="On")).run()
    assert report.ok is False
    assert any("Administrator" in w for w in report.warnings)
    assert any("WMI" in w for w in report.warnings)
    assert any("virtualization" in w.lower() for w in report.warnings)
    assert any("Smart App Control" in w for w in report.warnings)
    assert any("older than" in w for w in report.warnings)
