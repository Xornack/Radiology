# Project Plan: Local AI Radiology Dictation Platform

## Objective
Build a modular, secure, and high-performance radiology dictation platform that integrates local AI (ASR/LLM) and interacts with hospital systems (PACS/EHR) via HL7/DICOM.

## Core Mandates
1.  **Security First:** No PHI leaves the local machine.
2.  **Performance:** Low latency for dictation (sub-200ms).
3.  **Modularity:** Small, focused Python scripts (<150 lines).
4.  **Strict TDD Workflow:** Red -> Green -> Refactor for every feature. If a test is sound (correctly defines the requirement), **DO NOT** edit the test to pass; only edit the implementation scripts.
5.  **Separation of Concerns:** GUI (PyQt6) and Logic (Engine) must never be tightly coupled.

---

## Folder Structure

```text
/radiology-dictation/
├── src/
│   ├── main.py                 # Entry point
│   ├── core/                   # Core Orchestrator & live streaming
│   ├── ui/                     # PyQt6 Window & Widgets
│   ├── hardware/               # HID (SpeechMike/PowerMic) & audio capture
│   ├── engine/                 # Keyboard wedge (Win32 SendInput)
│   ├── ai/                     # Whisper (local & HTTP) + LLM client
│   ├── network/                # DICOM (pynetdicom) — HL7 TBD
│   ├── security/               # Encryption & De-identification
│   └── utils/                  # Profiling, Settings, PHI patterns
├── services/                   # AI Microservices (Docker/FastAPI) — placeholder
├── tests/
│   ├── unit/                   # Component-level tests
│   └── integration/            # Multi-component tests
├── docs/                       # API & Workflow Docs — placeholder
└── pyproject.toml              # Runtime & dev dependencies
```

---

## Phase 1: Foundation & Security (The "Safe" Zone)

### Task 1.1: De-identification (PHI Scrubber)
**Goal:** Create a utility that replaces PHI with placeholders before sending text to any AI model.

- [x] **Step 1:** Create `src/security/scrubber.py`.
- [x] **Step 2:** Write a unit test in `tests/unit/test_scrubber.py`: `test_scrub_patient_name` (Input: "Patient John Doe has a mass", Output: "Patient [NAME] has a mass").
- [x] **Step 3:** **RED:** Run `pytest tests/unit/test_scrubber.py` and watch it fail.
- [x] **Step 4:** **GREEN:** Implement `scrub_text` using basic Regex for names/dates.
- [x] **Step 5:** **REFACTOR:** Optimize regex and move patterns to a separate config file.

### Task 1.2: Local Encryption
**Goal:** Encrypt any local cache or logs using AES-256.

- [x] **Step 1:** Create `src/security/encryption.py` using `cryptography` library.
- [x] **Step 2:** Write test `test_encrypt_decrypt_cycle`.
- [x] **Step 3:** **RED:** Fail.
- [x] **Step 4:** **GREEN:** Implement `encrypt(data, key)` and `decrypt(token, key)`.

---

## Phase 2: Hardware & Interface (The "Feel")

### Task 2.1: The "Stay on Top" Floating Window
**Goal:** Create a minimalist PyQt6 window that doesn't steal focus.

- [x] **Step 1:** Create `src/ui/main_window.py`.
- [x] **Step 2:** Inherit from `QMainWindow`, set `Qt.WindowStaysOnTopHint` and `Qt.FramelessWindowHint`.
- [x] **Step 3:** Add a `QTextEdit` but keep it read-only for now.
- [x] **Step 4:** **TEST:** Write a test that launches the app and asserts `window.isWindowVisible()` and `window.windowFlags() & Qt.WindowStaysOnTopHint`.

### Task 2.2: Keyboard Wedge (Injection)
**Goal:** Type text into other apps using Windows `SendInput`.

- [x] **Step 1:** Create `src/engine/wedge.py`.
- [x] **Step 2:** Implement `type_text(string)` using `ctypes` (SendInput).
- [x] **Step 3:** **TEST:** Create a test that opens a notepad process, calls `type_text`, and verifies notepad content (this is an integration test).
- [x] **Step 4:** **REFACTOR:** Ensure scan codes are used for better compatibility with medical apps.

