"""Service layer for HyperGuard92.

Each module in this package wraps a single Windows technology surface (registry,
BCD, services, BitLocker, EFI). The :class:`~src.services.vbs_service.VbsService`
orchestrates them to deliver the high-level *PIRATE MODE* / *DEFENDER MODE*
workflows surfaced by the GUI.
"""

from src.services.bcd_ops import BcdOps
from src.services.bitlocker_ops import BitlockerOps
from src.services.efi_ops import EfiOps
from src.services.preflight import Preflight, PreflightReport
from src.services.registry_ops import RegistryOps
from src.services.service_ops import ServiceOps
from src.services.system_info import FeatureSnapshot, SystemInfo
from src.services.vbs_service import VbsService

__all__ = [
    "BcdOps",
    "BitlockerOps",
    "EfiOps",
    "FeatureSnapshot",
    "Preflight",
    "PreflightReport",
    "RegistryOps",
    "ServiceOps",
    "SystemInfo",
    "VbsService",
]
