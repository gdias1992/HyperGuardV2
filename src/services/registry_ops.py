"""Safe Windows Registry operations with backup/restore support.

All mutations go through :class:`RegistryOps` which:

* validates the target state against :class:`~src.models.state.SafeState`-style
  inputs before writing;
* captures the previous value into ``HKLM\\SOFTWARE\\HyperGuard92\\Backups``
  before every mutation;
* honours the global ``settings.dry_run`` flag.

``winreg`` is Windows-only. On other platforms the module still imports — tests
must monkey-patch :data:`winreg` to exercise the logic on CI.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

try:  # pragma: no cover - platform specific
    import winreg  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - executed on non-Windows test runners
    winreg = None  # type: ignore[assignment]

from src.config import settings
from src.exceptions import BackupError, RegistryError
from src.models.state import BackupEntry, RegistryValueType
from src.utils.logging import get_logger

logger = get_logger(__name__)


BACKUP_ROOT = r"SOFTWARE\HyperGuard92\Backups"

# Map between winreg constants and our portable enum.
_TYPE_TO_ENUM: dict[int, RegistryValueType] = {}
_ENUM_TO_TYPE: dict[RegistryValueType, int] = {}


def _ensure_type_tables() -> None:
    """Populate the winreg<->enum lookup tables once winreg is available."""
    if _TYPE_TO_ENUM or winreg is None:
        return
    _TYPE_TO_ENUM.update(
        {
            winreg.REG_DWORD: RegistryValueType.REG_DWORD,
            winreg.REG_QWORD: RegistryValueType.REG_QWORD,
            winreg.REG_SZ: RegistryValueType.REG_SZ,
            winreg.REG_EXPAND_SZ: RegistryValueType.REG_EXPAND_SZ,
            winreg.REG_BINARY: RegistryValueType.REG_BINARY,
            winreg.REG_MULTI_SZ: RegistryValueType.REG_MULTI_SZ,
        }
    )
    _ENUM_TO_TYPE.update({v: k for k, v in _TYPE_TO_ENUM.items()})


_ROOT_ALIASES: dict[str, str] = {
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCU": "HKEY_CURRENT_USER",
    "HKCR": "HKEY_CLASSES_ROOT",
    "HKU": "HKEY_USERS",
    "HKCC": "HKEY_CURRENT_CONFIG",
}


def parse_key_path(path: str) -> tuple[int, str, str]:
    """Split ``HKLM\\SOFTWARE\\Foo`` into ``(root_handle, subkey, canonical_root)``.

    Raises:
        RegistryError: If the root hive cannot be recognised.
    """
    if winreg is None:  # pragma: no cover - guarded at runtime
        raise RegistryError("winreg is not available on this platform.")
    if "\\" not in path:
        raise RegistryError(f"Invalid registry path (no sub-key): {path!r}")

    root_token, _, subkey = path.partition("\\")
    canonical = _ROOT_ALIASES.get(root_token.upper(), root_token.upper())
    root_attr = canonical
    if not hasattr(winreg, root_attr):
        raise RegistryError(f"Unknown registry root: {root_token!r}")
    return getattr(winreg, root_attr), subkey, canonical


class RegistryOps:
    """Read/write/delete registry values with automatic backup."""

    def __init__(self, dry_run: bool | None = None) -> None:
        """Create a new ``RegistryOps``.

        Args:
            dry_run: Override the global ``settings.dry_run``. When true, no
                mutation is performed but the intended action is logged.
        """
        self.dry_run = settings.dry_run if dry_run is None else dry_run
        self._backups: list[BackupEntry] = []
        _ensure_type_tables()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def backups(self) -> list[BackupEntry]:
        """Backups captured during the life of this instance."""
        return list(self._backups)

    def read_value(
        self, key_path: str, value_name: str
    ) -> tuple[RegistryValueType, Any] | None:
        """Read ``(type, data)`` from the registry, or ``None`` if absent."""
        if winreg is None:
            raise RegistryError("winreg is not available on this platform.")
        root, subkey, _ = parse_key_path(key_path)
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as handle:
                data, raw_type = winreg.QueryValueEx(handle, value_name)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise RegistryError(
                f"Failed to read {key_path}\\{value_name}: {exc}"
            ) from exc
        return _TYPE_TO_ENUM.get(raw_type, RegistryValueType.REG_SZ), data

    def backup(self, key_path: str, value_name: str) -> BackupEntry:
        """Capture the current value of ``key_path\\value_name``.

        The backup is recorded both in-memory and persisted under
        ``HKLM\\SOFTWARE\\HyperGuard92\\Backups`` so a later session can restore
        the value.
        """
        current = self.read_value(key_path, value_name)
        if current is None:
            entry = BackupEntry(
                key_path=key_path,
                value_name=value_name,
                value_type=RegistryValueType.REG_SZ,
                original_value=None,
                existed=False,
            )
        else:
            value_type, data = current
            entry = BackupEntry(
                key_path=key_path,
                value_name=value_name,
                value_type=value_type,
                original_value=data,
                existed=True,
            )
        self._persist_backup(entry)
        self._backups.append(entry)
        logger.debug(
            "Captured backup %s\\%s (existed=%s)",
            key_path,
            value_name,
            entry.existed,
        )
        return entry

    def write_value(
        self,
        key_path: str,
        value_name: str,
        value_type: RegistryValueType,
        data: Any,
    ) -> BackupEntry:
        """Write ``data`` to ``key_path\\value_name`` after capturing a backup.

        Returns the :class:`BackupEntry` describing the previous state.
        """
        backup = self.backup(key_path, value_name)

        if self.dry_run:
            logger.info(
                "[DRY-RUN] Would write %s=%r (%s) to %s",
                value_name,
                data,
                value_type.value,
                key_path,
            )
            return backup

        if winreg is None:  # pragma: no cover - runtime guard
            raise RegistryError("winreg is not available on this platform.")

        root, subkey, _ = parse_key_path(key_path)
        raw_type = _ENUM_TO_TYPE.get(value_type)
        if raw_type is None:
            raise RegistryError(f"Unsupported registry type: {value_type}")

        try:
            with winreg.CreateKeyEx(root, subkey, 0, winreg.KEY_SET_VALUE) as handle:
                winreg.SetValueEx(handle, value_name, 0, raw_type, data)
        except OSError as exc:
            raise RegistryError(
                f"Failed to write {key_path}\\{value_name}: {exc}"
            ) from exc

        logger.info(
            "Wrote %s\\%s = %r (%s)", key_path, value_name, data, value_type.value
        )
        return backup

    def delete_value(self, key_path: str, value_name: str) -> BackupEntry:
        """Delete ``key_path\\value_name`` after capturing a backup."""
        backup = self.backup(key_path, value_name)
        if not backup.existed:
            logger.debug(
                "Skipping delete: %s\\%s already absent", key_path, value_name
            )
            return backup

        if self.dry_run:
            logger.info("[DRY-RUN] Would delete %s\\%s", key_path, value_name)
            return backup

        if winreg is None:  # pragma: no cover
            raise RegistryError("winreg is not available on this platform.")

        root, subkey, _ = parse_key_path(key_path)
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE) as handle:
                winreg.DeleteValue(handle, value_name)
        except FileNotFoundError:
            return backup
        except OSError as exc:
            raise RegistryError(
                f"Failed to delete {key_path}\\{value_name}: {exc}"
            ) from exc

        logger.info("Deleted %s\\%s", key_path, value_name)
        return backup

    def restore(self, entry: BackupEntry) -> None:
        """Restore the registry state described by ``entry``."""
        if self.dry_run:
            logger.info(
                "[DRY-RUN] Would restore %s\\%s (existed=%s)",
                entry.key_path,
                entry.value_name,
                entry.existed,
            )
            return

        if not entry.existed:
            # Value did not exist — delete whatever is there now.
            try:
                self.delete_value(entry.key_path, entry.value_name)
            except RegistryError as exc:  # pragma: no cover - defensive
                raise BackupError(
                    f"Failed to undo creation of {entry.key_path}\\{entry.value_name}: {exc}"
                ) from exc
            return

        if winreg is None:  # pragma: no cover
            raise BackupError("winreg is not available on this platform.")

        root, subkey, _ = parse_key_path(entry.key_path)
        raw_type = _ENUM_TO_TYPE.get(entry.value_type)
        if raw_type is None:
            raise BackupError(f"Unsupported backup type: {entry.value_type}")

        try:
            with winreg.CreateKeyEx(root, subkey, 0, winreg.KEY_SET_VALUE) as handle:
                winreg.SetValueEx(
                    handle, entry.value_name, 0, raw_type, entry.original_value
                )
        except OSError as exc:
            raise BackupError(
                f"Failed to restore {entry.key_path}\\{entry.value_name}: {exc}"
            ) from exc

        logger.info(
            "Restored %s\\%s = %r",
            entry.key_path,
            entry.value_name,
            entry.original_value,
        )

    # ------------------------------------------------------------------
    # Backup persistence
    # ------------------------------------------------------------------

    def _persist_backup(self, entry: BackupEntry) -> None:
        """Persist ``entry`` under ``HKLM\\SOFTWARE\\HyperGuard92\\Backups``."""
        if self.dry_run or winreg is None:
            return

        token = hashlib.sha1(
            f"{entry.key_path}|{entry.value_name}|{entry.timestamp.isoformat()}".encode()
        ).hexdigest()[:16]
        sub = f"{BACKUP_ROOT}\\{token}"
        payload = entry.model_dump(mode="json")
        try:
            with winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, sub, 0, winreg.KEY_SET_VALUE
            ) as handle:
                winreg.SetValueEx(
                    handle, "payload", 0, winreg.REG_SZ, json.dumps(payload)
                )
        except OSError as exc:
            # Persisting a backup should not abort the calling operation.
            logger.warning(
                "Could not persist backup for %s\\%s: %s",
                entry.key_path,
                entry.value_name,
                exc,
            )

    @classmethod
    def load_persisted_backups(cls) -> list[BackupEntry]:
        """Load every persisted backup from the registry.

        Returns an empty list on non-Windows platforms or when the backup tree
        has not yet been created.
        """
        if winreg is None:
            return []
        entries: list[BackupEntry] = []
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, BACKUP_ROOT, 0, winreg.KEY_READ
            ) as root_handle:
                index = 0
                while True:
                    try:
                        name = winreg.EnumKey(root_handle, index)
                    except OSError:
                        break
                    index += 1
                    sub_path = f"{BACKUP_ROOT}\\{name}"
                    try:
                        with winreg.OpenKey(
                            winreg.HKEY_LOCAL_MACHINE,
                            sub_path,
                            0,
                            winreg.KEY_READ,
                        ) as handle:
                            raw, _ = winreg.QueryValueEx(handle, "payload")
                    except OSError:
                        continue
                    try:
                        data = json.loads(raw)
                        if "timestamp" in data and isinstance(data["timestamp"], str):
                            data["timestamp"] = datetime.fromisoformat(
                                data["timestamp"].replace("Z", "+00:00")
                            ).astimezone(timezone.utc)
                        entries.append(BackupEntry.model_validate(data))
                    except (ValueError, TypeError) as exc:
                        logger.warning(
                            "Skipping corrupt backup entry %s: %s", sub_path, exc
                        )
        except FileNotFoundError:
            return []
        except OSError as exc:  # pragma: no cover
            logger.warning("Could not enumerate backups: %s", exc)
        return entries


__all__ = ["BACKUP_ROOT", "RegistryOps", "parse_key_path"]
