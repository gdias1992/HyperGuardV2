"""BitLocker helpers built around ``manage-bde``."""

from __future__ import annotations

import re
import subprocess

from src.config import settings
from src.exceptions import BitLockerError
from src.models.state import OperationResult, OperationStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


_SAFE_DRIVE_RE = re.compile(r"^[A-Za-z]:$")


class BitlockerOps:
    """Suspend / resume BitLocker protectors."""

    def __init__(self, dry_run: bool | None = None) -> None:
        self.dry_run = settings.dry_run if dry_run is None else dry_run

    @staticmethod
    def _validate_drive(drive: str) -> str:
        if not _SAFE_DRIVE_RE.match(drive):
            raise BitLockerError(f"Unsafe drive argument: {drive!r}")
        return drive.upper()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = ["manage-bde", *args]
        if self.dry_run:
            logger.info("[DRY-RUN] Would run: %s", " ".join(command))
            return subprocess.CompletedProcess(command, 0, "", "")
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=60, check=False
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise BitLockerError(f"manage-bde invocation failed: {exc}") from exc
        if result.returncode != 0:
            raise BitLockerError(
                f"manage-bde {' '.join(args)} failed (rc={result.returncode}): "
                f"{result.stderr.strip()}"
            )
        return result

    def status(self, drive: str = "C:") -> str:
        """Return the raw ``manage-bde -status`` output for ``drive``."""
        drive = self._validate_drive(drive)
        return self._run("-status", drive).stdout

    def is_protected(self, drive: str = "C:") -> bool:
        """Return ``True`` when BitLocker protection is currently on."""
        try:
            text = self.status(drive).lower()
        except BitLockerError as exc:
            logger.warning("Could not read BitLocker status: %s", exc)
            return False
        return "protection on" in text

    def suspend(self, drive: str = "C:", reboot_count: int = 1) -> OperationResult:
        """Suspend protectors for ``reboot_count`` reboots (minimum 1)."""
        drive = self._validate_drive(drive)
        if reboot_count < 1:
            raise BitLockerError("reboot_count must be >= 1.")
        self._run(
            "-protectors", "-disable", drive, "-rebootcount", str(reboot_count)
        )
        return OperationResult(
            feature_id=14,
            step=f"manage-bde -protectors -disable {drive} -rebootcount {reboot_count}",
            status=OperationStatus.DRY_RUN if self.dry_run else OperationStatus.SUCCESS,
            message="BitLocker suspended for the next boot.",
        )

    def resume(self, drive: str = "C:") -> OperationResult:
        """Re-enable BitLocker protectors on ``drive``."""
        drive = self._validate_drive(drive)
        self._run("-protectors", "-enable", drive)
        return OperationResult(
            feature_id=14,
            step=f"manage-bde -protectors -enable {drive}",
            status=OperationStatus.DRY_RUN if self.dry_run else OperationStatus.SUCCESS,
            message="BitLocker protectors re-enabled.",
        )


__all__ = ["BitlockerOps"]
