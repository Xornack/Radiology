import sys
import sounddevice as sd
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication
from loguru import logger

from src.ui.main_window import MainWindow
from src.ui.field_navigator import FieldRegistry, FieldHighlighter, FieldNavigator
from src.hardware.recorder import AudioRecorder, list_input_devices
from src.hardware.mic_listener import MicListener
from src.hardware.global_hotkey import GlobalHotkey, VK_F4, MOD_NOREPEAT
from src.ai.ollama_client import OllamaClient
from src.ai.stt_registry import build_stt_client
from src.core.orchestrator import DictationOrchestrator
from src.core.streaming import StreamingTranscriber
from src.engine import wedge
from src.ui.warmup_coordinator import WarmupCoordinator
from src.ui.llm_worker import LlmWorker
from src.ui.stop_path_worker import StopPathWorker
from src.utils.profiler import LatencyTimer
from src.utils.settings import settings


def _build_stt_client(backend: str):
    """Thin wrapper over `stt_registry.build_stt_client`. Kept module-level
    so tests and profiler scenarios can patch `main._build_stt_client`."""
    return build_stt_client(backend, settings)


def _wire_warmup(window, warmup, stt_client):
    """Hook warmup signals to the UI and kick off the initial warm pass."""
    def _on_ready():
        window.set_warming(False)

    def _on_failed(msg: str):
        window.set_status(f"STT failed — {msg}", "#f38ba8")

    warmup.ready.connect(_on_ready)
    warmup.failed.connect(_on_failed)
    window.set_warming(True)
    warmup.warm_in_background(stt_client)


def _wire_streaming_commits(window, orchestrator, streaming):
    """Route each streaming commit to the active dictation destination.

    In-app sends the chunk to the editor's live-region controller; wedge
    types it into the externally focused window via the orchestrator helper
    (which also maintains the leading-space / capitalization state consumed
    later by the Stop-path remainder).
    """
    def _on_streaming_commit(text: str):
        if window.current_mode() == "wedge":
            orchestrator.type_wedge_commit(text)
        else:
            window.on_commit(text)

    streaming.commit_ready.connect(_on_streaming_commit)


def _create_stop_worker(window, orchestrator, streaming):
    """Build the off-thread Stop worker and wire its result handlers.

    The worker moves orchestrator.handle_trigger_up off the Qt main thread
    (the remainder transcribe can take 1-5s). On completion the worker
    emits `finished`/`failed` on the main thread via Qt's AutoConnection,
    and the handlers below paint the final status.
    """
    stop_worker = StopPathWorker(orchestrator)

    def _on_stop_finished(mode: str, result: str):
        if mode == "wedge":
            # Do NOT append to the in-app editor — Wedge mode's destination
            # is the externally focused window. Audit trail goes to the log.
            # `result` is just the remainder post-Stop; commits were typed
            # mid-session, so "success" means we typed SOMETHING — either a
            # commit during streaming or the remainder on Stop.
            had_commits = bool(streaming.get_committed_snapshot()[0])
            if result or had_commits:
                logger.info(f"Wedge sent remainder: {len(result)} chars")
                window.set_status("Ready")
            else:
                window.set_status("No text recognized", "#f9e2af")
        else:
            if result:
                window.commit_partial(result)
                window.set_status("Ready")
            else:
                window.commit_partial("")
                window.set_status("No text recognized", "#f9e2af")

    def _on_stop_failed(mode: str, _err: str):
        # A Whisper / recorder / wedge crash must not leave the UI stuck
        # on "Processing..." forever. Reset the partial anchor so the next
        # session starts clean, then surface the failure.
        if mode == "inapp":
            window.commit_partial("")
        window.set_status("Processing failed", "#f38ba8")

    stop_worker.finished.connect(_on_stop_finished)
    stop_worker.failed.connect(_on_stop_failed)
    return stop_worker


