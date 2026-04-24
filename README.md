# 🎨 HyperGuard92

## 📌 Context
**HyperGuard92** is a modern desktop application (built with Python) designed to give power users, developers, and reverse engineers low-level control over Windows 11 Virtualization-Based Security (VBS) features. By default, Windows locks down many virtualization features, which can conflict with third-party hypervisors, custom drivers, and anti-cheat systems. This app provides a safe, graphical interface to manage and disable these conflicting security layers while providing robust backup and restore capabilities.

## 🎯 Core Application Goals
1. **Detect**: Automatically analyze the system environment (BIOS VT-x/SVM, OS Build, WMI health) and current security feature states.
2. **Control**: Safely disable tightly integrated Windows security features (VBS, HVCI, Credential Guard, Meltdown mitigations, Windows Hyper-V).
3. **Manage State**: Keep track of every modification made to the system registry, Boot Configuration Data (BCD), and services to allow for precise "Revert Changes" operations.
4. **Graphical Interface**: Utilize **NiceGUI** to provide a seamless, browser-based graphical user interface that feels native and responsive.

## 🖥️ Key UI Screens & Components Needed

### 1. 📊 The Dashboard (System Health & Environment)
- **Top-Level Status**: A clear banner indicating if the system is currently "Standard/Secure" or "Modified/Optimized for Third-Party Hypervisors".
- **Hardware & Env Checks**: Visual indicators (icons: ✅ / ❌ / ⚠️) for prerequisites: 
  - Admin Privileges
  - BIOS Virtualization (VT-x/SVM)
  - WMI Health status
- **Action Dashboard**: Prominent "Optimize System" (disable conflicting features) and "Revert Changes" (restore from backup) buttons.

### 2. 🛡️ The Feature Matrix (Toggles & Status)
A detailed list or grid displaying the 14 core features managed by the app. Each row/card should include:
- **Feature Name** (e.g., Memory Integrity (HVCI), Credential Guard, Windows Hello Protection).
- **Current Status Pill**: e.g., `Active`, `Disabled`, or `Locked by UEFI`.
- **Toggle/Action Button**: Individual controls to manage the feature.
- **Tooltip/Info Icon**: Hovering over a feature should briefly explain what it does (e.g., "HVCI: Prevents unsigned drivers from loading").

#### 📋 Managed Features List
The application interacts with the following system components:

| # | Feature | Targeted Value | Scope | Description |
| :--- | :--- | :--- | :--- | :--- |
| **01** | **Virtualization (VT-x/SVM)** | **Enabled** | BIOS | Mandatory prerequisite. App fails if disabled in BIOS. |
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

### 3. ⚠️ Warning Modals & Action Flows
- **BitLocker Intervention**: A modal that appears to warn users that BitLocker will be temporarily suspended to change boot parameters.
- **Windows Hello Reset**: A critical dialog warning that biometric fingerprints and PINs will be reset if VBS is disabled, requiring the user to type their fallback password next login.
- **Smart App Control Notification**: A dismissible banner if Smart App Control is attempting to block the application. 

### 4. ⏳ Progress & Execution State
- **Console / Status Log**: A bottom pane or sidebar that shows terminal-like output as the app modifies registries (`winreg`) and BCD environments in the background.
- **Progress Bars**: Smooth loading states for when the app is performing sequential automated tasks.

## 🎨 Design System & Aesthetic Preferences
- **Style**: Modern Windows 11 (Mica/Fluent design) infused with a "power-user / developer" visual language. 
- **Theme**: **Mandatory Dark Mode**. The application must launch in and exclusively use a dark theme to align with its power-user utility profile.
- **Color Palette Ideas**: 
  - Deep dark backgrounds (slate/charcoal).
  - Status colors: Cyber-blue (info), Success Green (enabled/safe), Warning Amber (modifications needed), Alert Red (critical locks/BitLocker).
- **Typography**: Clean sans-serif (Inter, Segoe UI) with monospace fonts (Consolas/Fira Code) for the terminal/log areas.