### Task 2.3: Medical Mic Buttons (HID)
**Goal:** Map a SpeechMike button to a "Record" trigger.

- [x] **Step 1:** Create `src/hardware/mic_listener.py` using `hidapi`.
- [x] **Step 2:** Write a script to list HID devices and find the VendorID/ProductID for a PowerMic/SpeechMike.
- [x] **Step 3:** **RED:** Test `get_button_state` with no mic plugged in (should handle gracefully).
- [x] **Step 4:** **GREEN:** Implement a background thread that emits a signal when the trigger is pressed.

### Task 2.4: Audio Recording (Buffer)
**Goal:** Capture high-quality mono audio into a memory buffer while recording is active.

- [x] **Step 1:** Create `src/hardware/recorder.py` using `sounddevice`.
- [x] **Step 2:** Write test `test_recorder_captures_audio_stream`.
- [x] **Step 3:** **RED:** Fail.
- [x] **Step 4:** **GREEN:** Implement a `Recorder` class that captures 16kHz mono audio (Whisper standard).
- [x] **Step 5:** **REFACTOR:** Ensure the recorder uses a thread-safe queue for processing.

---

## Phase 3: AI Orchestration (The "Brain")

### Task 3.1: Whisper Client
**Goal:** Send audio bytes to a local FastAPI service and get text back.

- [x] **Step 1:** Create `src/ai/whisper_client.py`.
- [x] **Step 2:** Write test `test_transcribe_audio` with a mock FastAPI server.
- [x] **Step 3:** **RED:** Fail.
- [x] **Step 4:** **GREEN:** Implement `transcribe(audio_bytes)` using `requests`.

### Task 3.2: LLM Impression Generator
**Goal:** Send "Findings" text and get a "Summary" back.

- [x] **Step 1:** Create `src/ai/llm_client.py`.
- [x] **Step 2:** Define a prompt template for radiology summaries.
- [x] **Step 3:** **TEST:** Verify that the de-identification layer is called *before* the LLM client is called.
- [x] **Step 4:** Wire `LLMClient` into `DictationOrchestrator` via `generate_impression(findings)` method.

---

## Phase 4: Interoperability (The "Hospital" layer)

### Task 4.1: DICOM C-FIND for Priors
**Goal:** Query PACS for previous studies when a PatientID is entered.

