# 🛡️ Analysis of VBS_1.6.2.cmd (HyperGuard92 Implementation Guide)

This document provides a detailed breakdown of the features and logic implemented in `VBS_1.6.2.cmd`. This analysis serves as the architectural foundation for the **HyperGuard92** Python application.

---

## 🏗️ Core Architecture Overview

The script follows a structured workflow:
1.  **Environment Check**: Admin privileges, PowerShell functionality, WMI health, and Desktop detection.
2.  **Diagnostic Tests**: BIOS Virtualization, OS Build, and currently active security features.
3.  **State Management**: It uses `HKLM\SOFTWARE\ManageVBS` to track which features were modified, allowing for a precise "Revert Changes" operation.
4.  **Implementation**: Aggressively disables features that conflict with third-party hypervisors or syscall hooking.

---

## 📋 Feature Matrix (Enabled/Disabled/Used)

The script interacts with the following system components:

| # | Feature | Targeted Value | Scope | Description |
| :--- | :--- | :--- | :--- | :--- |
| **01** | **Virtualization (VT-x/SVM)** | **Enabled** | BIOS | Mandatory prerequisite. Script fails if disabled in BIOS. |
| **02** | **WMI (WinMgmt)** | **Functional** | System | Used for queries. Includes a "Troubleshoot" fix if broken. |
| **03** | **VBS (Virtualization-Based Security)** | **Disabled** | Registry/UEFI | The primary target. Disables the core security engine. |
| **04** | **HVCI (Memory Integrity)** | **Disabled** | Registry/UEFI | Disables kernel-mode code integrity checks. |
| **05** | **Credential Guard** | **Disabled** | Registry/UEFI | Disables LSA isolation. |
| **06** | **DSE (Driver Signature Enforcement)** | **Disabled** | Boot | Disabled via "Startup Settings" (F7) for one boot cycle. |
| **07** | **KVA Shadow (Meltdown Fix)** | **Disabled** | Registry | Disables syscall isolation (often required for hooks). |
| **08** | **Windows Hypervisor** | **Disabled** | BCD | Switches `hypervisorlaunchtype` to `off`. |
| **09** | **FACEIT Anti-Cheat** | **Disabled** | Service | Stops and disables services that block unsigned drivers. |
| **10** | **Windows Hello Protection** | **Removed** | Registry/TPM | Removes VBS-based isolation for PIN/Biometrics. |
| **11** | **Secure Biometrics** | **Disabled** | Registry | Disables enhanced sign-in security features. |
| **12** | **HyperGuard / System Guard** | **Disabled** | Registry | Disables SMM and boot integrity protections. |
| **13** | **Smart App Control** | **Monitor** | Registry | Notifies user if SAC might block the tool. |
| **14** | **BitLocker** | **Suspended** | System | Momentarily suspended to allow advanced boot options. |

---

## 🔍 Feature Breakdown & Detection Logic

### 1. BIOS Virtualization
*   **Detailed Explanation**: Hardware-assisted virtualization (Intel VT-x or AMD-V) is the foundation for all VBS features. It allows a single CPU to act as multiple virtual CPUs. When VBS is enabled, Windows uses this hardware as a "Level 0" hypervisor (Hyper-V) to create a secure memory enclave.
*   **Detection**: Uses CIM Instance via PowerShell.
    *   ` (Get-CimInstance Win32_ComputerSystem).HypervisorPresent`
    *   `(Get-CimInstance -ClassName Win32_Processor).VirtualizationFirmwareEnabled`

### 2. WMI (Windows Management Instrumentation)
*   **Detailed Explanation**: WMI is the infrastructure for management data and operations on Windows-based operating systems. The script relies on it for querying system states (like `Win32_DeviceGuard`). If WMI is corrupted, the script cannot reliably detect feature states.
*   **Detection**: Attempts a standard query: `wmic path Win32_ComputerSystem get CreationClassName`.
*   **Check**: If the query fails or returns nothing, `wmifailed=1` is set.

### 3. VBS (Virtualization-Based Security)
*   **Detailed Explanation**: VBS uses hardware virtualization to create and isolate a secure region of memory from the normal operating system. This secure enclave is used to host various security solutions (HVCI, Credential Guard, etc.), protecting them from kernel-level vulnerabilities.
*   **Detection**: 
    1.  **Active State**: `Win32_DeviceGuard` WMI class.
    2.  **Configuration**: Registry key `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard \ EnableVirtualizationBasedSecurity`.
