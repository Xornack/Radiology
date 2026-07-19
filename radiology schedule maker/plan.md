# Master Project Plan: Radiology Attending Scheduling App

## 📋 Project Overview
A high-performance WebAssembly application built in **Rust** (using **Leptos** and **Trunk**) designed specifically for radiology departments to automate and streamline attending physician scheduling.

The application operates in a **Single-Scheduler Workflow**, where an administrative chief or scheduling coordinator manages radiologist capabilities, vacation requests, and monthly shift generation without requiring individual attendings to log into a system.

---

## 🛠 Tech Stack & Tools
* **Language & Runtime**: Rust (compiled to WebAssembly)
* **Frontend Framework**: Leptos (Client-Side Rendering)
* **Build Tool & Server**: Trunk
* **Serialization & State**: `serde`, `serde_json`
* **Styling**: Vanilla CSS (Modern design system: dark mode/glassmorphism, vibrant subtle accents, responsive grid)
* **Integration**: Google Apps Script Web App (JSON endpoint for Google Sheets sync)

---

## 🎯 Key Domain Rules & Requirements
1. **Generalist vs. Subspecialist Capability**:
   * Radiologists have an `allowed_services` set. Generalists cover all ~20 daily services; subspecialists cover specific daytime services (e.g., MSK only) while remaining eligible for night/weekend general call.
2. **Multi-Service Bundling (Co-coverage)**:
   * Support for composite slots (e.g., Radiologist A covering both `Morning Checkout` + `MSK Service` on the same day).
3. **Vacation & PTO Management**:
   * Blockout dates per radiologist entered by the scheduler.
4. **Instant Constraint Solver ("Generate Best Schedule")**:
   * Uses **Simulated Annealing / Min-Conflicts** in pure Rust WASM to generate near-optimal schedules in milliseconds.
5. **Interactive Swaps & Change Highlighting**:
   * Click any slot $\rightarrow$ see eligible attendings $\rightarrow$ swap $\rightarrow$ view score delta.
   * Auto-generate Markdown/HTML email digests detailing schedule changes.
6. **Google Sheets Continuity**:
   * One-click pull/push sync to Google Sheets via an Apps Script Web App endpoint.

---

## 🗺 Implementation Phases & Milestones

### Phase 1: Project Setup & Core Data Architecture ⚙️
- [ ] Initialize Cargo project with Leptos, Trunk, and WebAssembly dependencies (`Cargo.toml`, `Trunk.toml`).
- [ ] Implement core Rust domain models:
  - `Radiologist`: ID, name, `allowed_services`, `can_cover_call`, `target_monthly_shifts`.
  - `Service`: ID, name, subspecialty requirement, bundle flags.
  - `ServiceBundle`: Defines co-coverage compatibility (e.g., Morning Checkout + MSK).
  - `VacationRequest`: Radiologist ID, start date, end date.
  - `ScheduleSlot`: Date, Service(s), assigned Radiologist ID, lock status.
  - `MonthlySchedule`: Calendar month state container.
- [ ] Write unit tests for data serialization and bundle logic.

---

### Phase 2: Scheduling & Constraint Solver Engine 🧠
- [ ] Implement **Hard Constraint Validation**:
  - PTO / Vacation blackout dates.
  - Service capability compliance (`allowed_services` & `call_eligible`).
  - Incompatible concurrent service assignments.
- [ ] Implement **Soft Cost Function (Fairness & Preference Scoring)**:
  - Even distribution penalty for weekend calls and evening checkouts.
  - Monthly shift target variance penalty $(\text{assigned} - \text{target})^2$.
  - Work pattern continuity rules (avoiding back-to-back heavy call days).
- [ ] Implement **Simulated Annealing Optimization Algorithm**:
  - Greedy initial schedule generation.
  - Stochastic shift mutation and swap iterations.
  - Performance benchmark in WASM target ($<50\text{ms}$ execution goal).

---

### Phase 3: Administrative UI & Interactive Monthly Grid 🎨
- [ ] Build core design system (`index.css`): modern typography, color palette, responsive table/grid styling, badge indicators.
- [ ] Build **Navigation Bar & Header** (Month selector, Action buttons: *Generate*, *Sync Google Sheet*, *Export Email*).
- [ ] Build **Radiologist Management Panel**:
  - Add/edit attendings, configure `allowed_services`, call eligibility, and target shifts.
- [ ] Build **Vacation & PTO Manager**:
  - Quick entry interface for adding attending leave dates.
- [ ] Build **Interactive Calendar & Monthly Grid View**:
  - Grid showing days of the month $\times$ ~20 daily service slots.
  - Visual status indicators (Unassigned, Assigned, Lock/Pinned, PTO conflict).

---

### Phase 4: Shift Swaps, Manual Fine-Tuning & Email Export 🔄
- [ ] Build **Interactive Swap Modal**:
  - Selecting an assigned slot opens a drawer/modal.
  - Displays list of eligible radiologists sorted by call availability and shift fairness score impact.
  - Instant swap button with live schedule re-scoring.
- [ ] Build **Schedule Locking Mechanism**:
  - Lock specific slots before re-running the solver so fixed assignments aren't changed.
- [ ] Build **Email Change Digest Generator**:
  - Diff view comparing baseline vs current schedule.
  - Markdown / Rich HTML generator formatted for easy copy-pasting into group emails.

---

### Phase 5: Google Sheets Continuity & Storage Persistence 📊
- [ ] Implement browser `LocalStorage` auto-save and state export/import (JSON).
- [ ] Provide **Google Apps Script Template** for the Google Sheet.
- [ ] Implement HTTP client sync in WASM (`web-sys` / `reqwest`) to push/pull schedule data to/from Google Sheets endpoint.
- [ ] End-to-end testing and optimization verification.

---

## 📅 Verification & Quality Criteria
- **Performance**: Schedule solver runs in $<100\text{ms}$ for a 30-day month with 20 daily services.
- **Correctness**: Zero hard constraint violations on generated schedules.
- **Usability**: Single-scheduler can generate, fine-tune, and export a monthly schedule in under 5 minutes.
