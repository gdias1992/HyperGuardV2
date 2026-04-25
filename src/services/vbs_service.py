"""High-level orchestrator exposing PIRATE / DEFENDER workflows to the GUI.

The class coordinates :class:`RegistryOps`, :class:`BcdOps`, :class:`ServiceOps`,
:class:`BitlockerOps`, :class:`EfiOps` and :class:`SystemInfo` and streams
progress updates to an ``asyncio.Queue`` consumed by the NiceGUI Logs tab.

All mutations are synchronous underneath; async methods marshal them onto a
worker thread via :func:`asyncio.to_thread` so the NiceGUI event loop is never
blocked.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from src.config import settings
from src.exceptions import HyperGuardError
from src.models.state import (
    BackupEntry,
    OperationResult,
    OperationStatus,
    RegistryValueType,
    SafeState,
)
from src.services.bcd_ops import BcdOps
from src.services.bitlocker_ops import BitlockerOps
from src.services.efi_ops import EfiOps
from src.services.preflight import Preflight, PreflightReport
from src.services.registry_ops import RegistryOps
from src.services.service_ops import ServiceOps
from src.services.system_info import SystemInfo
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Progress eventing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProgressEvent:
    """An update streamed during a workflow."""

    step: str
    percent: int
    level: str = "ACTION"  # ACTION | INFO | WARN | ERROR | SUCCESS
    message: str = ""


ProgressCallback = Callable[[ProgressEvent], Awaitable[None] | None]


# ---------------------------------------------------------------------------
# Canonical SafeState catalogue (validated targets)
# ---------------------------------------------------------------------------


PIRATE_SAFE_STATES: dict[int, SafeState] = {
    3: SafeState(
        feature_id=3,
        feature_name="VBS",
        action="disable",
        target_registry_value=0,
        requires_reboot=True,
    ),
    4: SafeState(
        feature_id=4,
        feature_name="HVCI",
        action="disable",
        target_registry_value=0,
        requires_reboot=True,
    ),
    5: SafeState(
        feature_id=5,
        feature_name="Credential Guard",
        action="disable",
        target_registry_value=0,
        requires_reboot=True,
    ),
    6: SafeState(
        feature_id=6,
        feature_name="Driver Signature Enforcement",
        action="disable",
        requires_reboot=True,
    ),
    7: SafeState(
        feature_id=7,
        feature_name="KVA Shadow",
        action="disable",
        target_registry_value=2,
        requires_reboot=True,
    ),
    8: SafeState(
        feature_id=8,
        feature_name="Windows Hypervisor",
        action="disable",
        requires_reboot=True,
    ),
    9: SafeState(
        feature_id=9, feature_name="FACEIT", action="disable", requires_reboot=False
    ),
    10: SafeState(
        feature_id=10,
        feature_name="Windows Hello Protection",
        action="remove",
        target_registry_value=0,
        requires_reboot=True,
    ),
    11: SafeState(
        feature_id=11,
        feature_name="Secure Biometrics",
        action="disable",
        target_registry_value=0,
        requires_reboot=True,
    ),
    12: SafeState(
        feature_id=12,
        feature_name="HyperGuard / System Guard",
        action="disable",
        target_registry_value=0,
        requires_reboot=True,
    ),
    14: SafeState(
        feature_id=14,
        feature_name="BitLocker",
        action="suspend",
        requires_reboot=False,
    ),
}


# Registry writes executed during PIRATE MODE. Order matters.
REGISTRY_PIRATE_PLAN: list[tuple[int, str, str, str, RegistryValueType, Any]] = [
    (
        3,
        "VBS disable",
        r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard",
        "EnableVirtualizationBasedSecurity",
        RegistryValueType.REG_DWORD,
        0,
    ),
    (
        4,
        "HVCI disable",
        r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity",
        "Enabled",
        RegistryValueType.REG_DWORD,
        0,
    ),
    (
        5,
        "Credential Guard Lsa flag",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Lsa",
        "LsaCfgFlags",
        RegistryValueType.REG_DWORD,
        0,
    ),
    (
        5,
        "Credential Guard policy flag",
        r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DeviceGuard",
        "LsaCfgFlags",
        RegistryValueType.REG_DWORD,
        0,
    ),
    (
        5,
        "Credential Guard scenario",
        r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\CredentialGuard",
        "Enabled",
        RegistryValueType.REG_DWORD,
        0,
    ),
    (
        7,
        "KVA Shadow override",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
        "FeatureSettingsOverride",
        RegistryValueType.REG_DWORD,
        2,
    ),
    (
        7,
        "KVA Shadow mask",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
        "FeatureSettingsOverrideMask",
        RegistryValueType.REG_DWORD,
        3,
    ),
    (
        10,
        "Windows Hello scenario",
        r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\WindowsHello",
        "Enabled",
        RegistryValueType.REG_DWORD,
        0,
    ),
    (
        11,
        "Secure Biometrics scenario",
        r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\SecureBiometrics",
        "Enabled",
        RegistryValueType.REG_DWORD,
        0,
    ),
    (
        11,
        "Secure Biometrics (legacy)",
        r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\WindowsHelloSecureBiometrics",
        "Enabled",
        RegistryValueType.REG_DWORD,
        0,
    ),
    (
        12,
        "HyperGuard scenario",
        r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HyperGuard",
        "Enabled",
        RegistryValueType.REG_DWORD,
        0,
    ),
    (
        12,
        "System Guard scenario",
        r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\SystemGuard",
        "Enabled",
        RegistryValueType.REG_DWORD,
        0,
    ),
    (
        12,
        "Host-Guardian scenario",
        r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\Host-Guardian",
        "Enabled",
        RegistryValueType.REG_DWORD,
        0,
    ),
]


# ---------------------------------------------------------------------------
# VbsService
# ---------------------------------------------------------------------------


class VbsService:
    """Orchestrator for the PIRATE / DEFENDER workflows."""

    def __init__(
        self,
        registry: RegistryOps | None = None,
        bcd: BcdOps | None = None,
        services: ServiceOps | None = None,
        bitlocker: BitlockerOps | None = None,
        efi: EfiOps | None = None,
        preflight: Preflight | None = None,
        system_info: SystemInfo | None = None,
        dry_run: bool | None = None,
    ) -> None:
        self.dry_run = settings.dry_run if dry_run is None else dry_run
        self.registry = registry or RegistryOps(dry_run=self.dry_run)
        self.bcd = bcd or BcdOps(dry_run=self.dry_run)
        self.services = services or ServiceOps(dry_run=self.dry_run)
        self.bitlocker = bitlocker or BitlockerOps(dry_run=self.dry_run)
        self.efi = efi or EfiOps(dry_run=self.dry_run)
        self.system_info = system_info or SystemInfo(self.registry)
        self.preflight = preflight or Preflight(self.system_info)

    # ------------------------------------------------------------------
    # Workflow entry points (async)
    # ------------------------------------------------------------------

    async def optimize(
        self, progress: ProgressCallback | None = None
    ) -> list[OperationResult]:
        """Run the PIRATE MODE sequence on a worker thread."""
        return await asyncio.to_thread(self._run_optimize_sync, progress)

    async def revert(
        self, progress: ProgressCallback | None = None
    ) -> list[OperationResult]:
        """Run the DEFENDER MODE sequence on a worker thread."""
        return await asyncio.to_thread(self._run_revert_sync, progress)

    # ------------------------------------------------------------------
    # Workflow bodies (synchronous — run in a worker thread)
    # ------------------------------------------------------------------

    def _run_optimize_sync(
        self, progress: ProgressCallback | None
    ) -> list[OperationResult]:
        emit = _sync_emitter(progress)
        results: list[OperationResult] = []

        emit(ProgressEvent("Running pre-flight checks", 5, "INFO"))
        report = self.preflight.run()
        results.append(
            OperationResult(
                step="preflight",
                status=(
                    OperationStatus.SUCCESS
                    if report.ok or self.dry_run
                    else OperationStatus.FAILED
                ),
                message=", ".join(report.warnings) or "All checks passed.",
            )
        )
        if not report.ok and not self.dry_run:
            emit(
                ProgressEvent(
                    "Pre-flight failed — aborting.", 100, "ERROR", results[-1].message
                )
            )
            return results

        steps = [
            ("Suspending BitLocker", 15, self._step_suspend_bitlocker),
            ("Disabling VBS registry keys", 30, self._step_disable_registry_features),
            ("Setting hypervisorlaunchtype=off", 55, self._step_disable_hypervisor),
            (
                "Enabling Startup Settings (F7) for DSE",
                65,
                self._step_disable_dse,
            ),
            ("Stopping FACEIT services", 78, self._step_disable_faceit),
            ("Removing Windows Hello container", 90, self._step_remove_hello),
        ]
        for label, percent, func in steps:
            emit(ProgressEvent(label, percent, "ACTION"))
            try:
                step_results = func()
            except HyperGuardError as exc:
                logger.exception("Workflow step failed: %s", label)
                results.append(
                    OperationResult(
                        step=label,
                        status=OperationStatus.FAILED,
                        message=str(exc),
                    )
                )
                emit(ProgressEvent(label, percent, "ERROR", str(exc)))
                continue
            results.extend(step_results)
            for r in step_results:
                if r.status == OperationStatus.FAILED:
                    emit(ProgressEvent(r.step, percent, "ERROR", r.message))

        needs_reboot = any(r.requires_reboot for r in results)
        emit(
            ProgressEvent(
                "Optimization complete",
                100,
                "SUCCESS",
                "Reboot required." if needs_reboot else "Done.",
            )
        )
        return results

    def _run_revert_sync(
        self, progress: ProgressCallback | None
    ) -> list[OperationResult]:
        emit = _sync_emitter(progress)
        results: list[OperationResult] = []

        emit(ProgressEvent("Loading persisted backups", 10, "INFO"))
        backups = self.registry.load_persisted_backups()
        results.append(
            OperationResult(
                step="load backups",
                status=OperationStatus.SUCCESS,
                message=f"{len(backups)} backup entries found.",
            )
        )

        emit(ProgressEvent("Restoring registry values", 35, "ACTION"))
        results.extend(self._restore_backups(backups))

        emit(ProgressEvent("Restoring BCD", 60, "ACTION"))
        try:
            results.append(self.bcd.set_hypervisor_launch("auto"))
        except HyperGuardError as exc:
            results.append(
                OperationResult(
                    feature_id=8,
                    step="bcdedit /set hypervisorlaunchtype auto",
                    status=OperationStatus.FAILED,
                    message=str(exc),
                )
            )
        try:
            results.append(self.bcd.clear_one_time_advanced_options())
        except HyperGuardError as exc:
            # Missing value is benign — report as skipped.
            results.append(
                OperationResult(
                    feature_id=6,
                    step="clear onetimeadvancedoptions",
                    status=OperationStatus.SKIPPED,
                    message=str(exc),
                )
            )

        emit(ProgressEvent("Resuming BitLocker", 85, "ACTION"))
        try:
            results.append(self.bitlocker.resume())
        except HyperGuardError as exc:
            results.append(
                OperationResult(
                    feature_id=14,
                    step="resume BitLocker",
                    status=OperationStatus.FAILED,
                    message=str(exc),
                )
            )

        needs_reboot = any(r.requires_reboot for r in results)
        emit(
            ProgressEvent(
                "Revert complete",
                100,
                "SUCCESS",
                "Reboot required." if needs_reboot else "Done.",
            )
        )
        return results

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _step_suspend_bitlocker(self) -> list[OperationResult]:
        if not self.system_info.bitlocker_active():
            return [
                OperationResult(
                    feature_id=14,
                    step="suspend BitLocker",
                    status=OperationStatus.SKIPPED,
                    message="BitLocker is not active on C:.",
                )
            ]
        return [self.bitlocker.suspend(drive="C:", reboot_count=1)]

    def _step_disable_registry_features(self) -> list[OperationResult]:
        results: list[OperationResult] = []
        for feature_id, label, path, name, value_type, value in REGISTRY_PIRATE_PLAN:
            state = PIRATE_SAFE_STATES.get(feature_id)
            # Validate the target value against the safe-state catalogue.
            if state and state.target_registry_value is not None:
                expected = state.target_registry_value
                if value not in {expected, 2, 3}:  # allow KVA mask values
                    results.append(
                        OperationResult(
                            feature_id=feature_id,
                            step=label,
                            status=OperationStatus.FAILED,
                            message=(
                                f"Value {value!r} is not a safe target for "
                                f"{state.feature_name}."
                            ),
                        )
                    )
                    continue
            try:
                backup = self.registry.write_value(path, name, value_type, value)
            except HyperGuardError as exc:
                results.append(
                    OperationResult(
                        feature_id=feature_id,
                        step=label,
                        status=OperationStatus.FAILED,
                        message=str(exc),
                    )
                )
                continue
            results.append(
                OperationResult(
                    feature_id=feature_id,
                    step=label,
                    status=(
                        OperationStatus.DRY_RUN
                        if self.dry_run
                        else OperationStatus.SUCCESS
                    ),
                    requires_reboot=True,
                    backups=[backup],
                )
            )
        return results

    def _step_disable_hypervisor(self) -> list[OperationResult]:
        return [self.bcd.set_hypervisor_launch("off")]

    def _step_disable_dse(self) -> list[OperationResult]:
        return [self.bcd.enable_one_time_advanced_options()]

    def _step_disable_faceit(self) -> list[OperationResult]:
        return self.services.disable_faceit()

    def _step_remove_hello(self) -> list[OperationResult]:
        results: list[OperationResult] = []
        try:
            results.append(self.efi.delete_hello_container())
        except HyperGuardError as exc:
            results.append(
                OperationResult(
                    feature_id=10,
                    step="certutil -DeleteHelloContainer",
                    status=OperationStatus.FAILED,
                    message=str(exc),
                )
            )
        return results

    # ------------------------------------------------------------------
    # Backup restoration
    # ------------------------------------------------------------------

    def _restore_backups(self, backups: list[BackupEntry]) -> list[OperationResult]:
        results: list[OperationResult] = []
        for entry in backups:
            try:
                self.registry.restore(entry)
                results.append(
                    OperationResult(
                        step=f"restore {entry.key_path}\\{entry.value_name}",
                        status=(
                            OperationStatus.DRY_RUN
                            if self.dry_run
                            else OperationStatus.SUCCESS
                        ),
                    )
                )
            except HyperGuardError as exc:
                results.append(
                    OperationResult(
                        step=f"restore {entry.key_path}\\{entry.value_name}",
                        status=OperationStatus.FAILED,
                        message=str(exc),
                    )
                )
        return results

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def preflight_report(self) -> PreflightReport:
        return self.preflight.run()


def _sync_emitter(
    callback: ProgressCallback | None,
) -> Callable[[ProgressEvent], None]:
    """Wrap an async / sync progress callback so sync code can emit events."""

    def emit(event: ProgressEvent) -> None:
        if callback is None:
            return
        try:
            result = callback(event)
        except Exception as exc:  # pragma: no cover - UI errors are informational
            logger.warning("Progress callback raised: %s", exc)
            return
        if asyncio.iscoroutine(result):
            # Schedule the coroutine on the running loop, if any.
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(result, loop)
            else:  # pragma: no cover
                asyncio.run(result)

    return emit


__all__ = [
    "PIRATE_SAFE_STATES",
    "ProgressCallback",
    "ProgressEvent",
    "REGISTRY_PIRATE_PLAN",
    "VbsService",
]
