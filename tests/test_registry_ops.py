"""Tests for :mod:`src.services.registry_ops`.

The tests install a fake ``winreg`` module so they run on every OS.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.exceptions import RegistryError
from src.models.state import RegistryValueType
from src.services import registry_ops
from src.services.registry_ops import RegistryOps


class FakeKey:
    def __init__(self, store: dict[str, dict[str, tuple[int, Any]]], path: str) -> None:
        self.store = store
        self.path = path

    def __enter__(self) -> FakeKey:
        return self

    def __exit__(self, *_: Any) -> None:
        return None


class FakeWinreg:
    """Minimal stand-in for the ``winreg`` module used by the production code."""

    HKEY_LOCAL_MACHINE = "HKLM"
    HKEY_CURRENT_USER = "HKCU"
    REG_DWORD = 4
    REG_QWORD = 11
    REG_SZ = 1
    REG_EXPAND_SZ = 2
    REG_BINARY = 3
    REG_MULTI_SZ = 7
    KEY_READ = 1
    KEY_SET_VALUE = 2

    def __init__(self) -> None:
        self.store: dict[str, dict[str, tuple[int, Any]]] = {}

    # Key management --------------------------------------------------------
    def _abs(self, root: str, sub: str) -> str:
        return f"{root}\\{sub}"

    def OpenKey(self, root: str, sub: str, _reserved: int, _mask: int) -> FakeKey:  # noqa: N802
        path = self._abs(root, sub)
        if path not in self.store:
            raise FileNotFoundError(path)
        return FakeKey(self.store, path)

    def CreateKeyEx(self, root: str, sub: str, _reserved: int, _mask: int) -> FakeKey:  # noqa: N802
        path = self._abs(root, sub)
        # Register the key and every intermediate ancestor so OpenKey can walk it.
        parts = sub.split("\\")
        for i in range(1, len(parts) + 1):
            self.store.setdefault(self._abs(root, "\\".join(parts[:i])), {})
        return FakeKey(self.store, path)

    # Value operations ------------------------------------------------------
    def SetValueEx(  # noqa: N802
        self, handle: FakeKey, name: str, _reserved: int, raw_type: int, data: Any
    ) -> None:
        handle.store[handle.path][name] = (raw_type, data)

    def QueryValueEx(self, handle: FakeKey, name: str) -> tuple[Any, int]:  # noqa: N802
        values = handle.store[handle.path]
        if name not in values:
            raise FileNotFoundError(name)
        raw_type, data = values[name]
        return data, raw_type

    def DeleteValue(self, handle: FakeKey, name: str) -> None:  # noqa: N802
        values = handle.store[handle.path]
        if name not in values:
            raise FileNotFoundError(name)
        del values[name]

    def EnumKey(self, handle: FakeKey, index: int) -> str:  # noqa: N802
        # Return child keys whose parent matches handle.path
        prefix = handle.path + "\\"
        children = sorted(
            {
                k[len(prefix):].split("\\", 1)[0]
                for k in self.store
                if k.startswith(prefix)
            }
        )
        if index >= len(children):
            raise OSError("no more")
        return children[index]


@pytest.fixture
def fake_winreg(monkeypatch: pytest.MonkeyPatch) -> FakeWinreg:
    fake = FakeWinreg()
    monkeypatch.setattr(registry_ops, "winreg", fake)
    # Reset cached type tables between tests
    registry_ops._TYPE_TO_ENUM.clear()
    registry_ops._ENUM_TO_TYPE.clear()
    return fake


def test_parse_key_path_accepts_hklm_alias(fake_winreg: FakeWinreg) -> None:
    root, subkey, canonical = registry_ops.parse_key_path(r"HKLM\SOFTWARE\X")
    assert canonical == "HKEY_LOCAL_MACHINE"
    assert subkey == "SOFTWARE\\X"
    assert root == fake_winreg.HKEY_LOCAL_MACHINE


def test_parse_key_path_rejects_unknown_root(fake_winreg: FakeWinreg) -> None:
    with pytest.raises(RegistryError):
        registry_ops.parse_key_path(r"HKZZZ\something")


def test_read_value_returns_none_for_missing(fake_winreg: FakeWinreg) -> None:
    ops = RegistryOps(dry_run=False)
    assert ops.read_value(r"HKLM\SOFTWARE\Missing", "x") is None


def test_write_then_read(fake_winreg: FakeWinreg) -> None:
    ops = RegistryOps(dry_run=False)
    backup = ops.write_value(
        r"HKLM\SOFTWARE\Test", "V", RegistryValueType.REG_DWORD, 1
    )
    assert backup.existed is False
    result = ops.read_value(r"HKLM\SOFTWARE\Test", "V")
    assert result == (RegistryValueType.REG_DWORD, 1)


def test_backup_captures_existing_value(fake_winreg: FakeWinreg) -> None:
    ops = RegistryOps(dry_run=False)
    ops.write_value(r"HKLM\SOFTWARE\Test", "V", RegistryValueType.REG_DWORD, 7)
    entry = ops.backup(r"HKLM\SOFTWARE\Test", "V")
    assert entry.existed is True
    assert entry.original_value == 7
    assert entry.value_type == RegistryValueType.REG_DWORD


def test_delete_value_captures_backup(fake_winreg: FakeWinreg) -> None:
    ops = RegistryOps(dry_run=False)
    ops.write_value(r"HKLM\SOFTWARE\Test", "V", RegistryValueType.REG_DWORD, 42)
    entry = ops.delete_value(r"HKLM\SOFTWARE\Test", "V")
    assert entry.existed is True
    assert ops.read_value(r"HKLM\SOFTWARE\Test", "V") is None


def test_restore_replaces_previous_value(fake_winreg: FakeWinreg) -> None:
    ops = RegistryOps(dry_run=False)
    ops.write_value(r"HKLM\SOFTWARE\Test", "V", RegistryValueType.REG_DWORD, 7)
    entry = ops.write_value(r"HKLM\SOFTWARE\Test", "V", RegistryValueType.REG_DWORD, 0)
    assert entry.original_value == 7
    ops.restore(entry)
    assert ops.read_value(r"HKLM\SOFTWARE\Test", "V") == (
        RegistryValueType.REG_DWORD,
        7,
    )


def test_restore_missing_value_deletes_it(fake_winreg: FakeWinreg) -> None:
    ops = RegistryOps(dry_run=False)
    entry = ops.write_value(
        r"HKLM\SOFTWARE\Test", "V", RegistryValueType.REG_DWORD, 9
    )
    assert entry.existed is False
    ops.restore(entry)
    assert ops.read_value(r"HKLM\SOFTWARE\Test", "V") is None


def test_dry_run_does_not_mutate(fake_winreg: FakeWinreg) -> None:
    ops = RegistryOps(dry_run=True)
    ops.write_value(r"HKLM\SOFTWARE\Test", "V", RegistryValueType.REG_DWORD, 7)
    assert ops.read_value(r"HKLM\SOFTWARE\Test", "V") is None
    # Backup is still captured for traceability
    assert ops.backups and ops.backups[-1].key_path == r"HKLM\SOFTWARE\Test"


def test_persisted_backups_are_enumerable(fake_winreg: FakeWinreg) -> None:
    ops = RegistryOps(dry_run=False)
    ops.write_value(r"HKLM\SOFTWARE\Test", "A", RegistryValueType.REG_DWORD, 1)
    ops.write_value(r"HKLM\SOFTWARE\Test", "B", RegistryValueType.REG_SZ, "hi")
    entries = RegistryOps.load_persisted_backups()
    assert len(entries) >= 2
    paths = {(e.key_path, e.value_name) for e in entries}
    assert (r"HKLM\SOFTWARE\Test", "A") in paths
    assert (r"HKLM\SOFTWARE\Test", "B") in paths
