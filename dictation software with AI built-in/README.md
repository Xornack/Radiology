# Radiology Dictation Platform

> **Status: archived — no further development planned.**
> Proof-of-concept proved out; kept around as a personal-use dictation tool.
> Pull requests / issues are not being monitored. Code is provided as-is.

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
- **Field templates** — `[bracket]` placeholders auto-highlight as pills; `Ctrl+Tab` / `Ctrl+Shift+Tab` walks between them, dictation replaces the active field.
- **Local LLM impression / structuring** via Ollama (default `qwen2.5:3b`), with a six-section ACR-style report layout.
- **Resilience** — Whisper retry with backoff, fast-fail on connection-refused, PACS connection timeouts, thread-safe audio buffer, shutdown cleanup.

## Quick Start

### Option A — run the packaged .exe (no Python needed)

If you have a build of `RadiologyDictation.exe` (see [Packaging](#packaging-as-an-exe)
below), just double-click it. The first launch downloads the default Whisper
model (`base.en`, ~140 MB) into your user Hugging Face cache.

### Option B — run from source

```bash
pip install -e .
python -m src.main
```

For development (adds `pytest`, `pytest-qt`, `pyinstrument`):

```bash
pip install -e '.[dev]'
```

The first launch downloads the default Whisper model (`base.en`, ~140 MB) from Hugging Face.

Press `F4` or click **● Record** to dictate. Click `F4` again or click **■ Stop**
when done — the final transcript replaces the live partial and is typed into
the foreground app.

## STT Backends

Three backends are supported today. Pick one in the UI dropdown or via the
`STT_BACKEND` env var.

| Dropdown label | `STT_BACKEND` | Requires |
|---|---|---|
| Whisper (local, CPU) | `whisper-local-cpu` (default) | nothing extra |
| Whisper (local, GPU) | `whisper-local-gpu` | `pip install -e '.[gpu]'` |
| SenseVoice (Alibaba) | `sensevoice` | `pip install -e '.[sensevoice]'` |

Whisper CPU is the zero-setup default and works on any machine. Whisper GPU
needs the `[gpu]` extra (cuBLAS + cuDNN wheels — no CUDA Toolkit install).
If CUDA is selected but the runtime DLLs aren't found, the client logs a
warning and falls back to CPU `int8` automatically. SenseVoice (via
Alibaba's FunASR) is a multilingual alternative that tends to handle this
author's voice better than Whisper-base.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `STT_BACKEND` | `whisper-local-cpu` | `whisper-local-cpu` / `whisper-local-gpu` / `sensevoice` |
| `WHISPER_MODEL` | `base.en` | Any faster-whisper model (`tiny.en`, `small.en`, `medium.en`, `large-v3`) |
| `RADIOLOGY_MODE` | `1` | Set to `0`/`false`/`off` to disable the radiology-vocabulary correction pass |
| `LLM_URL` | `http://localhost:8001/v1/completions` | OpenAI-compatible completions endpoint (impression generation) |
| `SPEECHMIKE_VID` | `0x0554` | HID vendor ID of the dictation mic (hex or decimal) |
| `SPEECHMIKE_PID` | `0x1001` | HID product ID |

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
│   ├── _common.py                # BaseSTTClient + WAV helpers (shared)
│   ├── local_whisper_client.py   # faster-whisper, in-process
│   ├── sensevoice_stt_client.py  # Alibaba SenseVoice via funasr
│   ├── stt_registry.py           # Source of truth for available backends
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
keyboard wedge, LLM client, PACS query (against a local DICOM SCP), field
navigator, profiling harness, and UI. 393 tests currently passing.

## Profiling

Measure end-to-end pipeline latency on a fixed LibriSpeech workload:

```bash
python -m tools.profile_pipeline
```

First run downloads ~350 MB of LibriSpeech test-clean into `benchmarks/`
(gitignored). Each run writes a timestamped report under
`docs/superpowers/profiling/` with per-scenario `pyinstrument` HTML traces.

Pass `--dry-run` to swap in a fixed-latency STT stub (no SenseVoice
required); useful for smoke-testing the harness itself.

## Packaging as an .exe

A standalone Windows folder (containing a single `RadiologyDictation.exe`
plus its DLLs and data files) can be built with [Nuitka](https://nuitka.net/):

```bash
pip install -e '.[build]'
build_exe.bat
```

The resulting binary lives at `build/main.dist/RadiologyDictation.exe`. Copy
the entire `main.dist/` folder anywhere — it has no external Python dependency.

Notes:

- First Nuitka run takes 10–20 minutes and may auto-download MinGW64.
- The Whisper model is **not** bundled (it would add ~140 MB to the build and
  is downloaded on first launch into the user's Hugging Face cache anyway).
- Only the default Whisper-CPU backend is bundled. SenseVoice / MedASR pull in
  PyTorch + funasr (~2 GB) and are excluded from the .exe; install those extras
  in a source checkout if you want them.
- LLM impression generation requires a local Ollama instance at
  `http://localhost:11434`; it is not bundled.

## Known Caveats

This was a proof of concept for personal use; the rough edges below are
**not** going to be fixed.

- **Punctuation** — dictated commands like "comma", "period", "new paragraph" are not recognized. Relies on Whisper's own punctuation inference, which is imperfect for clinical speech.
- **Streaming on long dictations** — each tick re-transcribes the full growing buffer, so `>30s` recordings see ticks skipped (UI updates slow).
- **PACS not in UI** — `PACSClient.get_priors()` works but has no button wired in.
- **Local cache encryption** — `src/security/encryption.py` is implemented but not yet used by any store.
- **Windows only** — the keyboard wedge and HID paths use Win32 APIs.
