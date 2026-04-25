"""UEFI opt-out helpers.

Wraps the sequence used by ``VBS_1.6.2.cmd``:

1. ``mountvol`` the EFI System Partition.
2. Copy ``SecConfig.efi`` into it.
3. Configure a one-time ``bootmgfw`` entry to launch ``SecConfig.efi``.
4. ``certutil -DeleteHelloContainer`` to purge Windows Hello TPM secrets.

Only the higher-level coordination is implemented here — raw ``subprocess``
invocations stay explicit so they remain auditable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.config import settings
from src.exceptions import EfiError
from src.models.state import OperationResult, OperationStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EfiOps:
    """Orchestrate the UEFI lock-out workflow."""

    def __init__(self, dry_run: bool | None = None) -> None:
        self.dry_run = settings.dry_run if dry_run is None else dry_run

    # ------------------------------------------------------------------
    # Primitive invocations
    # ------------------------------------------------------------------

    def _run(self, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        if self.dry_run:
            logger.info("[DRY-RUN] Would run: %s", " ".join(args))
            return subprocess.CompletedProcess(list(args), 0, "", "")
        try:
            result = subprocess.run(
                list(args),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise EfiError(f"Command failed ({' '.join(args)}): {exc}") from exc
        if result.returncode != 0:
            raise EfiError(
                f"{' '.join(args)} failed (rc={result.returncode}): "
                f"{result.stderr.strip()}"
            )
        return result

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def mount_efi(self, letter: str = "Y:") -> OperationResult:
        """Expose the EFI System Partition at ``letter``."""
        if not letter.endswith(":") or len(letter) != 2:
            raise EfiError(f"Unsafe mount letter: {letter!r}")
        self._run("mountvol", letter, "/s")
        return OperationResult(
            step=f"mountvol {letter} /s",
            status=OperationStatus.DRY_RUN if self.dry_run else OperationStatus.SUCCESS,
        )

    def unmount_efi(self, letter: str = "Y:") -> OperationResult:
        """Release the ESP mount created by :meth:`mount_efi`."""
        self._run("mountvol", letter, "/d")
        return OperationResult(
            step=f"mountvol {letter} /d",
            status=OperationStatus.DRY_RUN if self.dry_run else OperationStatus.SUCCESS,
        )

    def delete_hello_container(self) -> OperationResult:
        """``certutil -DeleteHelloContainer`` — purge Windows Hello secrets."""
        self._run("certutil", "-DeleteHelloContainer", timeout=60)
        return OperationResult(
            feature_id=10,
            step="certutil -DeleteHelloContainer",
            status=OperationStatus.DRY_RUN if self.dry_run else OperationStatus.SUCCESS,
            requires_reboot=True,
            message="Windows Hello container deleted.",
        )

    def stage_secconfig(
        self,
        source: Path,
        esp_letter: str = "Y:",
        relative_target: str = r"EFI\Microsoft\Boot\SecConfig.efi",
    ) -> OperationResult:
        """Copy ``SecConfig.efi`` into the mounted ESP.

        Args:
            source: Path to the Windows-provided ``SecConfig.efi`` (usually at
                ``%SystemRoot%\\System32\\SecConfig.efi``).
            esp_letter: The drive letter used for :meth:`mount_efi`.
            relative_target: Relative target path under the ESP.
        """
        if self.dry_run:
            logger.info(
                "[DRY-RUN] Would copy %s -> %s\\%s", source, esp_letter, relative_target
            )
            return OperationResult(
                step=f"copy {source} -> {esp_letter}\\{relative_target}",
                status=OperationStatus.DRY_RUN,
            )
        if not source.exists():
            raise EfiError(f"SecConfig.efi not found at {source}")

        target = Path(f"{esp_letter}\\") / relative_target
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        except OSError as exc:
            raise EfiError(f"Failed to stage SecConfig.efi: {exc}") from exc
        return OperationResult(
            step=f"stage SecConfig.efi -> {target}",
            status=OperationStatus.SUCCESS,
        )


__all__ = ["EfiOps"]
