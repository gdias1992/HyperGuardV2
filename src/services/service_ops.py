"""Service Control Manager helpers (start / stop / disable services).

Used primarily to take FACEIT's kernel-level anti-cheat out of the boot chain
before applying VBS mutations.
"""

from __future__ import annotations

import subprocess

from src.config import settings
from src.exceptions import ServiceControlError
from src.models.state import OperationResult, OperationStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - platform specific
    import win32service  # type: ignore[import-not-found]
    import win32serviceutil  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - non-Windows
    win32service = None  # type: ignore[assignment]
    win32serviceutil = None  # type: ignore[assignment]


FACEIT_SERVICES: tuple[str, ...] = ("FACEIT", "FACEITService")


class ServiceOps:
    """Stop / disable Windows services through ``win32service``.

    A ``subprocess`` fallback to ``sc.exe`` is used whenever ``pywin32`` is not
    available (e.g. during CI runs on Linux).
    """

    def __init__(self, dry_run: bool | None = None) -> None:
        self.dry_run = settings.dry_run if dry_run is None else dry_run

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def exists(self, name: str) -> bool:
        """Return True when service ``name`` is registered with the SCM."""
        if win32service is None:
            return self._sc_query(name) is not None
        try:
            scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
        except Exception as exc:  # pragma: no cover - Windows-only
            raise ServiceControlError(f"OpenSCManager failed: {exc}") from exc
        try:
            try:
                handle = win32service.OpenService(
                    scm, name, win32service.SERVICE_QUERY_STATUS
                )
            except Exception:
                return False
            win32service.CloseServiceHandle(handle)
            return True
        finally:
            win32service.CloseServiceHandle(scm)

    def _sc_query(self, name: str) -> str | None:
        try:
            result = subprocess.run(
                ["sc", "query", name],
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

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def stop(self, name: str) -> OperationResult:
        """Stop service ``name`` if it is running."""
        if self.dry_run:
            logger.info("[DRY-RUN] Would stop service %s", name)
            return OperationResult(
                step=f"stop {name}",
                status=OperationStatus.DRY_RUN,
                message="Dry-run: service left untouched.",
            )

        if win32serviceutil is not None:
            try:
                win32serviceutil.StopService(name)
            except Exception as exc:  # pragma: no cover - Windows-only
                if "1062" in str(exc):  # already stopped
                    return OperationResult(
                        step=f"stop {name}",
                        status=OperationStatus.SKIPPED,
                        message="Service already stopped.",
                    )
                raise ServiceControlError(f"Failed to stop {name}: {exc}") from exc
            return OperationResult(
                step=f"stop {name}",
                status=OperationStatus.SUCCESS,
            )

        # Fallback via sc.exe
        result = subprocess.run(
            ["sc", "stop", name], capture_output=True, text=True, check=False
        )
        if result.returncode not in (0, 1062):
            raise ServiceControlError(
                f"sc stop {name} failed (rc={result.returncode}): {result.stderr.strip()}"
            )
        return OperationResult(step=f"stop {name}", status=OperationStatus.SUCCESS)

    def disable(self, name: str) -> OperationResult:
        """Set service ``name`` start type to ``disabled``."""
        if self.dry_run:
            logger.info("[DRY-RUN] Would disable service %s", name)
            return OperationResult(
                step=f"disable {name}",
                status=OperationStatus.DRY_RUN,
            )

        if win32service is not None:
            try:
                scm = win32service.OpenSCManager(
                    None, None, win32service.SC_MANAGER_CONNECT
                )
                try:
                    handle = win32service.OpenService(
                        scm, name, win32service.SERVICE_CHANGE_CONFIG
                    )
                    try:
                        win32service.ChangeServiceConfig(
                            handle,
                            win32service.SERVICE_NO_CHANGE,
                            win32service.SERVICE_DISABLED,
                            win32service.SERVICE_NO_CHANGE,
                            None,
                            None,
                            False,
                            None,
                            None,
                            None,
                            None,
                        )
                    finally:
                        win32service.CloseServiceHandle(handle)
                finally:
                    win32service.CloseServiceHandle(scm)
            except Exception as exc:  # pragma: no cover - Windows-only
                raise ServiceControlError(
                    f"Failed to disable {name}: {exc}"
                ) from exc
            return OperationResult(step=f"disable {name}", status=OperationStatus.SUCCESS)

        result = subprocess.run(
            ["sc", "config", name, "start=", "disabled"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ServiceControlError(
                f"sc config {name} failed (rc={result.returncode}): {result.stderr.strip()}"
            )
        return OperationResult(step=f"disable {name}", status=OperationStatus.SUCCESS)

    def set_start_type(self, name: str, start_type: str) -> OperationResult:
        """Set start type to ``auto`` / ``demand`` / ``disabled`` etc."""
        allowed = {"auto", "demand", "disabled", "boot", "system"}
        if start_type not in allowed:
            raise ServiceControlError(
                f"Unsafe start type {start_type!r}; allowed={sorted(allowed)}"
            )
        if self.dry_run:
            return OperationResult(
                step=f"sc config {name} start={start_type}",
                status=OperationStatus.DRY_RUN,
            )
        result = subprocess.run(
            ["sc", "config", name, "start=", start_type],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ServiceControlError(
                f"sc config {name} failed (rc={result.returncode}): {result.stderr.strip()}"
            )
        return OperationResult(
            step=f"sc config {name} start={start_type}",
            status=OperationStatus.SUCCESS,
        )

    # ------------------------------------------------------------------
    # Orchestration helper
    # ------------------------------------------------------------------

    def disable_faceit(self) -> list[OperationResult]:
        """Stop and permanently disable FACEIT services."""
        results: list[OperationResult] = []
        for svc in FACEIT_SERVICES:
            if not self.exists(svc):
                results.append(
                    OperationResult(
                        feature_id=9,
                        step=f"stop {svc}",
                        status=OperationStatus.SKIPPED,
                        message="Service not installed.",
                    )
                )
                continue
            try:
                stop_result = self.stop(svc)
                stop_result = stop_result.model_copy(update={"feature_id": 9})
                results.append(stop_result)
                disable_result = self.disable(svc).model_copy(update={"feature_id": 9})
                results.append(disable_result)
            except ServiceControlError as exc:
                results.append(
                    OperationResult(
                        feature_id=9,
                        step=f"disable {svc}",
                        status=OperationStatus.FAILED,
                        message=str(exc),
                    )
                )
        return results


__all__ = ["FACEIT_SERVICES", "ServiceOps"]
