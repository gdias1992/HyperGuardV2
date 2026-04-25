"""State and result models used by the service layer.

These Pydantic models guard every registry / BCD / service mutation. They
describe:

* :class:`SafeState` — the *approved* target states for each feature.
* :class:`BackupEntry` — a snapshot of a registry value before mutation.
* :class:`OperationResult` — the outcome of a single operation step.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class OperationStatus(str, Enum):
    """Outcome of a single service operation."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    REQUIRES_REBOOT = "requires_reboot"
    DRY_RUN = "dry_run"


class RegistryValueType(str, Enum):
    """Subset of ``winreg`` value types we write."""

    REG_DWORD = "REG_DWORD"
    REG_QWORD = "REG_QWORD"
    REG_SZ = "REG_SZ"
    REG_EXPAND_SZ = "REG_EXPAND_SZ"
    REG_BINARY = "REG_BINARY"
    REG_MULTI_SZ = "REG_MULTI_SZ"


class BackupEntry(BaseModel):
    """Snapshot of a registry value captured before mutation."""

    model_config = ConfigDict(frozen=True)

    key_path: str = Field(
        ...,
        description="Full registry path (e.g. ``HKLM\\SOFTWARE\\...``).",
    )
    value_name: str = Field(..., description="Name of the value inside the key.")
    value_type: RegistryValueType = Field(
        ..., description="Registry value type recorded at backup time."
    )
    original_value: Any = Field(
        default=None,
        description="Original value. ``None`` means the value did not exist.",
    )
    existed: bool = Field(
        ..., description="Whether the value existed prior to mutation."
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the backup was captured.",
    )


class SafeState(BaseModel):
    """A validated target state for a single feature.

    ``SafeState`` intentionally constrains the set of acceptable values we will
    ever write so typos or copy/paste accidents cannot brick a machine.
    """

    model_config = ConfigDict(frozen=True)

    feature_id: int = Field(..., ge=1, le=14)
    feature_name: str = Field(..., min_length=1)
    action: Literal[
        "disable",
        "enable",
        "suspend",
        "remove",
        "monitor",
        "noop",
    ] = Field(..., description="High-level action taken against the feature.")
    target_registry_value: int | None = Field(
        None,
        description="Target DWORD when the action writes a registry value.",
    )
    requires_reboot: bool = Field(
        False, description="Whether completing the action requires a reboot."
    )


class OperationResult(BaseModel):
    """Outcome of a single service operation (one feature / one step)."""

    feature_id: int | None = Field(
        None, description="Owning feature id, when applicable."
    )
    step: str = Field(..., description="Human-readable operation label.")
    status: OperationStatus
    message: str = Field("", description="Supplementary detail for the operator.")
    requires_reboot: bool = Field(False)
    backups: list[BackupEntry] = Field(
        default_factory=list, description="Backups captured while executing this step."
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @property
    def ok(self) -> bool:
        """True when the step succeeded (or was a dry-run / skip, non-failing)."""
        return self.status not in {OperationStatus.FAILED}


__all__ = [
    "BackupEntry",
    "OperationResult",
    "OperationStatus",
    "RegistryValueType",
    "SafeState",
]
