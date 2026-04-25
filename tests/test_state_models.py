"""Tests for :mod:`src.models.state`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.state import (
    BackupEntry,
    OperationResult,
    OperationStatus,
    RegistryValueType,
    SafeState,
)


def test_safe_state_requires_feature_id_in_range() -> None:
    with pytest.raises(ValidationError):
        SafeState(feature_id=99, feature_name="x", action="disable")


def test_safe_state_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        SafeState(feature_id=1, feature_name="x", action="explode")  # type: ignore[arg-type]


def test_backup_entry_defaults_to_current_utc_timestamp() -> None:
    entry = BackupEntry(
        key_path=r"HKLM\SOFTWARE\X",
        value_name="V",
        value_type=RegistryValueType.REG_DWORD,
        original_value=0,
        existed=True,
    )
    assert entry.timestamp.tzinfo is not None


def test_operation_result_ok_property() -> None:
    ok = OperationResult(step="x", status=OperationStatus.SUCCESS)
    dry = OperationResult(step="x", status=OperationStatus.DRY_RUN)
    fail = OperationResult(step="x", status=OperationStatus.FAILED)
    assert ok.ok is True
    assert dry.ok is True
    assert fail.ok is False
