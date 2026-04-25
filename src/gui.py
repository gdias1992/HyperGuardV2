"""HyperGuard92 NiceGUI interface.

The sidebar hosts diagnostics and the PIRATE / DEFENDER mode buttons. The main
pane switches between the Feature Matrix and the Execution Terminal.

All destructive work is delegated to :class:`~src.services.vbs_service.VbsService`;
this module is responsible for composition and event streaming only.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Literal

from nicegui import ui

from src.models import INITIAL_FEATURES, Feature, clone_features
from src.models.state import OperationResult, OperationStatus
from src.services.preflight import PreflightReport
from src.services.system_info import FeatureSnapshot, SystemInfo
from src.services.vbs_service import ProgressEvent, VbsService
from src.utils.logging import get_logger

_logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants — design tokens borrowed from the React mock
# ---------------------------------------------------------------------------

VERSION = "v1.4.2"

OPTIMIZATION_STEPS: list[tuple[str, int]] = [
    ("Suspending BitLocker on C:...", 15),
    ("Disabling VBS in UEFI/Registry...", 30),
    ("Disabling Memory Integrity (HVCI)...", 45),
    ("Modifying BCD: hypervisorlaunchtype off...", 60),
    ("Stopping FACEIT services...", 75),
    ("Removing Windows Hello VBS protections...", 90),
    ("Finalizing optimization sequence...", 100),
]

SystemState = Literal["Defender Mode", "Modifying...", "Pirate Mode"]

# Inter font + custom scrollbar + tooltip wrap
EXTRA_HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  html, body, .nicegui-content { background:#000; color:#e4e4e7;
    font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
    margin:0; padding:0; }
  ::selection { background: rgba(255,255,255,.20); }
  .mono { font-family:'JetBrains Mono','Consolas','Fira Code',monospace; }
  .custom-scrollbar::-webkit-scrollbar { width:6px; height:6px; }
  .custom-scrollbar::-webkit-scrollbar-track { background:transparent; }
  .custom-scrollbar::-webkit-scrollbar-thumb { background:#272a30; border-radius:10px; }
  .custom-scrollbar::-webkit-scrollbar-thumb:hover { background:#3f444d; }
  .q-tooltip { font-size:12px !important; max-width:300px !important;
    background:#27272a !important; color:#d4d4d8 !important;
    border:1px solid rgba(255,255,255,.10) !important;
    padding:12px !important; border-radius:12px !important;
    line-height:1.5 !important; }
  /* Hide default NiceGUI page padding */
  .q-page { padding: 0 !important; }
  .nicegui-content > .q-page-container > .q-page { padding: 0 !important; }
</style>
"""


# ---------------------------------------------------------------------------
# Application state (single-process, single-user prototype)
# ---------------------------------------------------------------------------


class AppState:
    """Shared mutable state for the running session."""

    def __init__(self) -> None:
        self.active_tab: Literal["dashboard", "logs"] = "dashboard"
        self.system_state: SystemState = "Defender Mode"
        self.features: list[Feature] = clone_features()
        self.logs: list[str] = [
            f"[SYSTEM] HyperGuard92 initialized. {VERSION}",
        ]
        self.is_processing: bool = False
        self.progress: int = 0
        self.preflight: PreflightReport | None = None
        self.reboot_pending: bool = False
        self._active_task: asyncio.Task[None] | None = None

    def add_log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {msg}")

    def reset(self) -> None:
        self.features = clone_features()
        self.system_state = "Defender Mode"
        self.progress = 0
        self.add_log("[USER] Restored system to default secure state.")


state = AppState()
vbs = VbsService()
system_info = SystemInfo()


# ---------------------------------------------------------------------------
# Feature status synchronization
# ---------------------------------------------------------------------------


def _apply_snapshot(snapshots: list[FeatureSnapshot]) -> None:
    """Update :data:`state.features` in-place from a SystemInfo snapshot."""
    lookup = {s.feature_id: s for s in snapshots}
    for feature in state.features:
        snap = lookup.get(feature.id)
        if snap is not None and snap.status:
            feature.status = snap.status


