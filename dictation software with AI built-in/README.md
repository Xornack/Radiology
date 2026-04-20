# Radiology Dictation Platform

Local, privacy-first AI dictation for radiology workflows. Audio is captured,
transcribed via Whisper, PHI-scrubbed, and typed into any focused application
via a Win32 keyboard wedge. An optional local LLM generates impressions from
findings. No PHI leaves the machine.

## Features

- **Live transcription** — words appear in italic gray as you dictate, committed to final text on Stop.
- **Local Whisper STT** via `faster-whisper` (CPU `int8` by default, optional CUDA).
- **PHI scrubbing** before any AI hand-off (SSN, MRN, DOB, patient/titled names, phone, email).
- **Keyboard wedge** using Win32 `SendInput` with scan codes for legacy radiology-app compatibility; Unicode fallback so no characters are silently dropped (em-dash, curly quotes, `°`, `±`, `µ`).
- **Hardware trigger support** for Philips SpeechMike / Nuance PowerMic over HID.
- **UI controls** — Record / Stop / Clear / Generate Impression buttons, microphone picker.
- **Keyboard fallback** — `F4` toggles recording when no HID mic is connected.
- **DICOM PACS C-FIND** client for fetching patient priors (library-ready; not yet wired into UI).
- **Resilience** — Whisper retry with backoff, fast-fail on connection-refused, PACS connection timeouts, thread-safe audio buffer, shutdown cleanup.

## Quick Start

```bash
pip install -e .
python -m src.main
```

For development (adds `pytest`, `pytest-qt`):

```bash
pip install -e '.[dev]'
```

The first launch downloads the default Whisper model (`base.en`, ~140 MB) from Hugging Face.

Press `F4` or click **● Record** to dictate. Click **■ Stop** when done — the
final transcript replaces the live partial and is typed into the foreground app.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `WHISPER_MODE` | `local` | `local` = in-process faster-whisper; `http` = call `WHISPER_URL` |
| `WHISPER_MODEL` | `base.en` | Any faster-whisper model (`tiny.en`, `small.en`, `medium.en`, `large-v3`) |
| `WHISPER_DEVICE` | `cpu` | `cpu` or `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` | `int8` / `int8_float16` / `float16` / `float32` |
| `WHISPER_URL` | `http://localhost:8000/transcribe` | Used only when `WHISPER_MODE=http` |
| `LLM_URL` | `http://localhost:8001/v1/completions` | OpenAI-compatible completions endpoint |
| `SPEECHMIKE_VID` | `0x0911` | HID vendor ID of the dictation mic (hex or decimal) |
| `SPEECHMIKE_PID` | `0x0c1c` | HID product ID |

## Optional: GPU Acceleration

Easiest Windows path (no CUDA Toolkit install required):

```bash
pip install -e '.[gpu]'
$env:WHISPER_DEVICE="cuda"; $env:WHISPER_COMPUTE_TYPE="float16"; python -m src.main
```

If CUDA is set but the runtime DLLs aren't found, the app logs a warning and automatically falls back to CPU `int8`.

## Architecture

```
src/
├── main.py                       # Entry point & component wiring
├── core/
│   ├── orchestrator.py           # Trigger → record → STT → scrub → wedge
│   └── streaming.py              # Live partial-transcript timer (Qt)
├── ui/main_window.py             # Frameless floating PyQt6 window
├── hardware/
│   ├── recorder.py               # sounddevice capture + device enumeration
│   └── mic_listener.py           # HID polling thread for SpeechMike/PowerMic
├── ai/
│   ├── local_whisper_client.py   # faster-whisper, in-process
│   ├── whisper_client.py         # HTTP client (for microservice deployments)
│   └── llm_client.py             # OpenAI-compatible LLM for impressions
├── engine/wedge.py               # Win32 SendInput keyboard injection
├── network/pacs_query.py         # DICOM C-FIND client
├── security/
│   ├── scrubber.py               # Regex-based PHI de-identification
│   └── encryption.py             # Fernet (AES) key/encrypt/decrypt utilities
└── utils/
    ├── settings.py               # Environment-variable-backed config
    ├── config.py                 # PHI regex patterns
    └── profiler.py               # Latency measurement
```

## Testing

```bash
python -m pytest tests/
```

Unit and integration tests cover the audio pipeline, HID listener, PHI scrubber,
keyboard wedge, LLM client, PACS query (against a local DICOM SCP), and UI.
51 tests currently passing.

## Known Limitations

- **Punctuation** — dictated commands like "comma", "period", "new paragraph" are not recognized. Relies on Whisper's own punctuation inference, which is imperfect for clinical speech. A spoken-punctuation post-processor would help.
- **Streaming on long dictations** — each tick re-transcribes the full growing buffer, so `>30s` recordings see ticks skipped (UI updates slow). A VAD-based committed/partial split is the next improvement.
- **PACS not in UI** — `PACSClient.get_priors()` works but has no button wired in.
- **Local cache encryption** — `src/security/encryption.py` is implemented but not yet used by any store.
- **Windows only** — the keyboard wedge and HID paths use Win32 APIs.
