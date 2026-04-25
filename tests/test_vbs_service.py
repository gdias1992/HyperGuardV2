"""Tests for :mod:`src.services.vbs_service`."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.models.state import BackupEntry, OperationResult, OperationStatus, RegistryValueType
from src.services.vbs_service import REGISTRY_PIRATE_PLAN, ProgressEvent, VbsService


class FakeRegistry:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str, RegistryValueType, Any]] = []
        self.backups: list[BackupEntry] = []

    def write_value(
        self, path: str, name: str, value_type: RegistryValueType, data: Any
    ) -> BackupEntry:
        self.writes.append((path, name, value_type, data))
        entry = BackupEntry(
            key_path=path,
            value_name=name,
            value_type=value_type,
            original_value=None,
            existed=False,
        )
        self.backups.append(entry)
        return entry

    def restore(self, entry: BackupEntry) -> None:
        self.backups.append(entry)

    def load_persisted_backups(self) -> list[BackupEntry]:
        return list(self.backups)


class FakeBcd:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def set_hypervisor_launch(self, value: str) -> OperationResult:
        self.calls.append(f"launch={value}")
        return OperationResult(
            feature_id=8,
            step=f"bcdedit /set hypervisorlaunchtype {value}",
            status=OperationStatus.SUCCESS,
            requires_reboot=True,
        )

    def enable_one_time_advanced_options(self) -> OperationResult:
        self.calls.append("dse-on")
        return OperationResult(
            feature_id=6,
            step="dse",
            status=OperationStatus.SUCCESS,
            requires_reboot=True,
        )

    def clear_one_time_advanced_options(self) -> OperationResult:
        self.calls.append("dse-off")
        return OperationResult(
            feature_id=6, step="clear dse", status=OperationStatus.SUCCESS
        )


class FakeServices:
    def __init__(self) -> None:
        self.calls = 0

    def disable_faceit(self) -> list[OperationResult]:
        self.calls += 1
        return [
            OperationResult(
                feature_id=9, step="disable FACEIT", status=OperationStatus.SUCCESS
            )
        ]


class FakeBitlocker:
    def __init__(self, active: bool = True) -> None:
        self.calls: list[str] = []
        self.active = active

    def suspend(self, drive: str = "C:", reboot_count: int = 1) -> OperationResult:
        self.calls.append(f"suspend-{drive}")
        return OperationResult(
            feature_id=14, step="suspend", status=OperationStatus.SUCCESS
        )

    def resume(self, drive: str = "C:") -> OperationResult:
        self.calls.append(f"resume-{drive}")
        return OperationResult(
            feature_id=14, step="resume", status=OperationStatus.SUCCESS
        )


class FakeEfi:
    def __init__(self) -> None:
        self.calls = 0

    def delete_hello_container(self) -> OperationResult:
        self.calls += 1
        return OperationResult(
            feature_id=10,
            step="certutil",
            status=OperationStatus.SUCCESS,
            requires_reboot=True,
        )


class FakePreflight:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    def run(self) -> Any:
        return type(
            "R",
            (),
            {
                "ok": self.ok,
                "warnings": [] if self.ok else ["admin missing"],
                "is_admin": self.ok,
                "is_windows": True,
                "os_build": 22000,
                "virtualization": True,
                "wmi_healthy": True,
                "smart_app_control": "Off",
            },
        )()


class FakeSystemInfo:
    def __init__(self, bitlocker: bool = True) -> None:
        self.bitlocker = bitlocker

    def bitlocker_active(self, drive: str = "C:") -> bool:
        return self.bitlocker


@pytest.fixture
def svc() -> VbsService:
    return VbsService(
        registry=FakeRegistry(),
        bcd=FakeBcd(),
        services=FakeServices(),
        bitlocker=FakeBitlocker(),
        efi=FakeEfi(),
        preflight=FakePreflight(ok=True),
        system_info=FakeSystemInfo(bitlocker=True),
        dry_run=False,
    )


def test_pirate_plan_has_one_entry_per_managed_feature() -> None:
    # Every managed registry feature (3,4,5,7,10,11,12) has at least one entry.
    covered = {plan[0] for plan in REGISTRY_PIRATE_PLAN}
    assert {3, 4, 5, 7, 10, 11, 12} <= covered


def test_optimize_emits_progress_and_returns_results(svc: VbsService) -> None:
    events: list[ProgressEvent] = []

    def on_progress(event: ProgressEvent) -> None:
        events.append(event)

    results = asyncio.run(svc.optimize(progress=on_progress))

    # Pre-flight + steps
    assert len(results) >= 1
    assert any(e.percent == 100 for e in events)
    # At least one reboot-required result was produced
    assert any(r.requires_reboot for r in results)


def test_optimize_skips_bitlocker_when_inactive() -> None:
    bl = FakeBitlocker()
    svc = VbsService(
        registry=FakeRegistry(),
        bcd=FakeBcd(),
        services=FakeServices(),
        bitlocker=bl,
        efi=FakeEfi(),
        preflight=FakePreflight(ok=True),
        system_info=FakeSystemInfo(bitlocker=False),
        dry_run=False,
    )
    asyncio.run(svc.optimize())
    assert bl.calls == []  # suspend not invoked


def test_optimize_aborts_when_preflight_fails() -> None:
    bcd = FakeBcd()
    svc = VbsService(
        registry=FakeRegistry(),
        bcd=bcd,
        services=FakeServices(),
        bitlocker=FakeBitlocker(),
        efi=FakeEfi(),
        preflight=FakePreflight(ok=False),
        system_info=FakeSystemInfo(bitlocker=True),
        dry_run=False,
    )
    results = asyncio.run(svc.optimize())
    assert results and results[0].status == OperationStatus.FAILED
    # No mutations should have happened
    assert bcd.calls == []


def test_revert_restores_backups_and_reboot(svc: VbsService) -> None:
    # Seed a backup to restore.
    reg: FakeRegistry = svc.registry  # type: ignore[assignment]
    reg.backups.append(
        BackupEntry(
            key_path=r"HKLM\SOFTWARE\X",
            value_name="V",
            value_type=RegistryValueType.REG_DWORD,
            original_value=1,
            existed=True,
        )
    )
    results = asyncio.run(svc.revert())
    statuses = [r.status for r in results]
    assert OperationStatus.SUCCESS in statuses
    # BCD revert + BitLocker resume were invoked
    bcd: FakeBcd = svc.bcd  # type: ignore[assignment]
    bl: FakeBitlocker = svc.bitlocker  # type: ignore[assignment]
    assert "launch=auto" in bcd.calls
    assert "resume-C:" in bl.calls