async def _refresh_feature_states() -> None:
    """Poll :class:`SystemInfo` off the event loop and refresh the matrix."""
    try:
        snapshots = await asyncio.to_thread(system_info.snapshot_all)
    except Exception as exc:
        _logger.warning("Could not refresh feature snapshot: %s", exc)
        state.add_log(f"[WARN] Feature snapshot failed: {exc}")
        return
    _apply_snapshot(snapshots)
    feature_matrix.refresh()


async def _run_preflight() -> None:
    try:
        report = await asyncio.to_thread(vbs.preflight_report)
    except Exception as exc:
        _logger.warning("Preflight failed: %s", exc)
        state.add_log(f"[ERROR] Preflight failed: {exc}")
        return
    state.preflight = report
    if report.ok:
        state.add_log("[INFO] Environment pre-checks passed.")
    else:
        for warning in report.warnings:
            state.add_log(f"[WARN] {warning}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pill_classes(status: str, target: str) -> str:
    """Tailwind classes for the status pill, matching the React mock palette."""
    base = "px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider border"
    if status == target or status in {"Disabled", "Suspended", "Removed"}:
        return f"{base} bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
    if status == "Active":
        return f"{base} bg-amber-500/10 text-amber-400 border-amber-500/20"
    if status == "Monitoring":
        return f"{base} bg-white/10 text-white border-white/20"
    return f"{base} bg-zinc-800 text-zinc-400 border-zinc-700"


def _log_color(line: str) -> str:
    if "[ERROR]" in line:
        return "text-red-400"
    if "[WARN]" in line:
        return "text-amber-400"
    if "[USER]" in line:
        return "text-zinc-300"
    if "[ACTION]" in line:
        return "text-emerald-400"
    return "text-zinc-400"


def _optimizations_applied() -> int:
    return sum(1 for f in state.features if f.status == f.target and not f.locked)


# ---------------------------------------------------------------------------
# Refreshable UI fragments — re-rendered when state mutates
# ---------------------------------------------------------------------------


@ui.refreshable
def feature_matrix() -> None:
    """The 14-card Feature Matrix grid."""
    with ui.row().classes("items-center justify-between mb-6 w-full"):
        with ui.column().classes("gap-1"):
            ui.label("Feature Matrix").classes("text-xl font-bold text-white")
            ui.label(
                "Fine-tune individual security components and isolation boundaries."
            ).classes("text-sm text-zinc-400")
        ui.label(f"{_optimizations_applied()} / 11 Optimizations Applied").classes(
            "text-xs text-zinc-500 bg-zinc-900/50 px-3 py-1.5 rounded-lg "
            "border border-white/5"
        )

    with ui.element("div").classes(
        "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 w-full"
    ):
        for feature in state.features:
            _feature_card(feature)


def _feature_card(feature: Feature) -> None:
    with ui.element("div").classes(
        "flex flex-col p-5 rounded-2xl bg-zinc-900/30 border border-white/5 "
        "hover:border-white/10 hover:bg-zinc-900/60 transition-all duration-300"
    ):
        # --- Header row -----------------------------------------------------
        with ui.row().classes("justify-between items-start mb-5 w-full no-wrap"):
            with ui.column().classes("gap-2 pr-4 grow min-w-0"):
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.label(feature.name).classes(
                        "font-semibold text-zinc-200 text-sm leading-tight"
                    )
                    info_icon = ui.icon("info").classes(
                        "text-zinc-600 hover:text-white transition-colors text-sm"
                    )
                    with info_icon:
                        with ui.tooltip().classes("p-0"):
                            with ui.column().classes("gap-2 max-w-xs"):
                                ui.label(feature.name).classes(
                                    "text-white font-semibold text-sm"
                                )
                                ui.label(feature.desc).classes(
                                    "text-xs text-zinc-300 leading-relaxed"
                                )
                with ui.row().classes(
                    "items-center gap-1.5 bg-black/40 px-2 py-1 rounded-md "
                    "border border-white/5 self-start no-wrap"
                ):
                    ui.icon("settings").classes("text-zinc-500 text-xs")
                    ui.label(feature.scope.upper()).classes(
                        "text-[10px] mono text-zinc-400 tracking-wider"
                    )

            # Toggle switch — ON (right) means feature is currently active/enabled
            # in Windows; OFF (left) means it has been moved to its target state.
            switch = ui.switch(
                value=feature.status in {"Active", "Monitoring"},
                on_change=lambda _e, fid=feature.id: _toggle_feature(fid),
            ).classes("shrink-0")
            if feature.locked or state.is_processing:
                switch.disable()

        # --- Footer ---------------------------------------------------------
        with ui.row().classes(
            "mt-auto pt-4 border-t border-white/5 items-end justify-between w-full"
        ):
            with ui.column().classes("gap-1"):
                ui.label("Target State").classes(
                    "text-[9px] uppercase tracking-widest text-zinc-600 font-bold"
                )
                ui.label(feature.target).classes("text-xs font-medium text-zinc-300")
            with ui.column().classes("gap-1.5 items-end"):
                ui.label("Current").classes(
                    "text-[9px] uppercase tracking-widest text-zinc-600 font-bold"
                )
                ui.label(feature.status).classes(_pill_classes(feature.status, feature.target))


@ui.refreshable
def system_profile_panel() -> None:
    """Sidebar panel: current state + Pirate/Defender optimization buttons."""
    icon_name = {
        "Pirate Mode": "check_circle",
        "Modifying...": "autorenew",
        "Defender Mode": "shield",
    }[state.system_state]
    color = {
        "Pirate Mode": "text-emerald-400",
        "Modifying...": "text-amber-400",
        "Defender Mode": "text-zinc-400",
    }[state.system_state]
    state_label_color = (
        "text-emerald-400"
        if state.system_state == "Pirate Mode"
        else color
        if state.system_state == "Modifying..."
        else "text-zinc-300"
    )

    with ui.column().classes(
        "bg-zinc-900/80 border border-white/5 rounded-xl p-3.5 gap-3 w-full"
    ):
        ui.label("System Profile").classes(
            "text-[10px] uppercase text-zinc-500 font-semibold tracking-wider"
        )

        with ui.row().classes(
            "items-center gap-2 no-wrap pb-3 border-b border-white/5 w-full"
        ):
            spin = " animate-spin" if state.system_state == "Modifying..." else ""
            ui.icon(icon_name).classes(f"{color}{spin} text-base shrink-0")
            ui.label(state.system_state).classes(
                f"text-sm font-medium {state_label_color}"
            )

        ui.label("OPTIMIZATION ENGINE").classes(
            "text-[10px] uppercase text-zinc-500 font-semibold tracking-wider"
        )

        pirate_label = (
            "PROCESSING..."
            if state.is_processing
            else "PIRATE MODE ACTIVE"
            if state.system_state == "Pirate Mode"
            else "💀  PIRATE MODE"
        )
        pirate_btn = ui.button(
            pirate_label,
            on_click=_open_hello_modal,
        ).classes(
            "px-3 py-2 rounded-lg text-xs font-bold bg-white hover:bg-zinc-200 "
            "text-black shadow-lg w-full"
        ).props("flat no-caps")
        if state.is_processing or state.system_state == "Pirate Mode":
            pirate_btn.disable()

        ui.button(
            "🛡  DEFENDER MODE",
            on_click=_restore_defaults,
        ).classes(
            "px-3 py-2 rounded-lg text-xs font-medium bg-zinc-900 "
            "hover:bg-zinc-800 text-white border border-white/10 w-full"
        ).props("flat no-caps")


@ui.refreshable
def logs_panel() -> None:
    """Terminal-style log output."""
    with ui.row().classes("items-center justify-between mb-4 w-full"):
        with ui.column().classes("gap-1"):
            ui.label("Execution Terminal").classes("text-xl font-bold text-white")
            ui.label("Live output of system modifications.").classes(
                "text-sm text-zinc-400"
            )
        if state.is_processing:
            with ui.row().classes(
                "items-center gap-3 bg-zinc-900 border border-zinc-800 "
                "px-4 py-2 rounded-lg no-wrap"
            ):
                ui.label("Running...").classes(
                    "text-xs text-white mono animate-pulse"
                )
                with ui.element("div").classes(
                    "w-24 h-1.5 bg-zinc-800 rounded-full overflow-hidden"
                ):
                    ui.element("div").classes(
                        "h-full bg-white transition-all duration-300"
                    ).style(f"width: {state.progress}%")

    with ui.element("div").classes(
        "flex-1 bg-[#0a0a0c] border border-zinc-800 rounded-xl mono text-xs "
        "p-4 overflow-y-auto shadow-inner custom-scrollbar w-full min-h-0"
    ):
        for line in state.logs:
            ui.label(line).classes(f"mb-1.5 leading-relaxed {_log_color(line)}")
        if not state.is_processing and state.logs:
            ui.label("_").classes("mt-4 text-zinc-600 animate-pulse")


@ui.refreshable
def main_pane() -> None:
    """Switches between dashboard and logs based on active tab."""
    if state.active_tab == "dashboard":
        with ui.column().classes("p-6 max-w-6xl mx-auto gap-8 w-full"):
            with ui.column().classes("gap-0 w-full"):
                feature_matrix()
    else:
        with ui.column().classes("p-6 w-full h-full gap-0 min-h-0"):
            logs_panel()


@ui.refreshable
def sidebar_nav() -> None:
    """Sidebar navigation buttons."""
    items = [("dashboard", "dashboard", "Features"), ("logs", "terminal", "Execution Logs")]
    for tab_id, icon_name, label in items:
        is_active = state.active_tab == tab_id
        active_cls = (
            "bg-white/10 text-white"
            if is_active
            else "text-zinc-400 hover:text-zinc-200 hover:bg-white/5"
        )
        with ui.row().classes(
            f"w-full items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium "
            f"transition-all cursor-pointer no-wrap {active_cls}"
        ).on("click", lambda _e, t=tab_id: _switch_tab(t)):
            ui.icon(icon_name).classes("text-base")
            ui.label(label).classes("grow")
            if is_active:
                ui.element("div").classes("w-1 h-4 bg-white rounded-full")


@ui.refreshable
def diagnostics_panel() -> None:
    """Live diagnostics surface — backed by :class:`Preflight`."""
    report = state.preflight

    def _check(ok: bool) -> tuple[str, str]:
        return ("check_circle", "text-emerald-400") if ok else ("error", "text-red-400")

    rows: list[tuple[str, str, bool]] = [
        ("lock", "Admin Privileges", report.is_admin if report else False),
        ("memory", "BIOS VT-x/SVM", report.virtualization if report else False),
        ("favorite", "WMI Health", report.wmi_healthy if report else False),
    ]

    with ui.column().classes(
        "bg-zinc-900/50 border border-white/5 rounded-xl p-3.5 gap-3 w-full"
    ):
        ui.label("DIAGNOSTICS").classes(
            "text-[10px] uppercase text-zinc-500 font-semibold tracking-wider"
        )
        for icon_name, label, ok in rows:
            status_icon, status_color = _check(ok)
            with ui.row().classes("items-center justify-between w-full no-wrap"):
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.icon(icon_name).classes(
                        f"{status_color} text-sm w-4 text-center"
                    )
                    ui.label(label).classes("text-xs text-zinc-300")
                ui.icon(status_icon).classes(f"{status_color} text-sm")
        sac = report.smart_app_control if report else "Unknown"
        with ui.row().classes(
            "pt-3 mt-1 border-t border-white/5 items-start gap-2 no-wrap w-full"
        ):
            ui.icon("info").classes("text-zinc-400 text-sm shrink-0 mt-0.5")
            ui.html(
                "<p class='text-[10px] text-zinc-400 leading-snug'>"
                f"Smart App Control: <strong>{sac}</strong>.</p>"
            )


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


def _switch_tab(tab: str) -> None:
    state.active_tab = tab  # type: ignore[assignment]
    main_pane.refresh()
    sidebar_nav.refresh()


def _toggle_feature(feature_id: int) -> None:
    for f in state.features:
        if f.id == feature_id and not f.locked:
            new_status = f.target if f.status == "Active" else "Active"
            f.status = new_status
            state.add_log(f"[USER] Toggled {f.name} to {new_status}")
            break
    feature_matrix.refresh()
    logs_panel.refresh()


def _restore_defaults() -> None:
    if state.is_processing:
        return
    task = asyncio.create_task(_run_defender_mode())
    state._active_task = task  # keep reference to prevent GC


async def _run_defender_mode() -> None:
    state.is_processing = True
    state.system_state = "Modifying..."
    state.progress = 0
    state.active_tab = "logs"
    state.add_log("[USER] Restoring system to default secure state.")
    system_profile_panel.refresh()
    main_pane.refresh()
    sidebar_nav.refresh()
    logs_panel.refresh()

    loop = asyncio.get_running_loop()

    def on_progress(event: ProgressEvent) -> None:
        loop.call_soon_threadsafe(_handle_progress, event)

    try:
        results = await vbs.revert(progress=on_progress)
    except Exception as exc:
        _logger.exception("Revert failed")
        state.add_log(f"[ERROR] Revert failed: {exc}")
        results = []

    _finalize_workflow(results, success_state="Defender Mode")
    await _refresh_feature_states()


def _open_hello_modal() -> None:
    if state.system_state == "Pirate Mode" or state.is_processing:
        return
    hello_dialog.open()


async def _start_optimization_sequence() -> None:
    state.is_processing = True
    state.progress = 0
    state.system_state = "Modifying..."
    state.active_tab = "logs"

    main_pane.refresh()
    sidebar_nav.refresh()
    system_profile_panel.refresh()
    logs_panel.refresh()

    loop = asyncio.get_running_loop()

    def on_progress(event: ProgressEvent) -> None:
        # Invoked from the worker thread — marshal to the event loop.
        loop.call_soon_threadsafe(_handle_progress, event)

    try:
        results = await vbs.optimize(progress=on_progress)
    except Exception as exc:
        _logger.exception("Optimize failed")
        state.add_log(f"[ERROR] Optimization aborted: {exc}")
        results = []

    _finalize_workflow(results, success_state="Pirate Mode")
    await _refresh_feature_states()


# ---------------------------------------------------------------------------
# Progress + finalization helpers
# ---------------------------------------------------------------------------


def _handle_progress(event: ProgressEvent) -> None:
    """Render a :class:`ProgressEvent` into the Logs tab."""
    state.progress = max(0, min(100, int(event.percent)))
    suffix = f" — {event.message}" if event.message else ""
    state.add_log(f"[{event.level}] {event.step}{suffix}")
    logs_panel.refresh()


def _finalize_workflow(
    results: list[OperationResult], *, success_state: SystemState
) -> None:
    """Apply the final state after a workflow finishes."""
    failed = [r for r in results if r.status == OperationStatus.FAILED]
    needs_reboot = any(r.requires_reboot for r in results)
    state.reboot_pending = needs_reboot

    if failed:
        state.system_state = "Defender Mode"
        state.add_log(f"[ERROR] {len(failed)} step(s) failed. See log for details.")
    else:
        state.system_state = success_state
        state.add_log(f"[SUCCESS] {success_state} applied.")

    if needs_reboot:
        state.add_log("[ALERT] A system restart is required for changes to take effect.")

    state.is_processing = False
    system_profile_panel.refresh()
    feature_matrix.refresh()
    logs_panel.refresh()

    if needs_reboot:
        try:
            reboot_dialog.open()
        except NameError:  # pragma: no cover - dialog not built yet
            pass


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------

hello_dialog: ui.dialog
bitlocker_dialog: ui.dialog
reboot_dialog: ui.dialog


def _trigger_reboot() -> None:
    import subprocess

    state.add_log("[ACTION] Issuing shutdown /r /t 0")
    try:
        subprocess.Popen(["shutdown", "/r", "/t", "0"])  # noqa: S603,S607
    except OSError as exc:
        _logger.error("Could not issue reboot: %s", exc)
        state.add_log(f"[ERROR] Could not reboot: {exc}")
        logs_panel.refresh()


def _build_modals() -> None:
    global hello_dialog, bitlocker_dialog, reboot_dialog

    # --- Windows Hello reset modal -----------------------------------------
    with ui.dialog() as hello_dialog, ui.card().classes(
        "bg-zinc-900 border border-amber-500/30 rounded-2xl shadow-2xl "
        "max-w-md w-full p-6 gap-0"
    ):
        with ui.element("div").classes(
            "w-12 h-12 bg-amber-500/10 rounded-full flex items-center justify-center "
            "mb-4 text-amber-400 border border-amber-500/20"
        ):
            ui.icon("fingerprint").classes("text-2xl")
        ui.label("Windows Hello Reset").classes("text-xl font-bold text-white mb-2")
        ui.label(
            "Disabling VBS will clear your TPM-backed credentials. "
            "Your PIN/Biometrics will be reset."
        ).classes("text-sm text-zinc-400 mb-4")
        with ui.element("div").classes(
            "bg-zinc-950 border border-amber-500/20 rounded-lg p-3 "
            "text-xs text-amber-300 mb-6"
        ):
            ui.html(
                "<strong>Important:</strong> Have your Microsoft Account or Local "
                "Administrator password ready for the next boot phase to reconfigure "
                "sign-in options."
            )
        with ui.row().classes("justify-end gap-3 w-full"):
            ui.button("Cancel", on_click=hello_dialog.close).classes(
                "px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white"
            ).props("flat no-caps")
            ui.button(
                "I Understand",
                on_click=lambda: (hello_dialog.close(), bitlocker_dialog.open()),
            ).classes(
                "px-4 py-2 text-sm font-bold bg-amber-500 hover:bg-amber-400 "
                "text-zinc-950 rounded-lg"
            ).props("flat no-caps")

    # --- BitLocker suspension modal ----------------------------------------
    with ui.dialog() as bitlocker_dialog, ui.card().classes(
        "bg-zinc-900 border border-red-500/30 rounded-2xl shadow-2xl "
        "max-w-md w-full p-6 gap-0"
    ):
        with ui.element("div").classes(
            "w-12 h-12 bg-red-500/10 rounded-full flex items-center justify-center "
            "mb-4 text-red-400 border border-red-500/20"
        ):
            ui.icon("storage").classes("text-2xl")
        ui.label("BitLocker Suspension").classes("text-xl font-bold text-white mb-2")
        ui.label(
            "BCD modifications require suspending BitLocker on drive C:."
        ).classes("text-sm text-zinc-400 mb-4")
        with ui.row().classes(
            "bg-zinc-950 border border-red-500/20 rounded-lg p-3 "
            "text-xs text-red-300 mb-6 gap-3 items-start no-wrap"
        ):
            ui.icon("warning").classes("text-base shrink-0 mt-0.5")
            ui.label(
                "BitLocker will be suspended for 1 reboot. Ensure you are in a secure "
                "physical location before proceeding."
            ).classes("leading-relaxed")
        with ui.row().classes("justify-end gap-3 w-full"):
            ui.button("Abort", on_click=bitlocker_dialog.close).classes(
                "px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white"
            ).props("flat no-caps")
            ui.button(
                "Proceed",
                on_click=lambda: (
                    bitlocker_dialog.close(),
                    asyncio.create_task(_start_optimization_sequence()),
                ),
            ).classes(
                "px-4 py-2 text-sm font-bold bg-red-500 hover:bg-red-400 "
                "text-zinc-950 rounded-lg"
            ).props("flat no-caps")

    # --- Reboot confirmation modal -----------------------------------------
    with ui.dialog() as reboot_dialog, ui.card().classes(
        "bg-zinc-900 border border-amber-500/30 rounded-2xl shadow-2xl "
        "max-w-md w-full p-6 gap-0"
    ):
        with ui.element("div").classes(
            "w-12 h-12 bg-amber-500/10 rounded-full flex items-center justify-center "
            "mb-4 text-amber-400 border border-amber-500/20"
        ):
            ui.icon("restart_alt").classes("text-2xl")
        ui.label("Restart Required").classes("text-xl font-bold text-white mb-2")
        ui.label(
            "Some changes only take effect after a reboot. Restart now?"
        ).classes("text-sm text-zinc-400 mb-6")
        with ui.row().classes("justify-end gap-3 w-full"):
            ui.button("Later", on_click=reboot_dialog.close).classes(
                "px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white"
            ).props("flat no-caps")
            ui.button(
                "Restart now",
                on_click=lambda: (reboot_dialog.close(), _trigger_reboot()),
            ).classes(
                "px-4 py-2 text-sm font-bold bg-amber-500 hover:bg-amber-400 "
                "text-zinc-950 rounded-lg"
            ).props("flat no-caps")


# ---------------------------------------------------------------------------
# Page composition
# ---------------------------------------------------------------------------


def _build_sidebar() -> None:
    with ui.column().classes(
        "w-64 bg-[#0a0a0c] border-r border-white/5 h-screen "
        "flex flex-col z-20 shrink-0 gap-0"
    ):
        # Logo block
        with ui.row().classes("p-6 items-center gap-3 no-wrap"):
            with ui.element("div").classes(
                "bg-zinc-900/80 border border-zinc-700/50 p-2 rounded-lg shadow-lg"
            ):
                ui.icon("shield").classes("text-white text-2xl")
            with ui.column().classes("gap-0"):
                ui.label("HyperGuard92").classes(
                    "text-lg font-bold tracking-tight text-zinc-300 leading-tight"
                )
                ui.label("CONTROL PANEL").classes(
                    "text-[10px] text-zinc-500 mono uppercase tracking-widest"
                )

        # Navigation
        with ui.column().classes("flex-1 px-4 gap-1 mt-4 w-full"):
            sidebar_nav()

        # System profile + optimization engine, then diagnostics
        with ui.column().classes("p-4 gap-4 w-full"):
            system_profile_panel()
            diagnostics_panel()


@ui.page("/")
def index() -> None:
    """Main page route."""
    ui.add_head_html(EXTRA_HEAD)
    ui.dark_mode().enable()

    with ui.row().classes("h-screen w-screen bg-black no-wrap gap-0"):
        _build_sidebar()
        with ui.column().classes(
            "flex-1 min-w-0 overflow-y-auto custom-scrollbar h-screen gap-0"
        ):
            main_pane()

    _build_modals()

    async def _bootstrap() -> None:
        await _run_preflight()
        diagnostics_panel.refresh()
        logs_panel.refresh()
        await _refresh_feature_states()

    ui.timer(0.1, lambda: asyncio.create_task(_bootstrap()), once=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_app(host: str = "127.0.0.1", port: int = 8492, native: bool = True) -> None:
    """Launch the NiceGUI server. Called from ``src/__main__.py``."""
    ui.run(
        host=host,
        port=port,
        title="HyperGuard92 — Control Panel",
        dark=True,
        native=native,
        window_size=(1400, 900) if native else None,
        reload=False,
        show=not native,
        favicon="🛡️",
    )