*   **Disabling Action**: Sets registry `EnableVirtualizationBasedSecurity` to `0`. If locked by UEFI, it uses `SecConfig.efi` via a one-time boot sequence.

### 4. Memory Integrity (HVCI)
*   **Detailed Explanation**: Hypervisor-Protected Code Integrity (HVCI) ensures that only valid, signed code can be loaded into the kernel. It uses VBS to run kernel mode code integrity (KMCI) inside the secure environment, preventing drivers without valid signatures from executing.
*   **Detection**:
    1.  **Active State**: `Win32_DeviceGuard \ SecurityServicesRunning` (Code `2` indicates HVCI is active).
    2.  **Configuration**: `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity \ Enabled`.
*   **Disabling Action**: Sets `Enabled` to `0`.

### 5. Credential Guard
*   **Detailed Explanation**: Credential Guard uses VBS to isolate secrets (like NTLM hashes or Kerberos tickets) so that only privileged system software can access them. This prevents "Pass-the-Hash" or "Pass-the-Ticket" attacks even if the kernel is compromised.
*   **Detection**:
    1.  `HKLM\SYSTEM\CurrentControlSet\Control\Lsa \ LsaCfgFlags`.
    2.  `HKLM\SOFTWARE\Policies\Microsoft\Windows\DeviceGuard \ LsaCfgFlags`.
    3.  `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\CredentialGuard \ Enabled`.
*   **Disabling Action**: Deletes or zeroes out `LsaCfgFlags` and adds `Enabled=0` to the CredentialGuard scenario path.

### 6. DSE (Driver Signature Enforcement)
*   **Detailed Explanation**: DSE is a security policy that prevents unsigned drivers from loading into the Windows kernel. For research, debugging, or custom hypervisors, it often needs to be disabled to load "experimental" drivers.
*   **Detection**: Custom DLL call to `ntdll.dll!NtQuerySystemInformation`.
    *   **Logic**: Calls `NtQuerySystemInformation` with info class `103` (`SystemCodeIntegrityInformation`).
    *   **State Interpretation**:
        *   `0`: **Disabled** (The bitmask check `-not($o -band 1)` returns true).
        *   `1`: **Test Signing Enabled** (`$o -band 2`).
        *   `2`: **Enabled** (Default fallback).
*   **Disabling Action**: Since DSE cannot be persistently disabled in modern Windows without Test Signing, the script sets `bcdedit /set {default} onetimeadvancedoptions on` to force the user into the "Startup Settings" (F7) menu upon reboot.

### 7. KVA Shadow (Meltdown Mitigation)
*   **Detailed Explanation**: Kernel Virtual Address (KVA) Shadowing mitigates the Meltdown vulnerability by ensuring the kernel's memory map is not visible to user processes. This isolation deeply interferes with "detours" or "hooks" that modify kernel syscall tables.
*   **Detection**: Custom DLL call `ntdll.dll!NtQuerySystemInformation` with info class `196` (`SystemSpeculationControlInformation`). 
    *   **Logic**: Reads a 4-byte bitmask. Mitigation is considered "Required/Active" if:
        *   `KvaShadowEnabled` (`0x01`) is set OR
        *   `BpbEnabled` (`0x20`) AND `BpbTargets` (`0x10`) are BOTH set.
*   **Disabling Action**: 
    *   `FeatureSettingsOverride` -> `2`
    *   `FeatureSettingsOverrideMask` -> `3`
    *   (Registry: `HKLM\System\CurrentControlSet\Control\Session Manager\Memory Management`)

### 8. Windows Hypervisor (Hyper-V)
*   **Detailed Explanation**: The base hypervisor layer used by Windows features like WSL2, Sandbox, and Docker. If active, it takes control of VT-X/SVM, preventing third-party hypervisors from using these "root" hardware features.
*   **Detection**:
    1.  **Feature State (DISM)**: Iterates through `Microsoft-Windows-Subsystem-Linux`, `Containers-DisposableClientVM`, `Microsoft-Hyper-V-All`, `VirtualMachinePlatform`, and `HypervisorPlatform`. If any are "Enabled", the hypervisor is considered found.
    2.  **VBS Status**: Checks `VirtualizationBasedSecurityStatus` via WMI (`root\Microsoft\Windows\DeviceGuard`). Values `1` (Enabled but not running) or `2` (Running) trigger the need to disable.
    3.  **Active Hypervisor**: Queries WMI `Win32_ComputerSystem` for `HypervisorPresent == True`.
    4.  **BCD Check**: Checks `bcdedit /enum` for `hypervisorlaunchtype`. If set to `Auto` or `On`, it is targeted for disabling.
