import sys
import threading
import sounddevice as sd
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication
from loguru import logger

from src.ui.main_window import MainWindow
from src.hardware.recorder import AudioRecorder, list_input_devices
from src.hardware.mic_listener import MicListener
from src.hardware.global_hotkey import GlobalHotkey, VK_F4, MOD_NOREPEAT
from src.ai.whisper_client import WhisperClient
from src.ai.local_whisper_client import LocalWhisperClient
from src.ai.llm_client import LLMClient
from src.core.orchestrator import DictationOrchestrator
from src.core.streaming import StreamingTranscriber
from src.engine import wedge
from src.utils.profiler import LatencyTimer
from src.utils.settings import settings


def _build_whisper_client():
    """Return the configured STT client based on WHISPER_MODE."""
    if settings.whisper_mode == "http":
        logger.info(f"Whisper mode: HTTP → {settings.whisper_url}")
        return WhisperClient(url=settings.whisper_url)
    logger.info(
        f"Whisper mode: local (model={settings.whisper_model}, "
        f"device={settings.whisper_device})"
    )
    return LocalWhisperClient(
        model_size=settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


def main():
    logger.info("Initializing Local AI Radiology Dictation Platform...")

    app = QApplication(sys.argv)

    # 1. Initialize AI clients from settings (env-configurable, no hardcoded URLs)
    whisper = _build_whisper_client()
    llm = LLMClient(url=settings.llm_url)
    recorder = AudioRecorder()
    profiler = LatencyTimer()

    # Preload the local Whisper model in the background so the first
    # dictation doesn't block on model download/load.
    if isinstance(whisper, LocalWhisperClient):
        threading.Thread(target=whisper.warm, daemon=True).start()

    # 2. Setup Orchestrator (LLM client wired in for impression generation)
    orchestrator = DictationOrchestrator(
        recorder=recorder,
        whisper_client=whisper,
        wedge=wedge,
        profiler=profiler,
        llm_client=llm,
    )

    # 3. Setup UI
    window = MainWindow()
    window.profiler = profiler
    window.show()

    # 4. Streaming live-partial transcriber — ticks every 1.5s during recording
    streaming = StreamingTranscriber(recorder, whisper, interval_ms=1500)
    streaming.partial_ready.connect(window.update_partial)

    # 5. Dictation trigger handler — shared by HID mic, F4, and Record/Stop buttons
    recording_state = {"active": False}

    def handle_trigger(pressed: bool):
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
                orchestrator.handle_trigger_down()
                # No streaming in Wedge mode: partials have nowhere to render.
            else:
                window.set_status("Recording...", "#f38ba8")
                window.begin_streaming()
                orchestrator.handle_trigger_down()
                streaming.start()
        else:
            window.set_status("Processing...", "#fab387")
            if mode == "inapp":
                streaming.stop()
            result = orchestrator.handle_trigger_up(mode=mode)
            if mode == "wedge":
                if result:
                    window.append_text(result)
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
    else:
        f4_shortcut = QShortcut(QKeySequence("F4"), window)
        f4_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        f4_shortcut.activated.connect(f4_toggle)

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

    # 9. Shutdown cleanup — close HID, global hotkey, and audio stream when app exits
    def on_shutdown():
        logger.info("Shutting down...")
        try:
            f4_hotkey.unregister()
        except Exception as e:
            logger.warning(f"Error unregistering global hotkey: {e}")
        try:
            mic.stop()
        except Exception as e:
            logger.warning(f"Error stopping mic listener: {e}")
        try:
            recorder.stop()
        except Exception as e:
            logger.warning(f"Error stopping recorder: {e}")

    app.aboutToQuit.connect(on_shutdown)

    logger.info("Application ready.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