def _make_trigger_handler(window, orchestrator, streaming, stop_worker, recording_state):
    """Build the shared record/stop toggle used by HID, F4, and the button."""
    def handle_trigger(pressed: bool):
        # Drop triggers while the STT model is still warming up. A short
        # nudge tells the user what's happening instead of silently
        # doing nothing. Only applies to trigger-down; a release with
        # no active recording is already a no-op below.
        if pressed and window.is_warming():
            window.set_status("Still warming — please wait", "#f9e2af")
            return

        # Idempotent: clicking Record while already recording (or Stop while idle)
        # is a no-op. Keeps HID, F4, and button sources consistent.
        if pressed == recording_state["active"]:
            return
        recording_state["active"] = pressed
        mode = window.current_mode()
        window.set_recording_state(pressed)

        if pressed:
            if mode == "wedge":
                window.set_status("Recording (Wedge)...", "#f38ba8")
                # No begin_streaming(): wedge mode skips live partials
                # (external apps can't be rewritten mid-field). Commits
                # still stream — see _wire_streaming_commits.
            else:
                window.set_status("Recording...", "#f38ba8")
                window.begin_streaming()
            orchestrator.handle_trigger_down()
            # Only drive streaming if the active STT engine is fast
            # enough per tick (Gemma is too slow; it only runs on Stop).
            if getattr(orchestrator.stt_client, "supports_streaming", True):
                streaming.start()
        else:
            window.set_status("Processing...", "#fab387")
            # streaming.stop() still blocks briefly (joins the in-flight
            # tick worker, up to 2s) so get_committed_snapshot() below
            # reads a consistent commit pointer. That short block is
            # acceptable; the long transcribe is what's off-thread now.
            streaming.stop()
            stop_worker.run(mode)

    return handle_trigger


def _wire_stt_switching(window, orchestrator, streaming, warmup, recording_state):
    """Wire the STT-engine combo to live backend switching.

    Tracks the currently-active backend so a failed switch can revert the
    combo to what's actually running under the hood.
    """
    active_stt_backend = {"value": settings.stt_backend}

    def on_stt_changed(backend: str):
        # Rebuild the STT client and swap it into every consumer. Recording is
        # blocked mid-session by the UI lock, so we can replace the reference
        # atomically with no in-flight work to migrate.
        #
        # Model instantiation is synchronous here (1-2s stutter on backend
        # swap). Moving it to a worker thread is in the backlog — it needs
        # careful cross-thread Qt plumbing and the stutter is infrequent
        # enough (user action, not per-tick) that it's a later polish item.
        if recording_state["active"]:
            return
        try:
            new_client = _build_stt_client(backend)
        except Exception as e:
            logger.error(f"Failed to build STT client for {backend!r}: {e}")
            window.set_status(f"STT init failed — {e}", "#f38ba8")
            window.set_stt_backend(active_stt_backend["value"])
            return
        orchestrator.stt_client = new_client
        streaming.stt_client = new_client
        active_stt_backend["value"] = backend
        window.set_warming(True)
        warmup.warm_in_background(new_client)
        window.set_status(f"STT: {backend}")

    window.on_stt_changed = on_stt_changed
    window.set_stt_backend(settings.stt_backend)


def _register_f4_hotkey(window, handle_trigger, recording_state):
    """Register F4 as a global hotkey, falling back to app-local on conflict.

    Returns (hotkey, shortcut_or_none). The shortcut is None when the
    global registration succeeds. The shutdown path needs the hotkey
    handle to unregister; the shortcut is owned by Qt's parent chain.
    """
    def f4_toggle():
        handle_trigger(not recording_state["active"])

    f4_hotkey = GlobalHotkey(vk=VK_F4, modifiers=MOD_NOREPEAT)
    if f4_hotkey.register():
        f4_hotkey.activated.connect(f4_toggle)
        logger.info("F4 recording trigger registered as global hotkey.")
        return f4_hotkey, None

    f4_shortcut = QShortcut(QKeySequence("F4"), window)
    f4_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
    f4_shortcut.activated.connect(f4_toggle)
    # Surface the degraded mode in the UI: the app-local shortcut only
    # fires when the window has focus, which is useless for Wedge mode
    # (where the user intentionally focuses another app). Users should
    # know that F4 won't work while Chrome/Outlook/etc. is foreground.
    logger.warning(
        "Global F4 hotkey unavailable (another app is holding it?); "
        "falling back to app-local shortcut — F4 only fires when this "
        "window has focus."
    )
    window.set_status(
        "F4 works only when this window is focused", "#f9e2af"
    )
    return f4_hotkey, f4_shortcut


