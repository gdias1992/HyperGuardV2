"""Environment pre-flight checks (admin, WMI, VT-x, OS build, SAC)."""

from __future__ import annotations

import ctypes
import platform
import sys
from dataclasses import dataclass, field

from src.services.system_info import SystemInfo
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PreflightReport:
    """Aggregated result of all pre-flight checks."""

    is_admin: bool = False
    is_windows: bool = False
    os_build: int = 0
    virtualization: bool = False
    wmi_healthy: bool = False
    smart_app_control: str = "Unknown"
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when the critical prerequisites (admin + WMI + VT-x) are met."""
        return self.is_admin and self.wmi_healthy and self.virtualization


class Preflight:
    """Run environment checks required before applying any mutation."""

    def __init__(self, system_info: SystemInfo | None = None) -> None:
        self._sys = system_info or SystemInfo()

    # ------------------------------------------------------------------
    # Individual probes
    # ------------------------------------------------------------------

    @staticmethod
    def is_admin() -> bool:
        """Return ``True`` when the current process has Administrator rights."""
        if platform.system() != "Windows":
            return False
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - Windows-only
            logger.warning("IsUserAnAdmin failed: %s", exc)
            return False

    @staticmethod
    def os_build() -> int:
        """Return the current Windows build number (0 elsewhere)."""
        if platform.system() != "Windows":
            return 0
        try:
            release = sys.getwindowsversion()  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover
            return 0
        return int(getattr(release, "build", 0))

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(self) -> PreflightReport:
        """Run all probes and return a :class:`PreflightReport`."""
        report = PreflightReport(
            is_windows=platform.system() == "Windows",
            is_admin=self.is_admin(),
            os_build=self.os_build(),
            virtualization=self._sys.virtualization_enabled(),
            wmi_healthy=self._sys.wmi_healthy(),
            smart_app_control=self._sys.smart_app_control_state(),
        )
        if not report.is_admin:
            report.warnings.append("Administrator privileges are required.")
        if not report.wmi_healthy:
            report.warnings.append(
                "WMI is not responding — several detections will be unreliable."
            )
        if not report.virtualization:
            report.warnings.append(
                "BIOS virtualization (VT-x / AMD-V) is disabled — enable it first."
            )
        if report.smart_app_control == "On":
            report.warnings.append(
                "Smart App Control is enforcing. Some mutations may be blocked."
            )
        if report.os_build and report.os_build < 19041:
            report.warnings.append(
                "Windows build is older than 20H1 — several features may be missing."
            )
        return report


__all__ = ["Preflight", "PreflightReport"]
