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


def _build_stt_client(backend: str):
    """Return the configured STT client for the requested backend.

    Unknown backend strings fall back to local Whisper (CPU) so a dropdown
    typo doesn't disable dictation.
    """
    backend = (backend or "").lower()
    if backend == "whisper-http":
        logger.info(f"STT: Whisper HTTP → {settings.whisper_url}")
        return WhisperClient(url=settings.whisper_url)
    if backend == "whisper-local-gpu":
        # Force CUDA + float16. If the runtime DLLs are missing the client
        # already falls back to CPU+int8 automatically at inference time.
        logger.info(f"STT: Whisper local GPU (model={settings.whisper_model}, cuda/float16)")
        return LocalWhisperClient(
            model_size=settings.whisper_model,
            device="cuda",
            compute_type="float16",
        )
    if backend in ("moonshine-tiny", "moonshine-base"):
        # The ONNX-flavored package imports as `moonshine_onnx`; the torch
        # flavor as `moonshine`. Accept either so Python 3.13 users (where
        # the torch flavor's pin is broken) can still use the ONNX variant.
        try:
            import moonshine_onnx  # noqa: F401
        except ImportError:
            try:
                import moonshine  # noqa: F401
            except ImportError as e:
                raise ImportError(
                    "Moonshine STT requires the [moonshine] extra "
                    f"(missing: {getattr(e, 'name', None) or e}). "
                    "Install with: pip install -e '.[moonshine]'"
                ) from e
        from src.ai.moonshine_stt_client import MoonshineSTTClient
        model_name = (
            "moonshine/tiny" if backend == "moonshine-tiny" else "moonshine/base"
        )
        logger.info(f"STT: Moonshine ({model_name})")
        return MoonshineSTTClient(model=model_name)
    if backend == "parakeet-tdt":
        try:
            import nemo.collections.asr as _nemo_asr  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "Parakeet STT requires the [parakeet] extra "
                f"(missing: {getattr(e, 'name', None) or e}). "
                "Install with: pip install -e '.[parakeet]'"
            ) from e
        from src.ai.parakeet_stt_client import ParakeetSTTClient
        logger.info(f"STT: Parakeet-TDT ({settings.parakeet_model})")
        return ParakeetSTTClient(model=settings.parakeet_model)
    if backend == "vosk":
        try:
            import vosk  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "Vosk STT requires the [vosk] extra "
                f"(missing: {getattr(e, 'name', None) or e}). "
                "Install with: pip install -e '.[vosk]'"
            ) from e
        if not settings.vosk_model_path:
            raise ValueError(
                "Vosk requires VOSK_MODEL_PATH pointing at an unpacked Vosk "
                "model directory (download from https://alphacephei.com/vosk/models)."
            )
        from src.ai.vosk_stt_client import VoskSTTClient
        logger.info(f"STT: Vosk ({settings.vosk_model_path})")
        return VoskSTTClient(model_path=settings.vosk_model_path)
    if backend in ("gemma-e2b", "gemma-e4b", "gemma-e2b-4bit", "gemma-e4b-4bit"):
        # Validate heavy deps up front so a missing [gemma] extra surfaces in
        # the UI status pill instead of silently failing later on the warm thread.
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError as e:
            missing = getattr(e, "name", None) or str(e)
            raise ImportError(
                f"Gemma STT requires the [gemma] extra (missing: {missing}). "
                f"Install with: pip install -e '.[gemma]'"
            ) from e
        quantize_4bit = backend.endswith("-4bit")
        if quantize_4bit:
            try:
                import bitsandbytes  # noqa: F401
            except ImportError as e:
                raise ImportError(
                    "4-bit Gemma requires bitsandbytes (shipped with the "
                    "[gemma] extra). Re-run: pip install -e '.[gemma]'"
                ) from e
        from src.ai.gemma_stt_client import GemmaSTTClient
        # The instruction-tuned (-it) variants ship with the chat template that
        # the multimodal processor needs; the base repos don't.
        model_id = (
            "google/gemma-4-E4B-it"
            if backend.startswith("gemma-e4b")
            else "google/gemma-4-E2B-it"
        )
        label = f"Gemma 4 ({model_id}{', 4-bit' if quantize_4bit else ''})"
        logger.info(f"STT: {label}")
        return GemmaSTTClient(model_id=model_id, quantize_4bit=quantize_4bit)
    # Default / fallback: whisper-local-cpu (also handles legacy "whisper-local").
    logger.info(f"STT: Whisper local CPU (model={settings.whisper_model}, cpu/int8)")
    return LocalWhisperClient(
        model_size=settings.whisper_model,
        device="cpu",
        compute_type="int8",
    )


def main():
    logger.info("Initializing Local AI Radiology Dictation Platform...")

    app = QApplication(sys.argv)

    # 1. Initialize AI clients from settings (env-configurable, no hardcoded URLs)
    stt = _build_stt_client(settings.stt_backend)
    llm = LLMClient(url=settings.llm_url)
    recorder = AudioRecorder()
    profiler = LatencyTimer()

    # Preload heavy local models in the background so the first dictation
    # doesn't block on model download/load. Any client that implements warm()
    # participates; HTTP clients don't.
    if hasattr(stt, "warm"):
        threading.Thread(target=stt.warm, daemon=True).start()

    # 2. Setup Orchestrator (LLM client wired in for impression generation)
    orchestrator = DictationOrchestrator(
        recorder=recorder,
        stt_client=stt,
        wedge=wedge,
        profiler=profiler,
        llm_client=llm,
    )

    # 3. Setup UI
    window = MainWindow()
    window.profiler = profiler
    window.show()

    # 4. Streaming live-partial transcriber — ticks every 1.5s during recording
    streaming = StreamingTranscriber(recorder, stt, interval_ms=1500)
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
                # Only drive live partials if the active STT engine is fast
                # enough per tick (Gemma is too slow; it only runs on Stop).
                if getattr(orchestrator.stt_client, "supports_streaming", True):
                    streaming.start()
        else:
            window.set_status("Processing...", "#fab387")
            if mode == "inapp":
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
                if result:
                    logger.info(f"Wedge sent: {result!r}")
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
        if hasattr(new_client, "warm"):
            threading.Thread(target=new_client.warm, daemon=True).start()
        window.set_status(f"STT: {backend}")

    window.on_stt_changed = on_stt_changed
    window.set_stt_backend(settings.stt_backend)
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
