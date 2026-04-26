"""Feature domain model and the canonical seed list managed by HyperGuard92.

Each feature is tracked with three distinct states:

* ``pirate_state``   — the state PIRATE MODE (``VBS_1.6.2.cmd``) drives the
  feature towards in order to allow bypass / hooking software to run.
* ``defender_state`` — the state preferred by Windows Defender for maximum
  security and isolation.
* ``status``         — the live observed state on the running system.
"""

from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field


class Feature(BaseModel):
    """A single Windows security feature tracked by the application."""

    id: int = Field(..., description="Stable identifier (1-based index).")
    name: str = Field(..., description="Human-readable feature name.")
    pirate_state: str = Field(
        ...,
        description="State PIRATE MODE drives the feature towards (bypass-friendly).",
    )
    defender_state: str = Field(
        ...,
        description="State Windows Defender prefers for maximum security.",
    )
    scope: str = Field(..., description="Where the feature lives (BIOS, Registry, BCD...).")
    status: str = Field(..., description="Current observed runtime state.")
    locked: bool = Field(..., description="True if the feature cannot be toggled by the user.")
    desc: str = Field(..., description="Detailed technical explanation shown in tooltips.")

    @property
    def target(self) -> str:
        """Backward-compatible alias for :attr:`pirate_state`."""
        return self.pirate_state


class FeatureDetail(BaseModel):
    """Technical documentation shown in the feature detail modal."""

    model_config = ConfigDict(frozen=True)

    explanation: tuple[str, ...] = Field(
        ..., description="How the feature works and what it protects."
    )
    verification: tuple[str, ...] = Field(
        ..., description="Ways to verify the feature state outside HyperGuard92."
    )
    enablement: tuple[str, ...] = Field(
        ..., description="Manual steps to enable or restore the feature."
    )
    disablement: tuple[str, ...] = Field(
        ..., description="Manual steps to disable, suspend, or remove the feature."
    )


