"""Detect the live state of the 14 managed security features.

The heavy lifting is split between:

* WMI/CIM queries (``Win32_DeviceGuard``, ``Win32_Processor`` …) via
    ``pywin32`` COM with PowerShell fallbacks.
* A direct ``NtQuerySystemInformation`` call through :mod:`ctypes` for feature
  classes Windows does not surface via WMI (DSE = 103, KVA Shadow = 196).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
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

FACEIT_SERVICE_NAMES = ("FACEIT", "FACEITService")
ROOT_CIMV2_NAMESPACE = "root\\cimv2"
DEVICE_GUARD_NAMESPACE = "root\\Microsoft\\Windows\\DeviceGuard"


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

    @staticmethod
    def _bool_value(value: Any) -> bool | None:
        """Normalize common WMI/CIM bool representations."""
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1"}:
                return True
            if normalized in {"false", "no", "0"}:
                return False
        return None

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        """Convert COM SAFEARRAY / CIM array values into plain Python lists."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        try:
            return list(value)
        except TypeError:
            return [value]

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
            ctypes.cast(buffer, wt.LPVOID),
            wt.ULONG(size),
            ctypes.byref(returned),
        )
        if status != 0:
            logger.debug(
                "NtQuerySystemInformation(%d) returned 0x%X", info_class, status & 0xFFFFFFFF
            )
            return None
        return buffer.raw[: returned.value or size]

    def _wmi_first(
        self, namespace: str, query: str, properties: tuple[str, ...]
    ) -> dict[str, Any] | None:
        """Return selected fields from the first COM WMI row."""
        if not self.is_windows():
            return None
        try:
            import pythoncom  # type: ignore[import-not-found]
            import win32com.client  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - Windows-only dependency
            logger.debug("pywin32 WMI COM support is unavailable: %s", exc)
            return None
        com_initialized = False
        row: dict[str, Any] | None = None
        locator: Any | None = None
        service: Any | None = None
        items: Any | None = None
        item: Any | None = None
        try:
            pythoncom.CoInitialize()
            com_initialized = True
            locator = win32com.client.Dispatch("WbemScripting.SWbemLocator")
            service = locator.ConnectServer(".", namespace)
            items = service.ExecQuery(query)
            for item in items:
                row = {name: getattr(item, name, None) for name in properties}
                break
        except Exception as exc:  # pragma: no cover - Windows-only
            logger.debug("WMI query failed (%s): %s", namespace, exc)
        finally:
            item = None
            items = None
            service = None
            locator = None
            if com_initialized:
                pythoncom.CoUninitialize()
        return row

    def _run_powershell(
        self, command: str, timeout: int = 20
    ) -> subprocess.CompletedProcess[str] | None:
        """Run a fixed PowerShell probe without invoking a shell."""
        if not self.is_windows():
            return None
        try:
            return subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("PowerShell probe failed: %s", exc)
            return None

    def _powershell_json(self, command: str, timeout: int = 20) -> dict[str, Any]:
        """Return the first JSON object emitted by a fixed PowerShell probe."""
        result = self._run_powershell(command, timeout=timeout)
        if result is None or result.returncode != 0:
            return {}
        payload = (result.stdout or "").strip()
        if not payload:
            return {}
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            logger.debug("PowerShell JSON parse failed: %s", exc)
            return {}
        if isinstance(data, list):
            first = data[0] if data else {}
            return first if isinstance(first, dict) else {}
        return data if isinstance(data, dict) else {}

    def _processor_info(self) -> dict[str, Any]:
        """Return selected ``Win32_Processor`` fields via COM or CIM."""
        item = self._wmi_first(
            ROOT_CIMV2_NAMESPACE,
            "SELECT Manufacturer, VirtualizationFirmwareEnabled, "
            "SecondLevelAddressTranslationExtensions FROM Win32_Processor",
            (
                "Manufacturer",
                "VirtualizationFirmwareEnabled",
                "SecondLevelAddressTranslationExtensions",
            ),
        )
        if item is not None:
            return item
        return self._powershell_json(
            "Get-CimInstance -ClassName Win32_Processor | "
            "Select-Object -First 1 Manufacturer,VirtualizationFirmwareEnabled,"
            "SecondLevelAddressTranslationExtensions | ConvertTo-Json -Compress"
        )

    def _computer_system_info(self) -> dict[str, Any]:
        """Return selected ``Win32_ComputerSystem`` fields via COM or CIM."""
        item = self._wmi_first(
            ROOT_CIMV2_NAMESPACE,
            "SELECT HypervisorPresent FROM Win32_ComputerSystem",
            ("HypervisorPresent",),
        )
        if item is not None:
            return item
        return self._powershell_json(
            "Get-CimInstance -ClassName Win32_ComputerSystem | "
            "Select-Object -First 1 HypervisorPresent | ConvertTo-Json -Compress"
        )

    def _wmi_device_guard(self) -> dict[str, Any]:
        """Return a dict view of ``Win32_DeviceGuard`` (empty on failure)."""
        if not self.is_windows():
            return {}
        item = self._wmi_first(
            DEVICE_GUARD_NAMESPACE,
            "SELECT VirtualizationBasedSecurityStatus, SecurityServicesConfigured, "
            "SecurityServicesRunning FROM Win32_DeviceGuard",
            (
                "VirtualizationBasedSecurityStatus",
                "SecurityServicesConfigured",
                "SecurityServicesRunning",
            ),
        )
        if item is not None:
            return {
                "VirtualizationBasedSecurityStatus": item.get(
                    "VirtualizationBasedSecurityStatus", 0
                )
                or 0,
                "SecurityServicesConfigured": self._as_list(
                    item.get("SecurityServicesConfigured")
                ),
                "SecurityServicesRunning": self._as_list(item.get("SecurityServicesRunning")),
            }
        data = self._powershell_json(
            "Get-CimInstance -Namespace 'root\\Microsoft\\Windows\\DeviceGuard' "
            "-ClassName Win32_DeviceGuard | Select-Object -First 1 "
            "VirtualizationBasedSecurityStatus,SecurityServicesConfigured,"
            "SecurityServicesRunning | ConvertTo-Json -Compress"
        )
        if not data:
            return {}
        return {
            "VirtualizationBasedSecurityStatus": data.get(
                "VirtualizationBasedSecurityStatus", 0
            )
            or 0,
            "SecurityServicesConfigured": self._as_list(
                data.get("SecurityServicesConfigured")
            ),
            "SecurityServicesRunning": self._as_list(data.get("SecurityServicesRunning")),
        }

    # ------------------------------------------------------------------
    # Feature-level detection (1..14)
    # ------------------------------------------------------------------

    def virtualization_enabled(self) -> bool:
        """#1 — Hardware VT-x / AMD-V status.

        Mirrors the canonical CIM property used by Windows tooling:
        ``Win32_Processor.VirtualizationFirmwareEnabled``. Hypervisor runtime
        state is intentionally not used as a substitute because this diagnostic
        must reflect the BIOS/UEFI switch itself.
        """
        if not self.is_windows():
            return False
        value = self._bool_value(
            self._processor_info().get("VirtualizationFirmwareEnabled")
        )
        if value is not None:
            return value
        result = self._run_powershell(
            "Get-CimInstance -ClassName Win32_Processor | "
            "Select-Object -ExpandProperty VirtualizationFirmwareEnabled"
        )
        if result is None or result.returncode != 0:
            return False
        parsed = self._bool_value((result.stdout or "").strip())
        return bool(parsed)

    def wmi_healthy(self) -> bool:
        """#2 — WMI repository health.

        ``wmic.exe`` is deprecated and removed on recent Windows 11 builds, so
        we instead probe the WMI service directly via the COM API. Any answer
        from ``Win32_OperatingSystem`` proves the repository is responsive.
        """
        if not self.is_windows():
            return False
        item = self._wmi_first(
            ROOT_CIMV2_NAMESPACE,
            "SELECT Caption FROM Win32_OperatingSystem",
            ("Caption",),
        )
        if item is not None and item.get("Caption"):
            return True
        result = self._run_powershell("(Get-CimInstance Win32_OperatingSystem).Caption")
        if result is None:
            return False
        return result.returncode == 0 and bool((result.stdout or "").strip())

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

    def credential_guard_state(self) -> str:
        """#5 — Credential Guard.

        Mirrors ``msinfo32`` semantics: Credential Guard can be **Configured**
        (listed in ``SecurityServicesConfigured``) without actually be
        **Running** (listed in ``SecurityServicesRunning``). Returns one of
        ``"Running"``, ``"Configured"`` or ``"Disabled"``.
        """
        data = self._wmi_device_guard()
        running = data.get("SecurityServicesRunning") or []
        configured = data.get("SecurityServicesConfigured") or []
        if 1 in running:
            return "Running"
        if 1 in configured:
            return "Configured"
        return "Disabled"

    # Back-compat helper used by older callers / tests.
    def credential_guard_active(self) -> bool:
        return self.credential_guard_state() == "Running"

    def driver_signature_status(self) -> str:
        """#6 — DSE status.

        Uses the BCD store as the source of truth (per the Microsoft guidance
        in PROMPT.md): ``testsigning = Yes`` → Test Mode, ``nointegritychecks
        = Yes`` → fully disabled. When neither flag is present the kernel
        Code-Integrity options bitmap (NtQuerySystemInformation 103) acts as a
        fallback.
        """
        bcd = self._bcd_dse_flags()
        if bcd is not None:
            testsigning, nointegritychecks = bcd
            if nointegritychecks:
                return "Disabled"
            if testsigning:
                return "Test Signing"
            return "Enabled"
        buf = self._nt_query(SYSTEM_CODE_INTEGRITY_INFORMATION, size=8)
        if not buf or len(buf) < 8:
            return "Unknown"
        options = int.from_bytes(buf[4:8], "little")
        if options & CODE_INTEGRITY_OPTION_TESTSIGN:
            return "Test Signing"
        if not (options & CODE_INTEGRITY_OPTION_ENABLED):
            return "Disabled"
        return "Enabled"

    def _bcd_dse_flags(self) -> tuple[bool, bool] | None:
        """Return ``(testsigning, nointegritychecks)`` parsed from ``bcdedit``."""
        if not self.is_windows():
            return None
        try:
            result = subprocess.run(
                ["bcdedit"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("bcdedit probe failed: %s", exc)
            return None
        if result.returncode != 0:
            return None
        text = (result.stdout or "").lower()
        testsigning = False
        nointegritychecks = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("testsigning") and stripped.endswith("yes"):
                testsigning = True
            elif stripped.startswith("nointegritychecks") and stripped.endswith("yes"):
                nointegritychecks = True
        return testsigning, nointegritychecks

    def cpu_vendor(self) -> str:
        """Return the CPU vendor string (``GenuineIntel``, ``AuthenticAMD``...)."""
        if not self.is_windows():
            return ""
        return str(self._processor_info().get("Manufacturer", "") or "").strip()

    def kva_shadow_state(self) -> str:
        """#7 — KVA Shadow status with hardware-vulnerability awareness.

        Returns one of:

        * ``"Not Required (AMD)"`` — hardware is immune to Meltdown.
        * ``"Active"`` — mitigation is currently protecting the kernel.
        * ``"Disabled"`` — vulnerable hardware with mitigation off.
        * ``"Unknown"`` — cannot be determined.
        """
        vendor = self.cpu_vendor().lower()
        is_amd = "amd" in vendor
        active = self.kva_shadow_active()
        if is_amd and not active:
            return "Not Required (AMD)"
        if is_amd and active:
            return "Active (Unnecessary)"
        if active:
            return "Active"
        return "Disabled"

    def kva_shadow_active(self) -> bool:
        """#7 — Raw KVA Shadow flag via ``NtQuerySystemInformation(196)``."""
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
        return bool(self._bool_value(self._computer_system_info().get("HypervisorPresent")))

    def faceit_present(self) -> bool:
        """#9 — FACEIT filter currently loaded."""
        if not self.is_windows():
            return False
        try:
            result = subprocess.run(
                ["fltmc"], capture_output=True, text=True, timeout=15, check=False
            )
        except (OSError, subprocess.SubprocessError):
            result = None
        if result is not None and "faceit" in (result.stdout or "").lower():
            return True
        for service_name in FACEIT_SERVICE_NAMES:
            output = self._sc_query(service_name)
            if output is not None and "running" in output.lower():
                return True
        return False

    def windows_hello_enabled(self) -> bool:
        """#10 — Windows Hello protection.

        VBS-backed Hello requires both ``NgcSet : YES`` from ``dsregcmd /status``
        and an active VBS enclave. The legacy registry-only check is kept as a
        last resort.
        """
        ngc_set = self._dsregcmd_ngc_set()
        vbs_active = self._vbs_active()
        if ngc_set is not None:
            return ngc_set and vbs_active
        return self._registry_flag(
            r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\WindowsHello",
            "Enabled",
        )

    def _vbs_active(self) -> bool:
        data = self._wmi_device_guard()
        return int(data.get("VirtualizationBasedSecurityStatus", 0)) == 2

    def _dsregcmd_ngc_set(self) -> bool | None:
        """Return whether ``dsregcmd /status`` reports ``NgcSet : YES``."""
        if not self.is_windows():
            return None
        try:
            result = subprocess.run(
                ["dsregcmd", "/status"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("dsregcmd probe failed: %s", exc)
            return None
        if result.returncode != 0:
            return None
        for line in (result.stdout or "").splitlines():
            if "ngcset" in line.lower():
                return "yes" in line.lower()
        return False

    def secure_biometrics_enabled(self) -> bool:
        """#11 — Secure Biometrics (registry scenario AND VBS active)."""
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
                r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios"
                r"\WindowsHelloSecureBiometrics",
                "Enabled",
            ),
        ]
        registry_on = any(self._registry_flag(p, n) for p, n in paths)
        return registry_on and self._vbs_active()

    def hyperguard_enabled(self) -> bool:
        """#12 — HyperGuard / System Guard runtime state.

        Trust the Device Guard WMI namespace as the single source of truth:
        a service is only considered active when its code appears in
        ``SecurityServicesRunning``. Service codes used here:

        * ``3`` — System Guard Secure Launch
        * ``4`` — SMM Firmware Measurement
        * ``7`` — HyperGuard / Kernel-mode Code Integrity hardening
        """
        data = self._wmi_device_guard()
        running = set(data.get("SecurityServicesRunning") or [])
        return bool(running & {3, 4, 7})

    def smart_app_control_state(self) -> str:
        """#13 — Smart App Control state (``Off``/``Monitoring``/``On``)."""
        result = self._registry.read_value(
            r"HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy",
            "VerifiedAndReputablePolicyState",
        )
        if result is None:
            return "Unknown"
        _, value = result
        try:
            state = int(value)
        except (TypeError, ValueError):
            logger.debug("Unexpected Smart App Control value: %r", value)
            return "Unknown"
        return {0: "Off", 1: "On", 2: "Monitoring"}.get(state, "Unknown")

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

    def faceit_installed(self) -> bool:
        """True when the FACEIT service exists in the SCM (whether or not running)."""
        if not self.is_windows():
            return False
        return any(
            self._sc_query(service_name) is not None
            for service_name in FACEIT_SERVICE_NAMES
        )

    def faceit_status(self) -> str:
        """Return ``"Active"``, ``"Disabled"`` or ``"Not Installed"`` for FACEIT."""
        if not self.faceit_installed():
            return "Not Installed"
        return "Active" if self.faceit_present() else "Disabled"

    def snapshot_all(self) -> list[FeatureSnapshot]:
        """Return a :class:`FeatureSnapshot` for each of the 14 features."""
        dg = self._wmi_device_guard()
        vbs_code = int(dg.get("VirtualizationBasedSecurityStatus", 0))

        def _yn(flag: bool, on: str = "Active", off: str = "Disabled") -> str:
            return on if flag else off

        vbs_label = {0: "Disabled", 1: "Enabled", 2: "Active"}.get(vbs_code, "Unknown")
        dse = self.driver_signature_status()
        sac = self.smart_app_control_state()
        cg = self.credential_guard_state()
        kva = self.kva_shadow_state()
        faceit = self.faceit_status()
        hyper = _yn(self.hypervisor_present())

        return [
            FeatureSnapshot(
                1,
                "Virtualization (VT-x/SVM)",
                _yn(self.virtualization_enabled(), on="Enabled", off="Disabled"),
            ),
            FeatureSnapshot(
                2,
                "WMI (WinMgmt)",
                _yn(self.wmi_healthy(), on="Functional", off="Failed"),
            ),
            FeatureSnapshot(3, "VBS (Virt-Based Security)", vbs_label),
            FeatureSnapshot(4, "HVCI (Memory Integrity)", _yn(self.hvci_active())),
            FeatureSnapshot(5, "Credential Guard", cg),
            FeatureSnapshot(6, "Driver Signature Enf.", dse),
            FeatureSnapshot(7, "KVA Shadow (Meltdown)", kva),
            FeatureSnapshot(8, "Windows Hypervisor", hyper),
            FeatureSnapshot(9, "FACEIT Anti-Cheat", faceit),
            FeatureSnapshot(10, "Windows Hello Protection", _yn(self.windows_hello_enabled())),
            FeatureSnapshot(11, "Secure Biometrics", _yn(self.secure_biometrics_enabled())),
            FeatureSnapshot(12, "HyperGuard / Sys Guard", _yn(self.hyperguard_enabled())),
            FeatureSnapshot(13, "Smart App Control", sac),
            FeatureSnapshot(
                14,
                "BitLocker",
                _yn(self.bitlocker_active(), on="Active", off="Suspended"),
            ),
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

    def _sc_query(self, service_name: str) -> str | None:
        if not self.is_windows():
            return None
        try:
            result = subprocess.run(
                ["sc", "query", service_name],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        return result.stdout


__all__ = ["FeatureSnapshot", "SystemInfo"]
