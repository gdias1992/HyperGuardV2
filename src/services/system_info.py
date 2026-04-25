"""Detect the live state of the 14 managed security features.

The heavy lifting is split between:

* WMI queries (``Win32_DeviceGuard``, ``Win32_Processor`` …) via ``pywin32``.
* A direct ``NtQuerySystemInformation`` call through :mod:`ctypes` for feature
  classes Windows does not surface via WMI (DSE = 103, KVA Shadow = 196).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import platform
import subprocess
from dataclasses import dataclass
from typing import Any

from src.exceptions import SystemInfoError
from src.services.registry_ops import RegistryOps
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# NtQuerySystemInformation constants
# ---------------------------------------------------------------------------

SYSTEM_CODE_INTEGRITY_INFORMATION = 103
SYSTEM_SPECULATION_CONTROL_INFORMATION = 196

CODE_INTEGRITY_OPTION_ENABLED = 0x01
CODE_INTEGRITY_OPTION_TESTSIGN = 0x02

SPECULATION_KVA_SHADOW_ENABLED = 0x01
SPECULATION_BPB_ENABLED = 0x20
SPECULATION_BPB_TARGETS = 0x10


@dataclass(frozen=True)
class FeatureSnapshot:
    """Live state snapshot for a single feature id."""

    feature_id: int
    name: str
    status: str
    details: str = ""


class SystemInfo:
    """Detect the live state of each managed feature."""

    def __init__(self, registry: RegistryOps | None = None) -> None:
        self._registry = registry or RegistryOps(dry_run=False)

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_windows() -> bool:
        return platform.system() == "Windows"

    def _nt_query(self, info_class: int, size: int = 4) -> bytes | None:
        """Call ``NtQuerySystemInformation`` and return the raw buffer.

        Returns ``None`` on non-Windows platforms or when the call fails.
        """
        if not self.is_windows():
            return None
        try:
            ntdll = ctypes.WinDLL("ntdll")  # type: ignore[attr-defined]
        except OSError as exc:  # pragma: no cover - Windows-only
            raise SystemInfoError(f"Cannot load ntdll: {exc}") from exc

        buffer = ctypes.create_string_buffer(size)
        returned = wt.ULONG(0)
        status = ntdll.NtQuerySystemInformation(
            wt.ULONG(info_class),
            ctypes.byref(buffer),
            wt.ULONG(size),
            ctypes.byref(returned),
        )
        if status != 0:
            logger.debug(
                "NtQuerySystemInformation(%d) returned 0x%X", info_class, status & 0xFFFFFFFF
            )
            return None
        return buffer.raw[: returned.value or size]

    def _wmi_device_guard(self) -> dict[str, Any]:
        """Return a dict view of ``Win32_DeviceGuard`` (empty on failure)."""
        if not self.is_windows():
            return {}
        try:
            import wmi  # type: ignore[import-not-found]
        except ImportError:
            try:
                import win32com.client  # type: ignore[import-not-found]
            except ImportError:  # pragma: no cover - Windows-only
                return {}
            locator = win32com.client.Dispatch("WbemScripting.SWbemLocator")
            service = locator.ConnectServer(
                ".", "root\\Microsoft\\Windows\\DeviceGuard"
            )
            items = service.ExecQuery("SELECT * FROM Win32_DeviceGuard")
            for item in items:
                return {
                    "VirtualizationBasedSecurityStatus": getattr(
                        item, "VirtualizationBasedSecurityStatus", 0
                    ),
                    "SecurityServicesConfigured": list(
                        getattr(item, "SecurityServicesConfigured", []) or []
                    ),
                    "SecurityServicesRunning": list(
                        getattr(item, "SecurityServicesRunning", []) or []
                    ),
                }
            return {}

        try:
            connection = wmi.WMI(namespace="root\\Microsoft\\Windows\\DeviceGuard")
            for item in connection.Win32_DeviceGuard():
                return {
                    "VirtualizationBasedSecurityStatus": getattr(
                        item, "VirtualizationBasedSecurityStatus", 0
                    )
                    or 0,
                    "SecurityServicesConfigured": list(
                        getattr(item, "SecurityServicesConfigured", []) or []
                    ),
                    "SecurityServicesRunning": list(
                        getattr(item, "SecurityServicesRunning", []) or []
                    ),
                }
        except Exception as exc:  # pragma: no cover - Windows-only
            logger.warning("WMI DeviceGuard query failed: %s", exc)
        return {}

    # ------------------------------------------------------------------
    # Feature-level detection (1..14)
    # ------------------------------------------------------------------

    def virtualization_enabled(self) -> bool:
        """#1 — BIOS virtualization (VT-x / AMD-V)."""
        if not self.is_windows():
            return False
        try:
            import wmi  # type: ignore[import-not-found]

            cpu = next(iter(wmi.WMI().Win32_Processor()), None)
            if cpu is None:
                return False
            return bool(getattr(cpu, "VirtualizationFirmwareEnabled", False))
        except Exception as exc:  # pragma: no cover - Windows-only
            logger.debug("Win32_Processor query failed: %s", exc)
            return False

    def wmi_healthy(self) -> bool:
        """#2 — WMI repository health (cheap probe)."""
        if not self.is_windows():
            return False
        try:
            result = subprocess.run(
                ["wmic", "path", "Win32_ComputerSystem", "get", "CreationClassName"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("WMI probe failed: %s", exc)
            return False
        return result.returncode == 0 and "Win32_ComputerSystem" in (result.stdout or "")

    def vbs_status(self) -> tuple[str, dict[str, Any]]:
        """#3 — VBS status via Win32_DeviceGuard."""
        data = self._wmi_device_guard()
        code = int(data.get("VirtualizationBasedSecurityStatus", 0))
        label = {0: "Disabled", 1: "Enabled", 2: "Running"}.get(code, "Unknown")
        return label, data

    def hvci_active(self) -> bool:
        """#4 — HVCI / Memory Integrity (service code ``2`` is HVCI)."""
        data = self._wmi_device_guard()
        return 2 in (data.get("SecurityServicesRunning") or [])

    def credential_guard_active(self) -> bool:
        """#5 — Credential Guard (service code ``1``)."""
        data = self._wmi_device_guard()
        return 1 in (data.get("SecurityServicesRunning") or [])

    def driver_signature_status(self) -> str:
        """#6 — DSE status via ``NtQuerySystemInformation(103)``."""
        buf = self._nt_query(SYSTEM_CODE_INTEGRITY_INFORMATION, size=8)
        if not buf or len(buf) < 8:
            return "Unknown"
        options = int.from_bytes(buf[4:8], "little")
        if options & CODE_INTEGRITY_OPTION_TESTSIGN:
            return "Test Signing"
        if not (options & CODE_INTEGRITY_OPTION_ENABLED):
            return "Disabled"
        return "Enabled"

    def kva_shadow_active(self) -> bool:
        """#7 — KVA Shadow via ``NtQuerySystemInformation(196)``."""
        buf = self._nt_query(SYSTEM_SPECULATION_CONTROL_INFORMATION, size=4)
        if not buf or len(buf) < 4:
            return False
        flags = int.from_bytes(buf[0:4], "little")
        if flags & SPECULATION_KVA_SHADOW_ENABLED:
            return True
        return bool(
            (flags & SPECULATION_BPB_ENABLED)
            and (flags & SPECULATION_BPB_TARGETS)
        )

    def hypervisor_present(self) -> bool:
        """#8 — Windows hypervisor currently running."""
        if not self.is_windows():
            return False
        try:
            import wmi  # type: ignore[import-not-found]

            info = next(iter(wmi.WMI().Win32_ComputerSystem()), None)
            if info is None:
                return False
            return bool(getattr(info, "HypervisorPresent", False))
        except Exception as exc:  # pragma: no cover
            logger.debug("Hypervisor probe failed: %s", exc)
            return False

    def faceit_present(self) -> bool:
        """#9 — FACEIT filter currently loaded."""
        if not self.is_windows():
            return False
        try:
            result = subprocess.run(
                ["fltmc"], capture_output=True, text=True, timeout=15, check=False
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return "faceit" in (result.stdout or "").lower()

    def windows_hello_enabled(self) -> bool:
        """#10 — Windows Hello VBS scenario active."""
        return self._registry_flag(
            r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\WindowsHello",
            "Enabled",
        )

    def secure_biometrics_enabled(self) -> bool:
        """#11 — Secure Biometrics (any of the 3 registry variants)."""
        paths = [
            (
                r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\SecureBiometrics",
                "Enabled",
            ),
            (
                r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios",
                "SecureBiometrics",
            ),
            (
                r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\WindowsHelloSecureBiometrics",
                "Enabled",
            ),
        ]
        return any(self._registry_flag(p, n) for p, n in paths)

    def hyperguard_enabled(self) -> bool:
        """#12 — HyperGuard / System Guard / Host-Guardian scenarios."""
        paths = [
            r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HyperGuard",
            r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\SystemGuard",
            r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\Host-Guardian",
        ]
        return any(self._registry_flag(p, "Enabled") for p in paths)

    def smart_app_control_state(self) -> str:
        """#13 — Smart App Control state (``Off``/``Monitoring``/``On``)."""
        result = self._registry.read_value(
            r"HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy",
            "VerifiedAndReputablePolicyState",
        )
        if result is None:
            return "Unknown"
        _, value = result
        return {0: "Off", 1: "On", 2: "Monitoring"}.get(int(value), "Unknown")

    def bitlocker_active(self, drive: str = "C:") -> bool:
        """#14 — Any protector active on ``drive``."""
        if not self.is_windows():
            return False
        try:
            result = subprocess.run(
                ["manage-bde", "-status", drive],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        text = (result.stdout or "").lower()
        return "protection on" in text or "protection status: protection on" in text

    # ------------------------------------------------------------------
    # Aggregated status
    # ------------------------------------------------------------------

    def snapshot_all(self) -> list[FeatureSnapshot]:
        """Return a :class:`FeatureSnapshot` for each of the 14 features."""
        dg = self._wmi_device_guard()
        vbs_code = int(dg.get("VirtualizationBasedSecurityStatus", 0))

        def _yn(flag: bool, on: str = "Active", off: str = "Disabled") -> str:
            return on if flag else off

        vbs_label = {0: "Disabled", 1: "Enabled", 2: "Active"}.get(vbs_code, "Unknown")
        dse = self.driver_signature_status()
        sac = self.smart_app_control_state()

        return [
            FeatureSnapshot(1, "Virtualization (VT-x/SVM)", _yn(self.virtualization_enabled())),
            FeatureSnapshot(2, "WMI (WinMgmt)", _yn(self.wmi_healthy(), on="Active", off="Failed")),
            FeatureSnapshot(3, "VBS (Virt-Based Security)", vbs_label),
            FeatureSnapshot(4, "HVCI (Memory Integrity)", _yn(self.hvci_active())),
            FeatureSnapshot(5, "Credential Guard", _yn(self.credential_guard_active())),
            FeatureSnapshot(6, "Driver Signature Enf.", dse),
            FeatureSnapshot(7, "KVA Shadow (Meltdown)", _yn(self.kva_shadow_active())),
            FeatureSnapshot(8, "Windows Hypervisor", _yn(self.hypervisor_present())),
            FeatureSnapshot(9, "FACEIT Anti-Cheat", _yn(self.faceit_present())),
            FeatureSnapshot(10, "Windows Hello Protection", _yn(self.windows_hello_enabled())),
            FeatureSnapshot(11, "Secure Biometrics", _yn(self.secure_biometrics_enabled())),
            FeatureSnapshot(12, "HyperGuard / Sys Guard", _yn(self.hyperguard_enabled())),
            FeatureSnapshot(13, "Smart App Control", sac),
            FeatureSnapshot(14, "BitLocker", _yn(self.bitlocker_active(), on="Active", off="Suspended")),
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _registry_flag(self, key_path: str, value_name: str) -> bool:
        result = self._registry.read_value(key_path, value_name)
        if result is None:
            return False
        _, data = result
        try:
            return int(data) != 0
        except (TypeError, ValueError):
            return bool(data)


__all__ = ["FeatureSnapshot", "SystemInfo"]
