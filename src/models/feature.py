"""Feature domain model and the canonical seed list managed by HyperGuard92.

Mirrors the React prototype's ``INITIAL_FEATURES`` data with the same 14 rows.
"""

from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel, Field


class Feature(BaseModel):
    """A single Windows security feature tracked by the application."""

    id: int = Field(..., description="Stable identifier (1-based index).")
    name: str = Field(..., description="Human-readable feature name.")
    target: str = Field(..., description="Desired final state once optimized.")
    scope: str = Field(..., description="Where the feature lives (BIOS, Registry, BCD...).")
    status: str = Field(..., description="Current observed state.")
    locked: bool = Field(..., description="True if the feature cannot be toggled by the user.")
    desc: str = Field(..., description="Detailed technical explanation shown in tooltips.")


INITIAL_FEATURES: list[Feature] = [
    Feature(
        id=1,
        name="Virtualization (VT-x/SVM)",
        target="Enabled",
        scope="BIOS",
        status="Active",
        locked=True,
        desc=(
            "Hardware-level CPU virtualization extensions (Intel VT-x / AMD SVM). "
            "This allows the processor to trap specific instructions, manage Second Level "
            "Address Translation (SLAT), and control execution states. It is the fundamental "
            "prerequisite for VBS, Hyper-V, and third-party hypervisors. If disabled, the "
            "system cannot load hypervisor contexts."
        ),
    ),
    Feature(
        id=2,
        name="WMI (WinMgmt)",
        target="Functional",
        scope="System",
        status="Active",
        locked=True,
        desc=(
            "Windows Management Instrumentation. The core infrastructure for management data "
            "and operations. HyperGuard92 relies on WMI to query SMBIOS tables, motherboard "
            "configurations, and system health status. A corrupted WMI repository will prevent "
            "accurate system profiling."
        ),
    ),
    Feature(
        id=3,
        name="VBS (Virtualization Based Security)",
        target="Disabled",
        scope="Registry/UEFI",
        status="Active",
        locked=False,
        desc=(
            "Virtualization-Based Security uses the Windows Hypervisor to create an isolated "
            "memory enclave (Secure World) separate from the primary OS kernel (Normal World). "
            "This hardware-backed isolation prevents unauthorized code from accessing sensitive "
            "data, but its existence strictly blocks third-party hypervisors from acquiring "
            "Ring -1 privileges."
        ),
    ),
    Feature(
        id=4,
        name="HVCI (Memory Integrity)",
        target="Disabled",
        scope="Registry/UEFI",
        status="Active",
        locked=False,
        desc=(
            "Hypervisor-Enforced Code Integrity utilizes VBS to enforce kernel-mode code "
            "signing. It leverages SLAT to ensure that pages in kernel memory cannot be both "
            "Writable and Executable (W^X). This rigorously blocks unsigned drivers, manual "
            "mapping, and most custom kernel-level tools."
        ),
    ),
    Feature(
        id=5,
        name="Credential Guard",
        target="Disabled",
        scope="Registry/UEFI",
        status="Active",
        locked=False,
        desc=(
            "Defends against pass-the-hash and credential extraction by moving the Local "
            "Security Authority (LSA) secrets into the VBS Secure Enclave. Even with "
            "NT AUTHORITY\\SYSTEM privileges, the primary Windows kernel cannot read these "
            "isolated hashes."
        ),
    ),
    Feature(
        id=6,
        name="Driver Signature Enforcement",
        target="Disabled",
        scope="Boot",
        status="Active",
        locked=False,
        desc=(
            "Enforced by ci.dll (Code Integrity), DSE ensures only WHQL-signed `.sys` drivers "
            "are loaded into the Windows kernel. Disabling this allows loading custom or "
            "unsigned drivers, essential for certain deep-system optimizations or reversing "
            "tools."
        ),
    ),
    Feature(
        id=7,
        name="KVA Shadow (Meltdown)",
        target="Disabled",
        scope="Registry",
        status="Active",
        locked=False,
        desc=(
            "Kernel Virtual Address Shadowing is a mitigation for the Meltdown vulnerability "
            "(CVE-2017-5754). It separates user and kernel page tables. Disabling KVA Shadow "
            "reduces syscall overhead and is often required by specialized hooks that "
            "manipulate memory pagetables directly."
        ),
    ),
    Feature(
        id=8,
        name="Windows Hypervisor",
        target="Disabled",
        scope="BCD",
        status="Active",
        locked=False,
        desc=(
            "The bare-metal hypervisor loaded before the Windows kernel (hvloader.efi). "
            "Setting `hypervisorlaunchtype` to `off` in the Boot Configuration Data (BCD) "
            "disables Hyper-V entirely, freeing up VT-x/SVM locks for third-party "
            "virtualization software."
        ),
    ),
    Feature(
        id=9,
        name="FACEIT Anti-Cheat",
        target="Disabled",
        scope="Service",
        status="Active",
        locked=False,
        desc=(
            "An aggressive Ring 0 anti-cheat service that actively blocks hypervisor "
            "initialization and monitors for unsigned driver loads. This must be forcefully "
            "stopped and disabled via Service Control Manager prior to applying environment "
            "changes."
        ),
    ),
    Feature(
        id=10,
        name="Windows Hello Protection",
        target="Removed",
        scope="Registry/TPM",
        status="Active",
        locked=False,
        desc=(
            "TPM and VBS-backed biometrics. It stores cryptographic keys inside the VBS secure "
            "enclave. Removing VBS completely breaks this trust chain, requiring the user to "
            "reset their PIN or Biometric fingerprints upon the next boot using a standard "
            "password."
        ),
    ),
    Feature(
        id=11,
        name="Secure Biometrics",
        target="Disabled",
        scope="Registry",
        status="Active",
        locked=False,
        desc=(
            "Enforces encrypted USB/SPI channels for fingerprint and IR camera sensors. "
            "Disabling this removes the enhanced sign-in security features that rely on the "
            "virtualization boundary."
        ),
    ),
    Feature(
        id=12,
        name="HyperGuard / Sys Guard",
        target="Disabled",
        scope="Registry",
        status="Active",
        locked=False,
        desc=(
            "System Management Mode (SMM) protections and Boot isolation. Protects against "
            "firmware-level rootkits but actively locks specific CPU control registers (like "
            "CR4/CR0) which prevents dynamic environment alteration."
        ),
    ),
    Feature(
        id=13,
        name="Smart App Control",
        target="Monitor",
        scope="Registry",
        status="Monitoring",
        locked=True,
        desc=(
            "An AI-driven application whitelisting feature in Windows 11 that blocks "
            "unrecognized executables from interacting with critical system APIs. HyperGuard92 "
            "monitors this to ensure its registry modifications are not silently intercepted."
        ),
    ),
    Feature(
        id=14,
        name="BitLocker",
        target="Suspended",
        scope="System",
        status="Active",
        locked=False,
        desc=(
            "Full Volume Encryption (FVE). BitLocker validates the boot chain using TPM PCR "
            "registers. Modifying the BCD (e.g., turning off the hypervisor) will alter the "
            "boot chain and trip BitLocker recovery mode. Suspension temporarily bypasses "
            "this check for one boot cycle."
        ),
    ),
]


def clone_features() -> list[Feature]:
    """Return a deep copy of the seed feature list (used to reset state)."""
    return deepcopy(INITIAL_FEATURES)