def _wire_llm_buttons(window, orchestrator):
    """Wire Generate Impression and Structure Report to the LLM worker.

    Both round-trip through Ollama on a background thread via LlmWorker,
    so the UI stays responsive during the 2-30s call. Signal handlers
    paint the result and re-enable the button — the button-disable
    happens up front and is the only UI state we mutate synchronously.
    """
    llm_worker = LlmWorker(orchestrator)

    def _on_impression_ready(impression: str):
        window.append_text("")
        window.append_text("IMPRESSION: " + impression)
        window.set_status("Ready")
        window.impression_btn.setEnabled(True)

    def _on_impression_failed(_msg: str):
        window.set_status("Impression failed", "#f38ba8")
        window.impression_btn.setEnabled(True)

    def _on_structure_ready(structured: str):
        window.editor.setPlainText(structured)
        window.set_status("Ready")
        window.structure_btn.setEnabled(True)

    def _on_structure_failed(_msg: str):
        window.set_status("Structuring failed", "#f38ba8")
        window.structure_btn.setEnabled(True)

    llm_worker.impression_ready.connect(_on_impression_ready)
    llm_worker.impression_failed.connect(_on_impression_failed)
    llm_worker.structure_ready.connect(_on_structure_ready)
    llm_worker.structure_failed.connect(_on_structure_failed)

    def do_generate_impression():
        findings = window.get_findings().strip()
        if not findings:
            window.set_status("No findings to summarize", "#f9e2af")
            return
        window.set_status("Generating impression...", "#89b4fa")
        window.impression_btn.setEnabled(False)
        llm_worker.run_impression(findings)

    # Structure Report — replaces editor contents with the ACR six-section
    # template via the same Ollama pipeline. Editor is left untouched on
    # failure so a network blip can't destroy the user's text. Ctrl+Z
    # reverts the replacement via QTextEdit's built-in undo stack.
    def do_structure_report():
        text = window.get_findings().strip()
        if not text:
            window.set_status("No text to structure", "#f9e2af")
            return
        window.set_status("Structuring report...", "#89b4fa")
        window.structure_btn.setEnabled(False)
        llm_worker.run_structure(text)

    window.on_generate_impression = do_generate_impression
    window.on_structure_report = do_structure_report
    return llm_worker


def _register_shutdown(app, f4_hotkey, mic, streaming, recorder, warmup):
    """Stop every background source in reverse order (producer → consumer).

    Each step is wrapped independently so an earlier failure doesn't skip
    later ones and leak resources.
    """
    def on_shutdown():
        logger.info("Shutting down...")
        shutdown_tasks = [
            ("global hotkey", f4_hotkey.unregister),
            ("mic listener",  mic.stop),
            ("streaming",     streaming.stop),
            ("recorder",      recorder.stop),
            ("warmup",        warmup.shutdown),
        ]
        for label, task in shutdown_tasks:
            try:
                task()
            except Exception as e:
                logger.warning(f"Error stopping {label}: {e}")

    app.aboutToQuit.connect(on_shutdown)


def _wire_field_navigator(window, recording_state) -> tuple:
    """Attach field detection, highlighting, and Ctrl+Tab navigation to the editor.

    Returns the registry/highlighter/navigator triple so main() can keep
    references alive (otherwise the highlighter — a QObject child of the
    document — is fine, but the navigator is a child of the editor and
    auto-managed; the registry has no parent and would be GC'd if dropped).
    """
    registry = FieldRegistry(window.editor)
    highlighter = FieldHighlighter(window.editor.document(), registry, window.editor)
    navigator = FieldNavigator(
        window.editor,
        registry,
        is_recording_fn=lambda: recording_state["active"],
    )
    return registry, highlighter, navigator