- [x] **Step 1:** Create `src/network/pacs_query.py` using `pynetdicom`.
- [x] **Step 2:** Implement `get_priors(patient_id)`.
- [x] **Step 3:** **TEST:** Use a local DICOM simulator (like `dcmtk`'s `dcmqrscp`) to verify queries.

---

## Phase 5: Profiling & Optimization

### Task 5.1: Latency Profiling
**Goal:** Measure time from "Button Down" to "Text on Screen".

- [x] **Step 1:** Use `utils/profiler.py` with `cProfile` and `time.perf_counter()`.
- [x] **Step 2:** Log every step of the pipeline (Audio Capture -> STT -> Wedge Injection).
- [ ] **Step 3:** Identify the bottleneck (likely STT inference) and optimize batching or model size.

---

## Phase 6: Hardening & Bug Fixes

### Task 6.1: Audio Pipeline Type Safety ✅
**Fixed:** `AudioRecorder.get_wav_bytes()` converts the float32 numpy buffer to
16-bit mono WAV bytes. The orchestrator now calls `get_wav_bytes()` instead of
`get_buffer()`, ensuring Whisper receives correctly formatted audio data.

### Task 6.2: Keyboard Wedge — Full Character Set ✅
**Fixed:** `type_text()` now handles uppercase letters, Shift-modified symbols
(`!@#$%^&*()_+{}|:"<>?`), and direct symbols (`;'[]/\=`).
The erroneous `.lower()` call was removed to preserve case.

### Task 6.3: Silent Exception Handling ✅
**Fixed:** All bare `except:` blocks in `whisper_client.py`, `llm_client.py`,
`recorder.py`, and `mic_listener.py` now log errors/warnings via `loguru`.

### Task 6.4: LLM Client Integration ✅
**Fixed:** `DictationOrchestrator` accepts an optional `llm_client` parameter.
`generate_impression(findings)` method added. `main.py` instantiates and wires
`LLMClient` so the impression workflow is fully operational.

### Task 6.5: HID Background Polling Thread ✅
**Fixed:** `MicListener.start()` spawns a daemon polling thread (`_poll_loop`).
Button state-change detection fires `on_trigger` on press *and* release.
`stop()` gracefully terminates the thread and closes the device.

### Task 6.6: Configuration & Settings ✅
**Fixed:** `src/utils/settings.py` added. All hardcoded URLs and HID IDs moved to
environment variables (`WHISPER_URL`, `LLM_URL`, `SPEECHMIKE_VID`, `SPEECHMIKE_PID`)
with safe defaults. `main.py` uses `settings` throughout.

### Task 6.7: PHI Pattern Expansion ✅
**Fixed:** `src/utils/config.py` now scrubs SSNs (`[SSN]`), US phone numbers
(`[PHONE]`), email addresses (`[EMAIL]`), and month-spelled dates, in addition
to the original patterns.

### Task 6.8: Audio Recorder Hardening ✅
**Fixed:** Audio stream status codes are logged as warnings (not silently discarded).
`start()` closes any existing stream before opening a new one (resource leak fix).
Stream creation errors are logged then re-raised for visibility.

### Task 6.9: pyproject.toml Dependencies ✅
**Fixed:** `pyproject.toml` now declares all runtime dependencies, matching
`requirements.txt`. Dev/test dependencies isolated under `[project.optional-dependencies]`.

---

## Phase 7: Live Transcription, UX, and Second Hardening Pass

### Task 7.1: Local Whisper (in-process STT) ✅
**Added:** `src/ai/local_whisper_client.py` runs `faster-whisper` in-process —
no microservice required. Drop-in replacement for `WhisperClient` (same
`transcribe(bytes) -> str` interface). Chosen by `WHISPER_MODE=local` (default).
Model is lazy-loaded and can be preloaded via `warm()` on startup.

### Task 7.2: STT Defaults & CUDA Fallback ✅
**Added:** Default `WHISPER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8` for
zero-setup operation on any machine. If `WHISPER_DEVICE=cuda` is set but
cuBLAS/cuDNN DLLs are missing at inference time, the client automatically
falls back to CPU + int8 with a warning (no silent empty transcripts).

### Task 7.3: Streaming Partial Transcription ✅
**Added:** `src/core/streaming.py` → `StreamingTranscriber`. A `QTimer` ticks
every 1500ms during recording, dispatches transcription to a worker thread,
and emits `partial_ready` to the Qt main thread. UI shows partials in italic
gray; on Stop, the authoritative final transcribe commits in normal color.
Ticks are skipped while a previous transcribe is still in flight (no queue buildup).

### Task 7.4: UI Controls — Record / Stop / Clear ✅
**Added:** Three buttons in a new action bar, sharing a single
`handle_trigger(bool)` path with the HID mic and F4 shortcut. Buttons reflect
recording state (Record disabled while recording, Stop enabled, and vice versa).

### Task 7.5: UI — Microphone Picker ✅
**Added:** `hardware/recorder.list_input_devices()` enumerates all input-capable
devices with host API labels. `MainWindow.populate_microphones()` fills a
`QComboBox` with a "System default" entry first. Selection updates
`AudioRecorder.device`. Combo is disabled while recording to prevent mid-stream
swaps.

### Task 7.6: UI — Generate Impression Button ✅
**Wired:** `MainWindow.impression_btn` now calls `orchestrator.generate_impression()`
with the current transcript text. Result is appended under an `IMPRESSION:`
label. Button disables while generating.

### Task 7.7: Keyboard Fallback (F4) ✅
**Added:** `QShortcut` on F4 always registered, using
`Qt.ShortcutContext.ApplicationShortcut`. Functions with or without an HID mic
connected. Shares `recording_state` with the mic and buttons so all three
sources stay in sync.

### Task 7.8: Shutdown Cleanup ✅
**Added:** `app.aboutToQuit.connect(on_shutdown)` calls `mic.stop()` and
`recorder.stop()` on exit. Close button (`×`) now quits the application via
`QApplication.quit()` rather than just hiding the window.

### Task 7.9: PHI Pattern Broadening ✅
**Fixed:** Name scrubbing no longer requires the literal "Patient" prefix.
Added: ALL-CAPS names, hyphenated and accented names (`Mary-Jane`, `José`),
single-name patients, `Mr./Mrs./Ms./Dr./Prof.` titled names, and `Name:` labels.

### Task 7.10: Keyboard Wedge Unicode Fallback ✅
**Fixed:** `wedge.py` previously dropped any character missing from its scan-code
map (em-dash, curly quotes, `°`, `±`, `µ`, tab). Now falls back to
`KEYEVENTF_UNICODE` with surrogate-pair support. No character is silently lost.

### Task 7.11: PACS Resource Leak & Timeouts ✅
**Fixed:** `PACSClient.get_priors()` now wraps the association in `try/finally`
so `assoc.release()` runs even on exceptions. Added `network_timeout` and
`acse_timeout` (10 s each) so a dead PACS can't hang the UI. Failed associations
are logged.

### Task 7.12: Audio Buffer Thread Safety ✅
**Fixed:** `AudioRecorder._buffer` is now guarded by a `threading.Lock` on both
the callback (`extend`) and the readers (`get_buffer`, `get_wav_bytes`).
Clipping during float→int16 conversion now logs a warning instead of silently
distorting audio.

### Task 7.13: Whisper Retry & Fast-Fail ✅
**Fixed:** `WhisperClient.transcribe()` retries with exponential backoff on 5xx
and timeout. Catches `requests.exceptions.ConnectionError` first and returns
immediately (no retry loop when the port is closed).

### Task 7.14: HID Listener Busy-Loop Mitigation ✅
**Fixed:** `MicListener._poll_loop` sleeps 1 ms when a poll returns no data,
preventing a CPU-pinning tight loop when the device has nothing to report.

### Task 7.15: Settings Safe Parsing & Orchestrator Error Wrapping ✅
**Fixed:** `Settings._safe_int()` catches malformed `SPEECHMIKE_VID`/`PID`
environment variables and falls back to defaults (no startup crash).
`DictationOrchestrator` wraps `wedge.type_text()` in try/except so a Win32
failure cannot crash the Qt trigger handler.

---

## Phase 8: Dictation UX

### Task 8.1: Spoken Punctuation Post-Processor ✅
**Added:** `src/engine/punctuation.py` replaces Whisper's inferred punctuation
with user-dictated tokens (PowerScribe-style). Handles `period`, `comma`,
`question mark`, `exclamation point`, `colon`, `semicolon`, `new paragraph`,
`new line`, parentheses, quotes, `hyphen`, and `dash`. Context-aware colon
disambiguation: preserves `colon` as anatomy when neighbored by words like
`distal`, `sigmoid`, `cancer`, `polyp`. Auto-capitalizes document start and
first word after `.`, `?`, `!`, or a paragraph break. Called after PHI scrub
in the orchestrator and before `partial_ready.emit` in the streaming
transcriber so the UI preview matches the final output.

---

## Known Issues & Next Steps

- **Streaming on long dictations** — each tick re-transcribes the whole growing
  buffer, so recordings > ~30 s see ticks skipped. A VAD-based
  committed/in-flight split (whisper_streaming style) would give stable earlier
  text and faster updates. *[Deferred]*
- **PACS not in UI** — `PACSClient.get_priors()` works but has no button wired.
- **Local cache encryption not wired** — `security/encryption.py` is
  implemented but no cache exists to consume it.
- **Profiler export (Phase 5 Step 3)** — latencies are logged per-run but not
  persisted for weekly bottleneck review.

---

## Developer Instructions

1.  **Script Size:** No Python file should exceed 150 lines. If it does, split it into smaller modules.
2.  **Testing:** Every file in `src/` must have a corresponding file in `tests/`. Use `pytest`.
3.  **Profiling:** Run `python -m cProfile -m src.main` weekly to check for performance regressions.
4.  **GUI vs Logic:** The `ui/` folder should only handle `QSignals` and `QWidgets`. All calculation, networking, and AI must happen in `engine/` or `ai/`.
5.  **Logging:** Use `loguru` or Python's `logging` for structured logs. No `print()` statements in production code.
