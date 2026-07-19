# Hot Lab & Gamma Camera QI/QC Training Platform — Project Plan

*Drafted 2026-07-15; updated 2026-07-18 against NMSS-ISG-03 and the verified source inventory in `training_sources.md`. Scoping decisions: custom web app; hot lab + camera QC content first, extensible; cheap personally-run cloud hosting; admin-created accounts with email login. The 80-hour didactic coursework is delivered by separate software — this platform is the lab complement (hot lab + camera QC instruction and pre-lab prep).*

---

## 1. What we're building

A custom web platform ("Hot Lab Sim") that delivers interactive video training on hot lab operations and gamma camera QI/QC for radiology residents, with:

- **Interactive video lessons** — YouTube-hosted videos that pause at cue points and require a correct answer to continue.
- **Per-resident tracking** — an admin dashboard showing exactly where each resident is, with timestamped, per-question audit logs.
- **Quizzes/exams** — standalone module exams with scoring and pass thresholds.
- **Completion certificates** — PDF with unique ID and verification URL, kept on file for AU-track / ACR documentation.
- **Embedded physics demos** — the existing Rust/WASM manim-style demo embedded via iframe.
- **Regulatory paper trail** — hour accounting mapped to 10 CFR 35.290 topics, exportable records — including a printable syllabus + per-module learning objectives, since NRC may audit an online training entity's course outline, test, and completion-verification mechanism (NMSS-ISG-03) — and (later) preceptor sign-off worksheets feeding NRC Form 313A(AUD).

Quality bar: meet or exceed Core Physics Review's NRC80 in polish and rigor, at zero cost to the residency.

## 2. Key research findings that shape the design

### Regulatory (what the course must document)

