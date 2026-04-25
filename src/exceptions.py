"""Custom exception hierarchy for HyperGuard92."""

from __future__ import annotations


class HyperGuardError(Exception):
    """Base class for all application errors."""

    exit_code: int = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class ConfigurationError(HyperGuardError):
    """Invalid or missing configuration."""

    exit_code = 2


class PreflightError(HyperGuardError):
    """Environment prerequisites are not met."""

    exit_code = 3


class PrivilegeError(PreflightError):
    """The process is not running with Administrator rights."""


class RegistryError(HyperGuardError):
    """Failure while reading or writing the Windows Registry."""

    exit_code = 10


class BackupError(RegistryError):
    """Registry backup could not be written or restored."""


class BcdError(HyperGuardError):
    """``bcdedit`` invocation failed or returned unexpected output."""

    exit_code = 11


class ServiceControlError(HyperGuardError):
    """Failure while interacting with the Service Control Manager."""

    exit_code = 12


class BitLockerError(HyperGuardError):
    """``manage-bde`` invocation failed."""

    exit_code = 13


class EfiError(HyperGuardError):
    """EFI / ``SecConfig.efi`` orchestration failed."""

    exit_code = 14


class SystemInfoError(HyperGuardError):
    """Could not determine the current state of a feature."""

    exit_code = 15


__all__ = [
    "HyperGuardError",
    "ConfigurationError",
    "PreflightError",
    "PrivilegeError",
    "RegistryError",
    "BackupError",
    "BcdError",
    "ServiceControlError",
    "BitLockerError",
    "EfiError",
    "SystemInfoError",
]