*   **Disabling Action**: `bcdedit /set hypervisorlaunchtype off`.

### 9. FACEIT Anti-Cheat
*   **Detailed Explanation**: A kernel-level anti-cheat driver that acts as an extremely restrictive firewall for drivers. It prevents the loading of any driver it hasn't explicitly approved, which often includes diagnostic or research drivers.
*   **Detection**: `fltmc` (Filter Manager Control) is checked for the string "FACEIT".
*   **Disabling Action**: Stops the `FACEIT` and `FACEITService` services and sets their start type to `Disabled`.

### 10. Windows Hello Protection
*   **Detailed Explanation**: Windows Hello uses VBS to protect biometric data (fingerprints, face) and PINs inside the secure enclave. If you disable VBS while this is active, the system may lose access to the keys, causing login failures.
*   **Detection**: Registry query at `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\WindowsHello \ Enabled`.
*   **Handling**: Uses `certutil -DeleteHelloContainer` to remove the protected PIN/Biometric container before disabling VBS, forcing the user to use a password until it's reset.

### 11. Secure Biometrics
*   **Detailed Explanation**: Enhanced Sign-in Security (Secure Biometrics) uses VBS to protect biometric templates and the communication channel between the sensor and the OS.
*   **Detection**: Checks multiple registry variations:
    1.  `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\SecureBiometrics \ Enabled`.
    2.  `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios \ SecureBiometrics`.
    3.  `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\WindowsHelloSecureBiometrics \ Enabled`.
*   **Disabling Action**: Sets the found registry values to `0`.

### 12. HyperGuard & System Guard
*   **Detailed Explanation**: HyperGuard (kernel protection) and System Guard (boot integrity) use VBS and SMM (System Management Mode) to ensure the system hasn't been tampered with since boot.
*   **Detection**: 
    1.  **HyperGuard**: `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HyperGuard \ Enabled`.
    2.  **System Guard**: `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\SystemGuard \ Enabled`.
    3.  **Guarded Host**: `HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\Host-Guardian \ Enabled`.
*   **Disabling Action**: Sets the `Enabled` value of these scenarios to `0`.

### 13. Smart App Control (SAC)
*   **Detailed Explanation**: An AI-powered security layer in Windows 11 that blocks apps that are malicious or untrusted.
*   **Detection**: Registry query at `HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy \ VerifiedAndReputablePolicyState`.
*   **Status Indicators**: 
    *   `0x1`: **Enabled**.
    *   `0x2`: **Evaluation Mode**.
*   **Action**: Notification only.

### 14. BitLocker Management
*   **Detailed Explanation**: Windows full-disk encryption. Suspension is required to change boot parameters without triggering recovery mode.
*   **Detection**: `(Get-BitLockerVolume -MountPoint $env:SystemDrive).ProtectionStatus`.
*   **Handling**: Temporarily suspends protectors using `manage-bde -protectors -disable C: -rebootcount 1`.

---

## 🛠️ Implementation Strategy for HyperGuard92

| Phase | Technology | Notes |
| :--- | :--- | :--- |
| **Detection** | `pywin32` / `WMI` | Use native Python WMI wrappers to query `Win32_DeviceGuard` and `Win32_Processor`. |
| **Registry Ops** | `winreg` | Atomic updates to the registry. Always backup keys to `HKLM\SOFTWARE\HyperGuard92\Backups` |
| **EFI/BCD** | `subprocess` | Direct execution of `bcdedit` and `mountvol`. Requires careful handling of GUIDs. |
| **UI Validation** | `Playwright` | Ensure the state toggles and progress bars correctly reflect the background registry/BCD tasks. |
| **Safety** | Pydantic Models | Define strict schemas for "Safe States" to prevent accidental bricking or security policy violations on managed devices. |

---

> **Note**: The script explicitly mentions that some features (like VBS or HVCI) might be **Locked by UEFI**. In such cases, it leverages `SecConfig.efi`, a Microsoft tool designed to clear these settings. Our application must implement a "UEFI Opt-out" workflow if these locks are detected.
