"""Wrappers around ``bcdedit`` for Boot Configuration Data mutations."""

from __future__ import annotations

import subprocess

from src.config import settings
from src.exceptions import BcdError
from src.models.state import OperationResult, OperationStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BcdOps:
    """Manipulate the BCD store through ``bcdedit``.

    Every mutation goes through :meth:`_run_bcdedit` which honours the global
    ``settings.dry_run`` flag.
    """

    def __init__(self, dry_run: bool | None = None) -> None:
        self.dry_run = settings.dry_run if dry_run is None else dry_run

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_bcdedit(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = ["bcdedit", *args]
        if self.dry_run:
            logger.info("[DRY-RUN] Would run: %s", " ".join(command))
            return subprocess.CompletedProcess(command, 0, "", "")
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=30, check=False
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise BcdError(f"bcdedit invocation failed: {exc}") from exc
        if result.returncode != 0:
            raise BcdError(
                f"bcdedit {' '.join(args)} failed "
                f"(rc={result.returncode}): {result.stderr.strip()}"
            )
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enum(self) -> str:
        """Return the textual output of ``bcdedit /enum``."""
        if self.dry_run:
            return ""
        return self._run_bcdedit("/enum").stdout

    def is_hypervisor_launch_off(self) -> bool:
        """Return ``True`` when ``hypervisorlaunchtype`` is ``off``."""
        try:
            output = self.enum().lower()
        except BcdError as exc:
            logger.warning("Could not enumerate BCD: %s", exc)
            return False
        for line in output.splitlines():
            if line.strip().startswith("hypervisorlaunchtype"):
                return line.strip().endswith("off")
        return False

    def set_hypervisor_launch(self, value: str) -> OperationResult:
        """Set ``hypervisorlaunchtype`` to ``auto`` / ``off``."""
        if value not in {"auto", "off"}:
            raise BcdError(f"Unsafe hypervisorlaunchtype value: {value!r}")
        self._run_bcdedit("/set", "hypervisorlaunchtype", value)
        return OperationResult(
            feature_id=8,
            step=f"bcdedit /set hypervisorlaunchtype {value}",
            status=OperationStatus.DRY_RUN if self.dry_run else OperationStatus.SUCCESS,
            requires_reboot=True,
            message=(
                "BCD updated. A reboot is required to take effect."
                if not self.dry_run
                else "Dry-run: no changes applied."
            ),
        )

    def enable_one_time_advanced_options(self) -> OperationResult:
        """Force the F7/Startup-Settings menu on the next boot (DSE toggle)."""
        self._run_bcdedit("/set", "{default}", "onetimeadvancedoptions", "on")
        return OperationResult(
            feature_id=6,
            step="bcdedit /set {default} onetimeadvancedoptions on",
            status=OperationStatus.DRY_RUN if self.dry_run else OperationStatus.SUCCESS,
            requires_reboot=True,
            message=(
                "Startup Settings menu will appear on next boot to disable DSE."
            ),
        )

    def clear_one_time_advanced_options(self) -> OperationResult:
        """Undo :meth:`enable_one_time_advanced_options`."""
        self._run_bcdedit("/deletevalue", "{default}", "onetimeadvancedoptions")
        return OperationResult(
            feature_id=6,
            step="bcdedit /deletevalue {default} onetimeadvancedoptions",
            status=OperationStatus.DRY_RUN if self.dry_run else OperationStatus.SUCCESS,
            requires_reboot=False,
            message="Cleared one-time Startup Settings flag.",
        )


__all__ = ["BcdOps"]