def main():
    logger.info("Initializing Local AI Radiology Dictation Platform...")

    app = QApplication(sys.argv)

    # 1. Initialize AI clients from settings (env-configurable, no hardcoded URLs)
    stt = _build_stt_client(settings.stt_backend)
    llm = OllamaClient(url=settings.ollama_url, model=settings.ollama_model)
    recorder = AudioRecorder()
    profiler = LatencyTimer()

    # Preload heavy local models in the background so the first dictation
    # doesn't block on model download/load. The coordinator wraps the
    # warm thread with Qt signals so the UI can show "Warming model..."
    # and disable Record until ready. Clients without warm() (HTTP)
    # shortcut to ready() immediately inside the coordinator.
    warmup = WarmupCoordinator()

    # 2. Setup UI
    window = MainWindow()
    window.profiler = profiler
    window.show()

    _wire_warmup(window, warmup, stt)

    # 3. Streaming live-partial transcriber — ticks every 1.5s during recording.
    # Constructed before the orchestrator so the orchestrator can be wired to
    # read its committed-snapshot on Stop.
    streaming = StreamingTranscriber(
        recorder, stt, interval_ms=1500, profiler=profiler
    )
    streaming.partial_ready.connect(window.update_partial)

    # 4. Setup Orchestrator (LLM client wired in for impression generation).
    # `streaming` handle enables the commit-aware Stop path: both modes
    # read committed chunks and only transcribe the remaining partial
    # region on Stop.
    orchestrator = DictationOrchestrator(
        recorder=recorder,
        stt_client=stt,
        wedge=wedge,
        profiler=profiler,
        llm_client=llm,
        streaming=streaming,
    )

    _wire_streaming_commits(window, orchestrator, streaming)

    # 5. Dictation trigger handler — shared by HID mic, F4, and Record/Stop buttons
    recording_state = {"active": False}
    stop_worker = _create_stop_worker(window, orchestrator, streaming)
    handle_trigger = _make_trigger_handler(
        window, orchestrator, streaming, stop_worker, recording_state
    )
    window.on_toggle_recording = handle_trigger

    # Field navigation: detect [bracket] fields, highlight as pills,
    # and intercept Ctrl+Tab in the editor to walk between them.
    _field_registry, _field_highlighter, _field_navigator = _wire_field_navigator(
        window, recording_state
    )

    # Microphone picker
    def on_mic_changed(device_index):
        label = "system default" if device_index is None else f"index {device_index}"
        logger.info(f"Audio input device set to {label}")
        recorder.set_device(device_index)

    window.on_mic_changed = on_mic_changed

    # Mode switch is mostly cosmetic — the heavy lifting (read-only flag) is
    # already inside MainWindow.set_dictation_mode; this handler just nudges
    # the user when they enter Wedge mode.
    def on_mode_changed(mode: str):
        if recording_state["active"]:
            return
        if mode == "wedge":
            window.set_status(
                "Wedge mode — click into the target window, then hold the mic",
                "#89b4fa",
            )
        else:
            window.set_status("Ready")
        logger.info(f"Dictation mode: {mode}")

    window.on_mode_changed = on_mode_changed

    _wire_stt_switching(window, orchestrator, streaming, warmup, recording_state)

    def on_radiology_mode_changed(enabled: bool):
        orchestrator.radiology_mode = enabled
        window.set_status(f"Radiology vocabulary: {'on' if enabled else 'off'}")
        logger.info(f"Radiology vocabulary correction: {enabled}")

    window.on_radiology_mode_changed = on_radiology_mode_changed
    orchestrator.radiology_mode = settings.radiology_mode
    window.set_radiology_mode(settings.radiology_mode)
    window.populate_microphones(list_input_devices(), selected_index=None)

    # 6. Setup Hardware Listener (VID/PID from env or defaults)
    mic = MicListener(
        vendor_id=settings.speechmike_vid,
        product_id=settings.speechmike_pid,
    )
    # Signal emitted from the HID polling thread; AutoConnection queues it to
    # the GUI thread so handle_trigger runs where it can safely touch Qt widgets
    # and timers. Using the legacy on_trigger callback here crashes Qt because
    # it invokes begin_streaming() / streaming.start() on the wrong thread.
    mic.trigger_changed.connect(handle_trigger)

    if mic.start():
        logger.info("Medical microphone detected and initialized.")
    else:
        logger.warning("No medical microphone found. Using keyboard fallback (F4).")

    # Devices refresh — wired here (after `mic` exists) so the closure can
    # retry the HID mic if it wasn't connected at startup.
    def on_refresh_devices():
        # Force PortAudio to re-enumerate so hot-plugged mics appear.
        # Safe here because the refresh button is disabled during recording.
        try:
            sd._terminate()
            sd._initialize()
        except Exception as e:
            logger.warning(f"Audio device re-enumeration failed: {e}")
        devices = list_input_devices()
        window.populate_microphones(devices, selected_index=recorder.device)
        if mic.device is None and mic.start():
            logger.info("Medical microphone connected on refresh.")
        logger.info(f"Device list refreshed ({len(devices)} input devices).")
        window.set_status("Devices refreshed")

    window.on_refresh_devices = on_refresh_devices

    # 7. F4 toggles recording. Prefer a global hotkey (fires regardless of
    # focused window — critical for Wedge mode into Chrome/Outlook/etc.) and
    # fall back to an app-local Qt shortcut if registration fails.
    f4_hotkey, _f4_shortcut = _register_f4_hotkey(window, handle_trigger, recording_state)

    # 8. Wire the Generate Impression / Structure Report buttons.
    _wire_llm_buttons(window, orchestrator)

    # 9. Shutdown cleanup.
    _register_shutdown(app, f4_hotkey, mic, streaming, recorder, warmup)

    logger.info("Application ready.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