INITIAL_FEATURES: list[Feature] = [
    Feature(
        id=1,
        name="Virtualization (VT-x/SVM)",
        pirate_state="Enabled",
        defender_state="Enabled",
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
        pirate_state="Functional",
        defender_state="Functional",
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
        pirate_state="Disabled",
        defender_state="Active",
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
        pirate_state="Disabled",
        defender_state="Active",
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
        pirate_state="Disabled",
        defender_state="Running",
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
        pirate_state="Disabled",
        defender_state="Enabled",
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
        pirate_state="Disabled",
        defender_state="Active",
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
        pirate_state="Disabled",
        defender_state="Active",
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
        pirate_state="Disabled",
        defender_state="N/A",
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
        pirate_state="Removed",
        defender_state="Active",
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
        pirate_state="Disabled",
        defender_state="Active",
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
        pirate_state="Disabled",
        defender_state="Active",
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
        pirate_state="Monitor",
        defender_state="On",
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
        pirate_state="Suspended",
        defender_state="Active",
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


FEATURE_DETAILS: dict[int, FeatureDetail] = {
    1: FeatureDetail(
        explanation=(
            "CPU virtualization exposes Intel VT-x or AMD SVM, plus SLAT support "
            "(EPT/NPT), so Windows can run a hypervisor below the normal kernel.",
            "It does not block threats by itself; it enables VBS, Hyper-V, HVCI, "
            "and other isolation features that keep protected memory outside the "
            "reach of normal kernel code.",
        ),
        verification=(
            "Task Manager: Performance > CPU should show `Virtualization: Enabled`.",
            "PowerShell: `Get-CimInstance Win32_Processor | Select-Object "
            "Manufacturer,VirtualizationFirmwareEnabled,"
            "SecondLevelAddressTranslationExtensions`.",
            "Firmware setup: confirm Intel Virtualization Technology, VT-x, AMD-V, "
            "or SVM Mode is enabled.",
        ),
        enablement=(
            "Reboot into BIOS/UEFI setup and enable Intel VT-x / AMD SVM and IOMMU "
            "options when available.",
            "Save firmware changes, fully power-cycle the computer, then refresh the "
            "HyperGuard92 feature matrix.",
        ),
        disablement=(
            "Reboot into BIOS/UEFI setup and disable Intel VT-x / AMD SVM if you need "
            "to prevent hypervisor-based features from starting.",
            "Expect VBS, Hyper-V, WSL2, Android subsystem, sandboxing, and some security "
            "features to stop working after the next boot.",
        ),
    ),
    2: FeatureDetail(
        explanation=(
            "Windows Management Instrumentation (WinMgmt) is the local management "
            "repository and query service used by CIM, Device Guard reporting, and "
            "many administrative tools.",
            "It prevents blind state changes by giving HyperGuard92 a reliable source "
            "for processor, operating-system, Device Guard, and service telemetry.",
        ),
        verification=(
            "Services app: verify `Windows Management Instrumentation` is running.",
            "PowerShell: `Get-Service Winmgmt` and `(Get-CimInstance "
            "Win32_OperatingSystem).Caption` should both return successfully.",
            "Command Prompt: `winmgmt /verifyrepository` should report a consistent "
            "repository.",
        ),
        enablement=(
            "Services app: set Windows Management Instrumentation to Automatic and "
            "start the service.",
            "PowerShell as administrator: `Set-Service Winmgmt -StartupType Automatic` "
            "then `Start-Service Winmgmt`.",
            "If the repository is inconsistent, run `winmgmt /salvagerepository` and "
            "refresh the matrix.",
        ),
        disablement=(
            "Temporary stop: `Stop-Service Winmgmt` from an elevated PowerShell session.",
            "Permanent disablement is not recommended because Windows diagnostics, "
            "security reporting, and management tooling depend on WMI.",
        ),
    ),
    3: FeatureDetail(
        explanation=(
            "Virtualization-Based Security starts the Windows hypervisor and creates "
            "an isolated secure kernel alongside the normal Windows kernel.",
            "It prevents normal-world kernel code from reading or modifying protected "
            "secrets and policy state because the hypervisor enforces the memory "
            "boundary.",
        ),
        verification=(
            "System Information (`msinfo32`): check `Virtualization-based security` "
            "and the required, available, configured, and running security properties.",
            "PowerShell: `Get-CimInstance -Namespace root\\Microsoft\\Windows\\DeviceGuard "
            "-ClassName Win32_DeviceGuard`.",
            r"Registry: `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard` value "
            "`EnableVirtualizationBasedSecurity`.",
        ),
        enablement=(
            "Windows Security: Device security > Core isolation, then enable supported "
            "isolation features.",
            r"Registry: set `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard` "
            "`EnableVirtualizationBasedSecurity` to `1` and reboot.",
            "Ensure Secure Boot, TPM, CPU virtualization, and `bcdedit /set "
            "hypervisorlaunchtype auto` are in place.",
        ),
        disablement=(
            r"Registry: set `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard` "
            "`EnableVirtualizationBasedSecurity` to `0` and reboot.",
            "BCD: `bcdedit /set hypervisorlaunchtype off` prevents the Windows "
            "hypervisor from loading on the next boot.",
        ),
    ),
    4: FeatureDetail(
        explanation=(
            "Hypervisor-Enforced Code Integrity (Memory Integrity) runs kernel code "
            "integrity decisions inside the VBS trust boundary.",
            "It prevents unsigned, tampered, or dynamically generated kernel pages from "
            "executing by enforcing W^X memory and driver-signing rules through the "
            "hypervisor.",
        ),
        verification=(
            "Windows Security: Device security > Core isolation > Memory integrity.",
            "PowerShell: Device Guard `SecurityServicesRunning` contains service code "
            "`2` when HVCI is running.",
            "Registry: `HKLM\\SYSTEM\\CurrentControlSet\\Control\\DeviceGuard\\Scenarios\\"
            "HypervisorEnforcedCodeIntegrity` value `Enabled`.",
        ),
        enablement=(
            "Enable Memory Integrity in Windows Security, resolve incompatible driver "
            "warnings, then reboot.",
            r"Registry: set `...\HypervisorEnforcedCodeIntegrity` `Enabled` to `1` "
            "and keep VBS plus the Windows hypervisor enabled.",
        ),
        disablement=(
            "Turn Memory Integrity off in Windows Security and reboot.",
            r"Registry: set `...\HypervisorEnforcedCodeIntegrity` `Enabled` to `0`; "
            "this weakens kernel driver enforcement until re-enabled.",
        ),
    ),
    5: FeatureDetail(
        explanation=(
            "Credential Guard moves LSA secrets, NTLM hashes, and Kerberos material "
            "into a VBS-isolated process instead of leaving them readable by the normal "
            "kernel.",
            "It prevents common credential-theft paths, including pass-the-hash staging, "
            "because even high-privilege normal-world code cannot directly read the "
            "isolated LSA secrets.",
        ),
        verification=(
            "System Information: review `Virtualization-based security Services "
            "Configured` and `Services Running` for Credential Guard.",
            "PowerShell: Device Guard `SecurityServicesConfigured` or "
            "`SecurityServicesRunning` contains service code `1`.",
            r"Registry: `HKLM\SYSTEM\CurrentControlSet\Control\Lsa` value "
            "`LsaCfgFlags` and related Device Guard policy values.",
        ),
        enablement=(
            "Group Policy: Computer Configuration > Administrative Templates > System "
            "> Device Guard > Turn On Virtualization Based Security, then choose "
            "Credential Guard.",
            r"Registry: set `HKLM\SYSTEM\CurrentControlSet\Control\Lsa` "
            "`LsaCfgFlags` to `1` or policy-managed `2`, then reboot with VBS enabled.",
        ),
        disablement=(
            r"Registry and policy: set `LsaCfgFlags` values to `0` under both `Control\Lsa` "
            "and Device Guard policy locations, then reboot.",
            "If Credential Guard was deployed with UEFI lock, remove the lock using "
            "Microsoft's documented Device Guard and Credential Guard readiness tooling.",
        ),
    ),
    6: FeatureDetail(
        explanation=(
            "Driver Signature Enforcement is Windows Code Integrity policy for "
            "kernel-mode drivers.",
            "It prevents unsigned or test-signed kernel drivers from loading by checking "
            "driver signatures during the boot and driver-load paths.",
        ),
        verification=(
            "Command Prompt as administrator: run `bcdedit /enum {current}` and review "
            "`testsigning` plus `nointegritychecks`.",
            "DSE is enforced when neither flag is present, or both are explicitly `No`.",
            "Optional inventory: `driverquery /si` lists loaded signed drivers.",
        ),
        enablement=(
            "Command Prompt as administrator: `bcdedit /set testsigning off` and "
            "`bcdedit /set nointegritychecks off`, then reboot.",
            "Keep Secure Boot enabled where possible so boot policy and code integrity "
            "cannot be trivially weakened.",
        ),
        disablement=(
            "Command Prompt as administrator: `bcdedit /set testsigning on` enables "
            "test mode after reboot.",
            "`bcdedit /set nointegritychecks on` disables integrity checks more broadly; "
            "use only on controlled test systems.",
        ),
    ),
    7: FeatureDetail(
        explanation=(
            "KVA Shadow separates user-mode and kernel-mode page tables to mitigate "
            "Meltdown-class speculative execution attacks.",
            "It prevents user-mode code from speculatively observing privileged kernel "
            "memory. AMD processors generally do not require this mitigation, so a "
            "disabled state can be healthy on AMD hardware.",
        ),
        verification=(
            "PowerShell: install or import `SpeculationControl`, then run "
            "`Get-SpeculationControlSettings`.",
            "Review `KVAShadowRequired` and `KVAShadowWindowsSupportEnabled` together; "
            "required=false means the CPU is not affected by Meltdown.",
            r"Registry override path: `HKLM\SYSTEM\CurrentControlSet\Control\Session "
            "Manager\\Memory Management`.",
        ),
        enablement=(
            "For vulnerable Intel systems, remove KVA override values or set "
            "`FeatureSettingsOverride` to `0`, then reboot.",
            "Keep Windows fully patched so the kernel and microcode mitigation state "
            "match Microsoft's current guidance.",
        ),
        disablement=(
            r"Registry: set `FeatureSettingsOverride` to `2` and "
            "`FeatureSettingsOverrideMask` to `3` under the Memory Management key, "
            "then reboot.",
            "On AMD systems, no manual disablement is normally needed because KVA Shadow "
            "is not required for Meltdown protection.",
        ),
    ),
    8: FeatureDetail(
        explanation=(
            "The Windows hypervisor is loaded by the boot manager before the Windows "
            "kernel and provides the Ring -1 execution layer used by Hyper-V and VBS.",
            "It prevents isolation boundaries from being bypassed by placing VBS and "
            "HVCI enforcement below the normal kernel when enabled.",
        ),
        verification=(
            "PowerShell: `(Get-CimInstance Win32_ComputerSystem).HypervisorPresent` "
            "returns `True` when a hypervisor is running.",
            "Command Prompt: `bcdedit /enum {current}` shows the configured "
            "`hypervisorlaunchtype` value.",
            "System Information may show `A hypervisor has been detected` when it is "
            "active.",
        ),
        enablement=(
            "Command Prompt as administrator: `bcdedit /set hypervisorlaunchtype auto`, "
            "then reboot.",
            "Enable dependent Windows features such as Hyper-V, Virtual Machine Platform, "
            "or Windows Hypervisor Platform only when needed.",
        ),
        disablement=(
            "Command Prompt as administrator: `bcdedit /set hypervisorlaunchtype off`, "
            "then reboot.",
            "Disabling the hypervisor also prevents VBS, HVCI, WSL2, Hyper-V, and other "
            "hypervisor-backed components from running.",
        ),
    ),
    9: FeatureDetail(
        explanation=(
            "FACEIT Anti-Cheat is an application-specific kernel service and filter "
            "driver installed by the FACEIT client.",
            "HyperGuard92 treats it as optional: the toggle is hidden when the service "
            "is not installed, and service changes should only be made on machines you "
            "administer and when not using FACEIT-protected games.",
        ),
        verification=(
            "Services app: look for `FACEIT` or `FACEITService`.",
            "Command Prompt: `sc query FACEIT` and `sc query FACEITService` show SCM "
            "service state when installed.",
            "Command Prompt: `fltmc` can show whether a FACEIT file-system filter is "
            "currently loaded.",
        ),
        enablement=(
            "Install or repair the official FACEIT client if the service is missing.",
            "Command Prompt as administrator: `sc start FACEIT` or `sc start "
            "FACEITService` when the service is installed.",
        ),
        disablement=(
            "Command Prompt as administrator: `sc stop FACEIT` or `sc stop "
            "FACEITService` when no protected session is active.",
            "To keep it off between boots, use Services app startup settings or "
            "`sc config FACEIT start= disabled`; restore the original startup mode "
            "before launching software that requires it.",
        ),
    ),
    10: FeatureDetail(
        explanation=(
            "Windows Hello Protection combines TPM-backed keys, the Windows Hello key "
            "container, and VBS state to protect PIN and biometric credentials.",
            "It prevents credential replay and key extraction by keeping authentication "
            "material bound to the TPM and, when active, the VBS trust boundary.",
        ),
        verification=(
            "Settings: Accounts > Sign-in options should show configured PIN, face, or "
            "fingerprint methods.",
            "Command Prompt: `dsregcmd /status` and review `NgcSet : YES`.",
            "Registry fallback: `HKLM\\SYSTEM\\CurrentControlSet\\Control\\DeviceGuard\\"
            "Scenarios\\WindowsHello` value `Enabled`.",
        ),
        enablement=(
            "Enable VBS and TPM-backed sign-in, then configure Windows Hello from "
            "Settings > Accounts > Sign-in options.",
            "If credentials were reset after VBS changes, sign in with your password "
            "and recreate the PIN or biometric enrollment.",
        ),
        disablement=(
            "Settings: remove PIN, face, and fingerprint sign-in options before changing "
            "the VBS profile.",
            r"Registry: set `...\Scenarios\WindowsHello` `Enabled` to `0` if you are "
            "testing VBS-backed Hello behavior, then reboot.",
        ),
    ),
    11: FeatureDetail(
        explanation=(
            "Secure Biometrics, also called Enhanced Sign-in Security, protects sensor "
            "traffic and biometric processing with hardware and VBS support.",
            "It prevents spoofed or tampered biometric data from being accepted by "
            "requiring trusted sensor channels and a secure processing path.",
        ),
        verification=(
            "Settings: Accounts > Sign-in options shows whether enhanced sign-in "
            "security is available for the device.",
            "Registry: check `HKLM\\SYSTEM\\CurrentControlSet\\Control\\DeviceGuard\\"
            "Scenarios\\SecureBiometrics` value `Enabled`.",
            "PowerShell: confirm VBS is running through `Win32_DeviceGuard`; secure "
            "biometrics depends on VBS being active.",
        ),
        enablement=(
            "Enable VBS, install OEM biometric drivers, and enable Enhanced Sign-in "
            "Security when Windows exposes the setting.",
            r"Registry: set `...\Scenarios\SecureBiometrics` `Enabled` to `1` only on "
            "hardware that supports secure biometric channels, then reboot.",
        ),
        disablement=(
            r"Registry: set `...\Scenarios\SecureBiometrics` `Enabled` to `0` and "
            "reboot.",
            "You may need to re-enroll Windows Hello biometrics after disabling or "
            "re-enabling this scenario.",
        ),
    ),
    12: FeatureDetail(
        explanation=(
            "HyperGuard / System Guard covers Secure Launch, SMM measurement, and "
            "firmware-related Device Guard scenarios that harden the boot chain.",
            "It prevents firmware and early-boot tampering from silently changing the "
            "trust boundary by measuring launch state and reporting it to Windows.",
        ),
        verification=(
            "System Information: review VBS services configured/running for Secure "
            "Launch or related System Guard entries.",
            "PowerShell: Device Guard `SecurityServicesRunning` may contain service "
            "codes `3`, `4`, or `7` when these protections are active.",
            r"Registry scenarios: `HyperGuard`, `SystemGuard`, and `Host-Guardian` "
            "under the Device Guard scenarios key.",
        ),
        enablement=(
            "Enable Secure Boot, TPM, IOMMU/DMA protections, and firmware Secure Launch "
            "support where available.",
            r"Registry: set supported Device Guard scenario `Enabled` values to `1`, "
            "then reboot and confirm through `msinfo32`.",
        ),
        disablement=(
            r"Registry: set `HyperGuard`, `SystemGuard`, and `Host-Guardian` scenario "
            "`Enabled` values to `0`, then reboot.",
            "Firmware or policy-managed deployments may re-enable these protections at "
            "the next policy refresh.",
        ),
    ),
    13: FeatureDetail(
        explanation=(
            "Smart App Control is Windows 11 reputation-based application control for "
            "untrusted scripts, installers, and executables.",
            "It prevents unknown or low-reputation code from launching by combining "
            "Microsoft cloud reputation with local code integrity policy.",
        ),
        verification=(
            "Windows Security: App & browser control > Smart App Control shows Off, "
            "Evaluation, or On.",
            r"Registry: `HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy` value "
            "`VerifiedAndReputablePolicyState` maps to Off, On, or Monitoring.",
        ),
        enablement=(
            "Use Windows Security to turn Smart App Control on when Windows allows it.",
            "If Smart App Control has been turned off, Windows may require a reset or "
            "clean installation before it can enter evaluation or on mode again.",
        ),
        disablement=(
            "Windows Security: App & browser control > Smart App Control > Off.",
            "Turning it off is usually one-way for the current Windows installation, so "
            "confirm the change before applying it.",
        ),
    ),
    14: FeatureDetail(
        explanation=(
            "BitLocker encrypts volumes and seals boot trust to TPM Platform "
            "Configuration Registers.",
            "It prevents offline data access and alerts on boot-chain changes because "
            "unexpected BCD or firmware changes alter the TPM measurements used to "
            "release the volume key.",
        ),
        verification=(
            "Control Panel or Settings: open BitLocker Drive Encryption for the system "
            "drive.",
            "Command Prompt: `manage-bde -status C:` and review conversion plus "
            "protection status.",
            "PowerShell: `Get-BitLockerVolume -MountPoint C:` shows protection state "
            "and suspension count.",
        ),
        enablement=(
            "Settings or Control Panel: turn on BitLocker for the operating-system "
            "drive and save the recovery key in a secure location.",
            "PowerShell as administrator: `Enable-BitLocker -MountPoint C: "
            "-TpmProtector` when TPM requirements are satisfied.",
            "If protection was only suspended, use `Resume-BitLocker -MountPoint C:`.",
        ),
        disablement=(
            "Temporary: `Suspend-BitLocker -MountPoint C: -RebootCount 1` before BCD or "
            "boot-policy changes.",
            "Permanent decrypt: `Disable-BitLocker -MountPoint C:` or use the BitLocker "
            "control panel. Decryption can take a long time.",
        ),
    ),
}


def get_feature_detail(feature: Feature) -> FeatureDetail:
    """Return modal documentation for ``feature``."""
    detail = FEATURE_DETAILS.get(feature.id)
    if detail is not None:
        return detail
    return FeatureDetail(
        explanation=(feature.desc,),
        verification=(
            "Review the current state in HyperGuard92 and cross-check it with the "
            "corresponding Windows control surface.",
        ),
        enablement=(
            f"Restore {feature.name} to the Defender state: `{feature.defender_state}`.",
        ),
        disablement=(
            f"Move {feature.name} to the Pirate state: `{feature.pirate_state}`.",
        ),
    )


def clone_features() -> list[Feature]:
    """Return a deep copy of the seed feature list (used to reset state)."""
    return deepcopy(INITIAL_FEATURES)
