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
│   ├── app.py                  # Entry point
│   ├── core/                   # Core Orchestrator
│   ├── ui/                     # PyQt6 Window & Widgets
│   ├── hardware/               # HID (SpeechMike/PowerMic)
│   ├── engine/                 # Text Processing & Logic
│   ├── ai/                     # AI Client (FastAPI/Whisper/Llama)
│   ├── network/                # HL7 & DICOM (pynetdicom)
│   ├── security/               # Encryption & De-identification
│   └── utils/                  # Profiling, Logging, Config
├── services/                   # AI Microservices (Docker/FastAPI)
├── tests/
│   ├── unit/                   # Component-level tests
│   └── integration/            # Multi-component tests
├── docs/                       # API & Workflow Docs
├── requirements.txt
└── .env.example
```

---

## Phase 1: Foundation & Security (The "Safe" Zone)

### Task 1.1: De-identification (PHI Scrubber)
**Goal:** Create a utility that replaces PHI with placeholders before sending text to any AI model.

- [ ] **Step 1:** Create `src/security/scrubber.py`.
- [ ] **Step 2:** Write a unit test in `tests/unit/test_scrubber.py`: `test_scrub_patient_name` (Input: "Patient John Doe has a mass", Output: "Patient [NAME] has a mass").
- [ ] **Step 3:** **RED:** Run `pytest tests/unit/test_scrubber.py` and watch it fail.
- [ ] **Step 4:** **GREEN:** Implement `scrub_text` using basic Regex for names/dates.
- [ ] **Step 5:** **REFACTOR:** Optimize regex and move patterns to a separate config file.

### Task 1.2: Local Encryption
**Goal:** Encrypt any local cache or logs using AES-256.

- [ ] **Step 1:** Create `src/security/encryption.py` using `cryptography` library.
- [ ] **Step 2:** Write test `test_encrypt_decrypt_cycle`.
- [ ] **Step 3:** **RED:** Fail.
- [ ] **Step 4:** **GREEN:** Implement `encrypt(data, key)` and `decrypt(token, key)`.

---

## Phase 2: Hardware & Interface (The "Feel")

### Task 2.1: The "Stay on Top" Floating Window
**Goal:** Create a minimalist PyQt6 window that doesn't steal focus.

- [ ] **Step 1:** Create `src/ui/main_window.py`.
- [ ] **Step 2:** Inherit from `QMainWindow`, set `Qt.WindowStaysOnTopHint` and `Qt.FramelessWindowHint`.
- [ ] **Step 3:** Add a `QTextEdit` but keep it read-only for now.
- [ ] **Step 4:** **TEST:** Write a test that launches the app and asserts `window.isWindowVisible()` and `window.windowFlags() & Qt.WindowStaysOnTopHint`.

### Task 2.2: Keyboard Wedge (Injection)
**Goal:** Type text into other apps using Windows `SendInput`.

- [ ] **Step 1:** Create `src/engine/wedge.py`.
- [ ] **Step 2:** Implement `type_text(string)` using `ctypes` (SendInput).
- [ ] **Step 3:** **TEST:** Create a test that opens a notepad process, calls `type_text`, and verifies notepad content (this is an integration test).
- [ ] **Step 4:** **REFACTOR:** Ensure scan codes are used for better compatibility with medical apps.

### Task 2.3: Medical Mic Buttons (HID)
**Goal:** Map a SpeechMike button to a "Record" trigger.

- [ ] **Step 1:** Create `src/hardware/mic_listener.py` using `hidapi`.
- [ ] **Step 2:** Write a script to list HID devices and find the VendorID/ProductID for a PowerMic/SpeechMike.
- [ ] **Step 3:** **RED:** Test `get_button_state` with no mic plugged in (should handle gracefully).
- [ ] **Step 4:** **GREEN:** Implement a background thread that emits a signal when the trigger is pressed.

### Task 2.4: Audio Recording (Buffer)
**Goal:** Capture high-quality mono audio into a memory buffer while recording is active.

- [ ] **Step 1:** Create `src/hardware/recorder.py` using `sounddevice`.
- [ ] **Step 2:** Write test `test_recorder_captures_audio_stream`.
- [ ] **Step 3:** **RED:** Fail.
- [ ] **Step 4:** **GREEN:** Implement a `Recorder` class that captures 16kHz mono audio (Whisper standard).
- [ ] **Step 5:** **REFACTOR:** Ensure the recorder uses a thread-safe queue for processing.

---

## Phase 3: AI Orchestration (The "Brain")

### Task 3.1: Whisper Client
**Goal:** Send audio bytes to a local FastAPI service and get text back.

- [ ] **Step 1:** Create `src/ai/whisper_client.py`.
- [ ] **Step 2:** Write test `test_transcribe_audio` with a mock FastAPI server.
- [ ] **Step 3:** **RED:** Fail.
- [ ] **Step 4:** **GREEN:** Implement `transcribe(audio_bytes)` using `requests`.

### Task 3.2: LLM Impression Generator
**Goal:** Send "Findings" text and get a "Summary" back.

- [ ] **Step 1:** Create `src/ai/llm_client.py`.
- [ ] **Step 2:** Define a prompt template for radiology summaries.
- [ ] **Step 3:** **TEST:** Verify that the de-identification layer is called *before* the LLM client is called.

---

## Phase 4: Interoperability (The "Hospital" layer)

### Task 4.1: DICOM C-FIND for Priors
**Goal:** Query PACS for previous studies when a PatientID is entered.

- [ ] **Step 1:** Create `src/network/pacs_query.py` using `pynetdicom`.
- [ ] **Step 2:** Implement `get_priors(patient_id)`.
- [ ] **Step 3:** **TEST:** Use a local DICOM simulator (like `dcmtk`'s `dcmqrscp`) to verify queries.

---

## Phase 5: Profiling & Optimization

### Task 5.1: Latency Profiling
**Goal:** Measure time from "Button Down" to "Text on Screen".

- [ ] **Step 1:** Use `utils/profiler.py` with `cProfile` and `time.perf_counter()`.
- [ ] **Step 2:** Log every step of the pipeline (Audio Capture -> STT -> Wedge Injection).
- [ ] **Step 3:** Identify the bottleneck (likely STT inference) and optimize batching or model size.

---

## Developer Instructions

1.  **Script Size:** No Python file should exceed 150 lines. If it does, split it into smaller modules.
2.  **Testing:** Every file in `src/` must have a corresponding file in `tests/`. Use `pytest`.
3.  **Profiling:** Run `python -m cProfile src/app.py` weekly to check for performance regressions.
4.  **GUI vs Logic:** The `ui/` folder should only handle `QSignals` and `QWidgets`. All calculation, networking, and AI must happen in `engine/` or `ai/`.
5.  **Logging:** Use `loguru` or Python's `logging` for structured logs. No `print()` statements in production code.