- **10 CFR 35.290** (imaging & localization AU pathway): 700 total hours of training & experience, **including** a minimum of **80 hours of classroom and laboratory training** in five topics: (1) radiation physics & instrumentation, (2) radiation protection, (3) mathematics of radioactivity, (4) chemistry of byproduct material, (5) radiation biology.
- **Work experience elements** (35.290(c)(1)(ii)(A)–(G)) map directly onto hot lab activities: package receipt & surveys; dose calibrator QC & survey meter checks; calculating/measuring/preparing dosages; administrative controls to prevent medical events; spill containment/decon; administering dosages; generator elution + eluate purity testing (Mo-99 breakthrough per 10 CFR 35.204: ≤0.15 kBq Mo-99 per MBq Tc-99m, measured in each eluate) + kit preparation.
- **Critical framing:** an on-screen simulator **cannot itself satisfy the supervised work-experience elements** (those require hands-on handling under an AU), but it legitimately delivers **classroom/laboratory hours** toward the 80 and serves as pre-lab preparation — exactly the NRC80 model (pre-lab video → hands-on in the program's own hot lab → data analysis worksheet, AU-signed). With the 80 didactic hours handled by external software, this platform's role narrows to the lab side: pre-lab preparation for the seven 35.290(c)(1)(ii) work-experience elements plus camera QC — any hours it credits are still classroom/laboratory-type hours.
- **Documentation:** completion feeds **NRC Form 313A(AUD)** (diagnostic AU form) with preceptor attestation — signable by the program director on faculty consensus if at least one faculty member is a qualifying AU. NRC 10 CFR 35.2310 record requirements are simple: topics, date, attendee names, instructor names, retained 3 years; electronic records explicitly acceptable. **No SCORM/xAPI required** — a plain database + audit log + PDF certificate is fully defensible.
- **NMSS-ISG-03 (Apr 2025, `ML25051A034.pdf` in repo):** NRC broadly interprets classroom/laboratory training to include **online training**; for online programs NRC **may contact the training entity** to review course outline, test, and completion-verification mechanism — hence the syllabus/objectives export feature. Credited hours = time engaged in the learning activity, and an hour counts in only one category (never both classroom/lab and work experience). Preceptor attestation is required for alternate-pathway AUs (program director may serve as preceptor); board-certification-pathway AUs need none. Current documentation guide: NUREG-1556 Vol. 9 **Rev. 3** (2019), Appendix D.
- **QC content ground truth** (ACR NM accreditation + NUREG-1556 Vol. 9 + ANSI practice):
  - Dose calibrator: constancy daily, linearity quarterly, accuracy annually, geometry at installation (±10%, geometry ±5–10%).
  - Survey meters: calibrated annually/after repair (10 CFR 35.61); daily battery/check-source before use.
  - Surveys: end-of-day exposure-rate surveys of use areas; weekly wipe tests; package receipt surveys per 10 CFR 20.1906; sealed-source leak tests semiannually.
  - Gamma camera (ACR): uniformity flood **each day of use**; bar phantom resolution/linearity **monthly** (weekly for older analog); SPECT center-of-rotation **monthly**; ACR/Jaszczak phantom **semiannually**; SPECT/CT daily CT QC; annual physics survey by a qualified medical physicist.
- **Free source material to build on:** IAEA QC Atlas for Scintillation Camera Systems (free PDF library of normal/abnormal flood images — ideal for "spot the artifact" questions), IAEA NMQC ImageJ plugins (reference algorithms for uniformity/COR analysis), NUREG-1556 Vol. 9 model procedures (mirror verbatim in worksheets), StatPearls NM QA chapter.
- **Market gap:** no free interactive hot-lab/gamma-camera simulator exists. Paid market = ASNC/SNMMI 80-hour didactic video course, and NRC80 guided physical labs. This project sits in the open niche between them.

### Technical (how to build it)

- **Stack:** Next.js (16.x) + Postgres. No off-the-shelf product bundles all requirements cheaply — LearnWorlds does but costs ~$3,000/yr; MoodleCloud ($170/yr) is the fallback if the custom build stalls.
- **Auth:** **Better Auth** (MIT-licensed, users live in our own Postgres, first-class magic-link + invite flows). Auth.js/NextAuth v5 is effectively end-of-life for new projects. Email via **Resend** free tier.
- **Database:** **Neon** free Postgres tier (0.5 GB, no expiry) via **Drizzle ORM**.
- **Hosting:** **Railway (~$5/mo)** or Fly.io (~$3/mo). (Vercel Hobby is $0 but its non-commercial clause is a gray zone for institutional training; Vercel Pro $20/mo is fine if preferred.) Realistic total cost: **$5–10/mo**.
- **Video player:** raw **YouTube IFrame Player API** (skip wrapper libraries). Cue points by polling `getCurrentTime()` every 250 ms. Anti-seek via `controls: 0` + `disablekb: 1` + our own play/pause UI (cleaner than seek-revert polling).
  - **ToS compliance:** render questions **beside/below the paused player**, not overlaying it (YouTube's Required Minimum Functionality terms prohibit obscuring overlays; Edpuzzle-style overlays are tolerated but gray-zone).
  - **Must-set embed details:** `playsinline: 1` (mandatory on iOS or fullscreen kills our logic), `referrerpolicy="strict-origin-when-cross-origin"` (prevents the Nov 2025 "Error 153" breakage), re-check time on `visibilitychange` (background-tab timer throttling can blow past cue points).
  - **Ads:** embeds show ads iff the source channel is monetized; we can't suppress them. Self-recorded videos go on our own **non-monetized channel, unlisted, embedding allowed** → ad-free. The Julie Bolin channel videos may show ads we can't control — re-upload with permission if that becomes a problem.
  - Unlisted = obscurity, not access control (video IDs visible in page HTML) — acceptable for training content.
- **Certificates:** **pdf-lib** stamping name/date/score/cert-ID onto a designed background PDF; store the exact generated PDF server-side; cert ID resolves at a public `/verify/[id]` URL.
- **Rust/WASM demos:** build to static output (Trunk/wasm-pack), serve from `/public/`, embed via iframe. Zero bundler config (importing WASM directly into Turbopack has real friction — avoid).
- **Effort estimate:** ~2–4 part-time weeks (~70–130 h) for v1 with AI assistance. Highest-risk piece: the interactive player on iOS Safari.
- **Optional shortcut (not chosen for v1):** Lumi + h5p-standalone as a drop-in interactive-video engine capturing xAPI events — saves player work but clunkier authoring and fragile YouTube support. Keep as a fallback if the custom player fights us.

## 3. Course & content structure

Content model is **Course → Module → Lesson → Activity**, deliberately extensible so future modules can grow toward the full 80-hour curriculum.

### v1 modules (hot lab + gamma camera QC)

| # | Module | Maps to | Content sources (verified video links in `training_sources.md` §2) |
|---|--------|---------|-----------------|
| 1 | Radioactivity math & units — short pre-lab refresher (full didactics live in the external 80-h course) | 35.290(c)(1)(i)(C) | Self-made video + Rust/WASM decay demo; embedded calculation questions |
| 2 | Package receipt, surveys & wipe tests | (c)(1)(ii)(A); 20.1906 | **Self-filmed** (no third-party found; Bolin channel has no hot-lab QC content); NUREG-1556 procedures; Reg Guide 8.23 |
| 3 | Dose calibrator QC (constancy, accuracy, linearity, geometry) | (c)(1)(ii)(B); 35.60 | IowaRadOnc hands-on lab + Kamal didactic (verified); physicist linearity footage later; data-analysis worksheet (enter readings → auto-check ±10%) |
| 4 | Survey meters & area surveys | (c)(1)(ii)(B); 35.61 | **Self-filmed** (no third-party found) + "which meter for which task" questions |
| 5 | Generator elution, Mo-99 breakthrough, kit prep | (c)(1)(ii)(G); 35.204 | Bolin UltraTag kit; IowaRadOnc kit prep; Currie cold-kit 1–2; Kamal generator QC; NM Solutions moly assay (all verified); self-filmed elution; breakthrough calculation activity (limit: 0.15 kBq/MBq) |
| 6 | Dose calculation, preparation & administration; written directives / medical-event prevention | (c)(1)(ii)(C),(D),(F) | Bolin venous access (verified); self-filmed dose drawing/assay + scenario questions |
| 7 | Spills & decontamination | (c)(1)(ii)(E) | **Self-filmed** scenarios (minor vs major spill; no third-party found) |
| 8 | Waste: decay-in-storage & disposal | 35.92 | **Self-filmed** (no third-party found) |
| 9 | Gamma camera daily QC: uniformity floods | ACR NM accreditation | Olympic Health Physics daily flood (verified) + IAEA QC Atlas image bank: "normal or artifact?" image questions |
| 10 | Camera resolution/linearity, COR, SPECT phantom, SPECT/CT QC | ACR | IAEA bar-phantom videos, TechNucMed COR + Jaszczak, Olympic Jaszczak 3-part (all verified); physicist footage later + atlas images |
| 11 | Module exams + final exam | — | Question bank, pass threshold (e.g., 80%), limited attempts logged |

Each module carries a **credited hour value** (like NRC80's accounting) and a **regulatory citation tag** shown on the module page and printed on records — this per-citation mapping is a headline feature that matches NRC80's compliance framing.

### Differentiators vs NRC80
- Gamma camera QC in depth (NRC80 gives it a quarter of one lab).
- Interactive image-interpretation questions from the IAEA atlas (spot the PMT failure, the cracked crystal, the COR error).
- Real-time physics demos (Rust/WASM).
- No shipped physical materials required; free to the program.

### v2 content (later)
- **Preceptor worksheet workflow**: printable/digital lab worksheets for the hands-on portion residents complete in the actual hot lab, signed off in-app by the AU/preceptor — this is what turns the platform into a full 313A(AUD) evidence pipeline.
- Additional didactic modules toward the full 80 hours (radiation biology, radiation protection, instrumentation physics).

## 4. Architecture

```
Next.js 16 (App Router, TypeScript)
├─ Better Auth        — invite-only accounts, email magic link + password
├─ Neon Postgres      — via Drizzle ORM
├─ Resend             — invite + magic-link emails
├─ YouTube IFrame API — custom interactive player component
├─ pdf-lib            — certificate generation (stored server-side)
├─ /public/demos/     — Rust/WASM builds, iframed into lessons
└─ Railway            — hosting (~$5/mo)
```

### Data model (core tables)

- `users` — id, name, email, role (`resident` | `admin`), invited_by, created_at (Better Auth tables + role/profile extension)
- `courses` / `modules` / `lessons` — ordering, credited_minutes, regulatory_citation, published flag, **version**
- `activities` — type (`video`, `quiz`, `demo`, `worksheet`), config JSON
- `video_cues` — activity_id, time_seconds, question_id
- `questions` — stem, type (MCQ, multi-select, numeric-with-tolerance, image-hotspot), options, correct answer, explanation, image ref, **version**
- `attempts` — user_id, question_id, question_version, response, correct, timestamp (append-only; never updated)
- `lesson_progress` — user_id, lesson_id, watched_seconds, completed_at
- `exam_sessions` — user_id, module_id, score, passed, started/finished timestamps
- `certificates` — id (unique, unguessable), user_id, course_id, course_version, issued_at, pdf blob/path, revoked flag
- `audit_log` — append-only event stream (login, lesson start/complete, exam submit, cert issue) with timestamps

Content versioning + append-only attempts + stored PDFs = the defensible record NRC/TJC/ACGME actually care about (who, what, when, instructor, evidence; ≥3-year retention — we'll keep everything indefinitely, with periodic CSV/PDF export as backup).

### Interactive player component (the hard part)

- Load IFrame API; `controls: 0`, `disablekb: 1`, `playsinline: 1`, `rel: 0`, host `youtube-nocookie.com`, `referrerpolicy="strict-origin-when-cross-origin"`.
- Custom control bar: play/pause, volume, captions toggle, progress bar that only allows seeking **backward** (or into already-watched territory).
- Poll `getCurrentTime()` @250 ms; on cue: `pauseVideo()`, render question **below the player** (ToS-safe), disable play until answered correctly; wrong answer → optional "rewatch from segment start" jump (adaptivity).
- `visibilitychange` handler: on tab return, if a cue was skipped while throttled, seek back to it.
- Track cumulative watched seconds server-side (heartbeat every ~15 s) → lesson completion requires ≥ threshold watched + all cues answered.
- Test matrix: Chrome/Edge/Firefox desktop, iOS Safari, Android Chrome. iOS is the known risk — verify pause/question/resume early, before building everything on top.

### Admin dashboard

- Roster with invite flow (admin creates account → resident gets email).
- Matrix view: residents × modules, cell = not started / in progress (%) / completed (date) / exam score.
- Drill-down per resident: full timeline, per-question responses, hours credited by 35.290 topic, certificate status.
- Exports: CSV of completion records; per-resident PDF training summary (topics, dates, hours, instructor) formatted to transcribe onto Form 313A(AUD); printable course syllabus + per-module learning objectives (the package NRC would ask for when auditing an online training entity).

### Certificates

- Issued on course completion (all modules + final exam passed).
- PDF: resident name, course title + version, credited hours by topic, completion date, program/instructor name (you, as course director), unique certificate ID, QR/URL to `/verify/[id]`.
- `/verify/[id]` publicly shows: valid/revoked, name, course, date — nothing else.

## 5. Build phases

### Phase 0 — Skeleton & risk retirement (~2–4 days)
1. Scaffold Next.js + Drizzle + Neon + Better Auth (invite-only, magic link); deploy to Railway from day one.
2. **Spike the interactive player** with one real video and two hardcoded cue questions; test on iOS Safari immediately. *Go/no-go: if the player fights us on iOS, fall back to h5p-standalone as the engine.*

### Phase 1 — Core platform (~1–2 weeks part-time)
3. Content schema + admin CRUD (courses/modules/lessons/questions/cues) — simple forms, no fancy editor.
4. Player wired to real cue data; attempts + progress + audit log persisted.
5. Quiz/exam engine (question bank, randomized order, pass threshold, attempt limits).
6. Admin dashboard matrix + resident drill-down.

### Phase 2 — Records & polish (~1 week part-time)
7. Certificate generation + verification URL.
8. CSV export + 313A(AUD)-oriented per-resident training summary PDF.
9. Rust/WASM demo embedded in the math module; UI polish pass (this must *look* better than a Moodle course).

### Phase 3 — Content build-out (ongoing, parallel with filming)
10. Author modules 1–11: write cue questions per video, build the IAEA-atlas image question bank, breakthrough/linearity calculation worksheets.
11. Pilot with 1–2 residents; fix friction; then roll out to the cohort.

### Phase 4 — v2
12. Preceptor sign-off worksheets (digital signature + stored record) for the hands-on work-experience elements.
13. Additional didactic modules toward the full 80 hours; multi-program support if other residencies want in.

## 6. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| YouTube embed breakage (e.g., Error 153-class changes) | `referrerpolicy` set; player isolated in one component; fallback plan: self-host MP4s (Cloudflare R2 free egress) — schema stores a generic `video_source` so swapping is cheap |
| Ads on third-party videos | Bolin videos (2 in v1 scope): re-upload to our own non-monetized unlisted channel (permission already granted). Other third-party QC videos (Iowa, Olympic, TechNucMed, IAEA…): no re-upload rights — accept possible ads, or replace with self-filmed versions over time |
| iOS Safari player bugs | Spike in Phase 0 before building on top; h5p-standalone fallback |
| Physicist linearity/COR videos hard to schedule | Largely retired: modules 3 & 10 launch with verified third-party videos (IowaRadOnc dose-cal lab, TechNucMed COR, Olympic flood/Jaszczak series) + atlas images; physicist footage upgrades lessons when filmed — content model supports version bump |
| Scope creep toward full 80-hour course | v1 scope is frozen to modules 1–11; extensibility is in the schema, not the roadmap |
| Solo bus factor / data loss | Neon automated backups + weekly CSV/PDF export job; repo on GitHub |
| "Does simulator time count?" challenges | Never claim work-experience credit; label everything as classroom/laboratory hours + pre-lab prep; per-citation mapping printed on records; program director attestation remains the authority |

## 7. Open questions (non-blocking, decide during build)

1. Course director / instructor-of-record name and program name to print on certificates and records.
2. Pass threshold and attempt policy for exams (default proposal: 80%, unlimited attempts, all attempts logged).
3. Whether to re-upload the Bolin videos to a project channel now (recommended) or embed her channel directly at first.
4. Domain name (e.g., `hotlabsim.com` or an institutional subdomain) — needed before rollout, not before building.
5. How many credited hours to assign per module (needs your judgment against actual lesson runtimes).

## 8. Source references

- 10 CFR 35.290 / 35.190 / 35.204 / 35.60 / 35.61 / 35.2310 — https://www.law.cornell.edu/cfr/text/10/35.290 (et al.)
- NMSS-ISG-03 T&E implementation guidance (Apr 2025) — https://www.nrc.gov/docs/ML2505/ML25051A034.pdf (local: `ML25051A034.pdf`)
- NRC Med Use Toolkit, Authorized Individuals — https://www.nrc.gov/materials/miau/med-use-toolkit/auth-individuals
- Verified video + free-content inventory — `training_sources.md` (all links oEmbed-verified 2026-07-18)
- NRC Form 313A(AUD) — https://www.nrc.gov/reading-rm/doc-collections/forms/nrc313a-aud-info
- NUREG-1556 Vol. 9 Rev. 3 (2019) model procedures + Appendix D T&E documentation — https://www.nrc.gov/reading-rm/doc-collections/nuregs/staff/sr1556/v9/
- ACR NM accreditation QC — https://accreditationsupport.acr.org/support/solutions/articles/11000061046-quality-control-nuclear-medicine
- IAEA QC Atlas — https://www-pub.iaea.org/MTCD/publications/PDF/Pub1141_web.pdf
- IAEA NMQC Toolkit (ImageJ plugins) — https://humanhealth.iaea.org/HHW/MedicalPhysics/NuclearMedicine/QualityAssurance/NMQC-Plugins/index.html
- Core Physics Review NRC80 (competitor) — https://corephysicsreview.com/nrc80
- ASNC/SNMMI 80-hour course (didactic competitor) — https://www.asnc.org/80hour
- YouTube IFrame Player API — https://developers.google.com/youtube/iframe_api_reference
- Better Auth — https://better-auth.com · Drizzle — https://orm.drizzle.team · pdf-lib — https://pdf-lib.js.org
- ACGME DR FAQ (700/80-hour interplay) — https://www.acgme.org/globalassets/pdfs/faq/420_diagnosticradiology_faqs.pdf
