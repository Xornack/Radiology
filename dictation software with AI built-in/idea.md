# Potential project impetus
Our standard dictation software doesn't incorporate LLMs into the editing process. There are free, open source LLMs that could do this job.
In fact, our hospital actually provides one online that allows PHI. It's clunky to cut and paste into it, and read the output for editing.
Would be better if the software flagged potential errors and offered edits and possibly clickable rewording/rewriting in app.

# Desires
-Speed, both for the program and it's voice recognition is a must.
-Security. Deploying a program like this on a hospital computer needs to be incredibly secure.
-Modular for redability and feature upgrade potential.
-Prefer an OS neutral system, but must work in Windows.
-Has to send messages with HL7
-It PACS communication is possible, woulk like to get back the functionality of showing studies as priors if we open them in PACS.

# Questions that need answering
...


# Project Blueprint: Local AI Radiology Dictation Platform

## Executive Summary
The goal is to develop a modular, high-performance, local-first alternative to **PowerScribe**. This system will replicate the essential "tactile" radiology workflow while leveraging modern Large Language Models (LLMs) and Automatic Speech Recognition (ASR) to automate the generation of impressions and structured reports.

---

## 1. Interface & Workflow (The "PowerScribe" Feel)
To maintain clinical efficiency, the UI must stay out of the way while providing deep hardware integration.

* **Field Navigation:** Use Regex-based "jump to next field" logic (e.g., finding `[ ]` or `{{ }}`).
* **Hardware Hooks:** Map physical buttons on medical mics (SpeechMike/PowerMic) using HID listeners (`pywinusb`, `pynput`).
* **Redundancy:** Full keyboard parity (e.g., `F4` for Record, `Tab` for Next Field, `Ctrl+Enter` to Sign).
* **Overlay Mode:** An "Always on Top" transparent window using **PyQt6** that acts as a virtual keyboard wedge, typing directly into **Epic**, **Cerner**, or **PACS**.

---

## 2. The Local AI Stack (ASR & LLM)
A "best-of-breed" approach using modular, swappable containers.

### Automatic Speech Recognition (STT)
| Model | Role | Benefit |
| :--- | :--- | :--- |
| **Google MedASR** | **Primary** | Trained on 5,000+ hours of clinical audio; high medical accuracy. |
| **NVIDIA Riva** | **Performance** | Sub-150ms latency; supports "Word Boosting" for anatomy/isotopes. |
| **Distil-Whisper** | **Redundancy** | Robust fallback for noisy environments or heavy accents. |

### Natural Language Processing (The Brain)
* **Model:** **Qwen 2.5** (7B or 35B) or **Llama 3** variants.
* **Tasks:** * **Impression Generation:** Auto-summarize the "Findings" section.
    * **Structuring:** Convert "stream of consciousness" dictation into structured JSON/HL7 fields.
    * **Recommendations:** Compare findings against ACR/Fleischner guidelines for follow-up.

---

## 3. Library & Knowledge Management
* **Template Engine:** Maintain a library of **Structured Reports** and **Autotext**.
* **Standardization:** Base the core library on **RSNA RadReport** templates to ensure clinical validity and interoperability.
* **AI Maintenance:** Use the local LLM to tag, categorize, and update templates based on new peer-reviewed research.

---

## 4. Technical Architecture
* **Interoperability:** Use **HL7apy** and **pydicom** for messaging with hospital EHRs and PACS vendors.
* **Modularity:** Build as a **Microservice Architecture** (using **FastAPI** or **Docker**). This allows you to upgrade the ASR model or the LLM independently without touching the core UI.
* **Hardware Requirements:** * **GPU:** RTX 4090 or A6000 (essential for local LLM/ASR inference).
    * **RAM:** 64GB+ (to keep multiple models resident in VRAM/System RAM).

---

## 5. Intellectual Property (IP) Strategy
* **Functional Parity:** Replicating industry-standard features (drop-downs, fill-in fields) is generally safe, as these are functional UI patterns.
* **Safe Harbors:** * Avoid proprietary names (use "Templates" instead of "Autotext").
    * Avoid copying the exact "Trade Dress" (visual look) of Nuance software.
    * Consult an IP attorney regarding specific workflow patents.

# PyQt6 PowerScribe Functionality Mapping

## 1. The Floating Dictation Box
* **PyQt6 Component:** `Qt::WindowStaysOnTopHint` and `Qt::FramelessWindowHint`
* **Implementation:** Use these window flags to create a borderless, transparent overlay that hovers over PACS or EHRs (Epic/Cerner) without losing focus.

## 2. Rich Text & Report Body
* **PyQt6 Component:** `QTextEdit`
* **Implementation:** This is the core widget for your text editor. It natively supports HTML/Rich Text, allowing for standard medical tables, bolding, and structured formatting.

## 3. Labeled Box Fill-in Fields (e.g., `[Diagnosis]`)
* **PyQt6 Component:** `QSyntaxHighlighter` + `QTextCharFormat`
* **Implementation:** Write a custom syntax highlighter using a regular expression (like `\[.*?\]`). The `QTextCharFormat` automatically changes the background and font color of anything inside brackets, visually mimicking PowerScribe fields.

## 4. "Next Field" Navigation & Overwriting
* **PyQt6 Component:** `QTextCursor`
* **Implementation:** When triggered by a hardware button (via `hidapi`) or voice command, use `QTextCursor` to search the document for the next regex match. The cursor highlights the entire `[ ]` block so the next dictated phrase automatically overwrites it.

## 5. Drop-down "Pick Lists"
* **PyQt6 Component:** `QMenu`
* **Implementation:** Capture a right-click or mic button event when a field is highlighted. Spawn a `QMenu` at the exact coordinates of the `QTextCursor` containing pre-defined field options (e.g., Mild, Moderate, Severe). Selecting an option replaces the highlighted text.

## 6. Voice Commands & Auto-Text Interception
* **PyQt6 Component:** `undo()` method and `insertHtml()` / `insertPlainText()`
* **Implementation:** Route the STT output through a Python interceptor before it hits the UI. 
    * If the text matches "scratch that," call `QTextEdit.undo()`.
    * If it matches an Autotext trigger (e.g., "Insert Normal Chest"), fetch the HTML template from a local database and insert it at the current `QTextCursor` position using `insertHtml()`.

