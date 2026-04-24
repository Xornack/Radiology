import sys
import sounddevice as sd
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication
from loguru import logger

from src.ui.main_window import MainWindow
from src.hardware.recorder import AudioRecorder, list_input_devices
from src.hardware.mic_listener import MicListener
from src.hardware.global_hotkey import GlobalHotkey, VK_F4, MOD_NOREPEAT
from src.ai.ollama_client import OllamaClient
from src.ai.stt_registry import build_stt_client
from src.core.orchestrator import DictationOrchestrator
from src.core.streaming import StreamingTranscriber
from src.engine import wedge
from src.ui.warmup_coordinator import WarmupCoordinator
from src.utils.profiler import LatencyTimer
from src.utils.settings import settings


def _build_stt_client(backend: str):
    """Thin wrapper over `stt_registry.build_stt_client`. Kept so existing
    tests that monkeypatch `main._build_stt_client` still work."""
    return build_stt_client(backend, settings)


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

    # Wire the warm-up coordinator now that the window exists.
    def _on_warm_ready():
        window.set_warming(False)

    def _on_warm_failed(msg: str):
        window.set_status(f"STT failed — {msg}", "#f38ba8")

    warmup.ready.connect(_on_warm_ready)
    warmup.failed.connect(_on_warm_failed)
    window.set_warming(True)
    warmup.warm_in_background(stt)

    # 3. Streaming live-partial transcriber — ticks every 1.5s during recording.
    # Constructed before the orchestrator so the orchestrator can be wired to
    # read its committed-snapshot on Stop.
    streaming = StreamingTranscriber(recorder, stt, interval_ms=1500)
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

    # Route each streaming commit by the active dictation mode. In-app
    # sends the chunk to the editor's live-region controller; wedge types
    # it into the externally focused window via the orchestrator helper
    # (which also maintains the leading-space / capitalization state
    # consumed later by the Stop-path remainder).
    def _on_streaming_commit(text: str):
        if window.current_mode() == "wedge":
            orchestrator.type_wedge_commit(text)
        else:
            window.on_commit(text)

    streaming.commit_ready.connect(_on_streaming_commit)

    # 5. Dictation trigger handler — shared by HID mic, F4, and Record/Stop buttons
    recording_state = {"active": False}

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
                # still stream — see _on_streaming_commit.
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
            streaming.stop()
            try:
                result = orchestrator.handle_trigger_up(mode=mode)
            except Exception as e:
                # A Whisper / recorder / wedge crash must not leave the UI
                # stuck on "Processing..." forever. Reset the partial anchor
                # so the next session starts clean, then surface the failure.
                logger.error(f"Dictation processing failed: {e}")
                if mode == "inapp":
                    window.commit_partial("")
                window.set_status("Processing failed", "#f38ba8")
                return

            if mode == "wedge":
                # Do NOT append to the in-app editor — Wedge mode's destination
                # is the externally focused window. Audit trail goes to the log.
                # `result` is just the remainder post-Stop; commits were typed
                # mid-session, so "success" means we typed SOMETHING — either a
                # commit during streaming or the remainder on Stop.
                had_commits = bool(streaming.get_committed_snapshot()[0])
                if result or had_commits:
                    logger.info(f"Wedge sent remainder: {result!r}")
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

    # Wire the Record/Stop buttons to the same toggle path
    window.on_toggle_recording = handle_trigger

    # Populate the microphone dropdown and wire device selection
    def on_mic_changed(device_index):
        label = "system default" if device_index is None else f"index {device_index}"
        logger.info(f"Audio input device set to {label}")
        recorder.set_device(device_index)

    window.on_mic_changed = on_mic_changed

    def on_mode_changed(mode: str):
        # Ignore mid-recording (the UI also disables the combo, but guard here too).
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

    # Tracks the currently-active STT backend so a failed switch can revert
    # the combo to what's actually running under the hood.
    active_stt_backend = {"value": settings.stt_backend}

    def on_stt_changed(backend: str):
        # Rebuild the STT client and swap it into every consumer. Recording is
        # blocked mid-session by the UI lock, so we can replace the reference
        # atomically with no in-flight work to migrate.
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

    def on_radiology_mode_changed(enabled: bool):
        orchestrator.radiology_mode = enabled
        window.set_status(f"Radiology vocabulary: {'on' if enabled else 'off'}")
        logger.info(f"Radiology vocabulary correction: {enabled}")

    window.on_radiology_mode_changed = on_radiology_mode_changed
    orchestrator.radiology_mode = settings.radiology_mode
    window.set_radiology_mode(settings.radiology_mode)
    window.populate_microphones(list_input_devices(), selected_index=None)

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
        # Retry the HID medical mic if it wasn't connected at startup.
        if mic.device is None:
            if mic.start():
                logger.info("Medical microphone connected on refresh.")
        logger.info(f"Device list refreshed ({len(devices)} input devices).")
        window.set_status("Devices refreshed")

    window.on_refresh_devices = on_refresh_devices

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

    mic_connected = mic.start()
    if mic_connected:
        logger.info("Medical microphone detected and initialized.")
    else:
        logger.warning("No medical microphone found. Using keyboard fallback (F4).")

    # 7. F4 toggles recording. Prefer a global hotkey (fires regardless of
    # focused window — critical for Wedge mode into Chrome/Outlook/etc.) and
    # fall back to an app-local Qt shortcut if registration fails (e.g., another
    # app already holds F4).
    def f4_toggle():
        handle_trigger(not recording_state["active"])

    f4_hotkey = GlobalHotkey(vk=VK_F4, modifiers=MOD_NOREPEAT)
    if f4_hotkey.register():
        f4_hotkey.activated.connect(f4_toggle)
        f4_shortcut = None
        logger.info("F4 recording trigger registered as global hotkey.")
    else:
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

    # 8. Wire the Generate Impression button
    def do_generate_impression():
        findings = window.get_findings().strip()
        if not findings:
            window.set_status("No findings to summarize", "#f9e2af")
            return
        window.set_status("Generating impression...", "#89b4fa")
        window.impression_btn.setEnabled(False)
        try:
            impression = orchestrator.generate_impression(findings)
        finally:
            window.impression_btn.setEnabled(True)
        if impression:
            window.append_text("")
            window.append_text("IMPRESSION: " + impression)
            window.set_status("Ready")
        else:
            window.set_status("Impression failed", "#f38ba8")

    window.on_generate_impression = do_generate_impression

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
        try:
            structured = orchestrator.structure_report(text)
        finally:
            window.structure_btn.setEnabled(True)
        if structured:
            window.editor.setPlainText(structured)
            window.set_status("Ready")
        else:
            window.set_status("Structuring failed", "#f38ba8")

    window.on_structure_report = do_structure_report

    # 9. Shutdown cleanup — stop every background source in reverse order
    # (producer → consumer). Each step is wrapped independently so an
    # earlier failure doesn't skip later ones and leak resources.
    def on_shutdown():
        logger.info("Shutting down...")
        shutdown_tasks = [
            ("global hotkey", f4_hotkey.unregister),
            ("mic listener",  mic.stop),
            ("streaming",     streaming.stop),
            ("recorder",      recorder.stop),
        ]
        for label, task in shutdown_tasks:
            try:
                task()
            except Exception as e:
                logger.warning(f"Error stopping {label}: {e}")

    app.aboutToQuit.connect(on_shutdown)

    logger.info("Application ready.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
