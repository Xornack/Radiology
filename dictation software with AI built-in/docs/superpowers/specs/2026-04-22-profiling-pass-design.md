# Design: Profiling Harness + Initial Report

**Date:** 2026-04-22
**Status:** Approved for implementation planning
**Slice:** Reusable profiling tooling + first sweep. Adjustments identified by the report are deferred to a follow-up spec.

## Purpose

Give the project a repeatable way to answer "what's slow?" Today `LatencyTimer`
captures a handful of pipeline spans, but there's no sampling profiler, no
reproducible workload, and no report format. Future plans end with a profiling
pass (standing preference); this spec gives that pass a harness to use.

Two deliverables:
1. **Reusable harness** at `tools/profile_pipeline.py` — re-runnable after any
   change that might affect latency.
2. **Initial report** under `docs/superpowers/profiling/` — the first sweep's
   findings, which will seed the follow-up adjustment spec.

## Non-goals

- Acting on findings (e.g. fixing streaming re-transcribe cost, switching STT
  engines, GPU tuning). Those become their own specs after the user reads the
  report.
- Multi-backend comparison. SenseVoice only for this pass — it is the user's
  preferred engine. If the report shows SenseVoice is slow in an unexpected
  way, a backend comparison is a natural follow-up.
- Word-error-rate regression testing. The harness stores ground-truth
  transcripts so WER can be added later, but the initial pass measures time,
  not accuracy.
- CI integration. Harness is a developer tool, run manually.

## Scope of this slice

1. **Benchmark workload** — three LibriSpeech test-clean clips at short
   (~3 s), medium (~10 s), long (~30 s via concatenation). Stored under
   `benchmarks/` (gitignored) with matching ground-truth transcripts.
2. **Two-pass profiling** — every scenario runs twice:
   - **Timing pass**: N iterations captured via `LatencyTimer`; summary table
     reports min / median / p95.
   - **Discovery pass**: one `pyinstrument` run; HTML trace saved alongside
     the report.
3. **Six scenarios** (timing-pass iteration counts in parens; the discovery
   pass runs once per scenario that gets an HTML trace):
   - `cold_import` (1 run) — subprocess `python -c "import src.main"` wall
     time. No HTML trace (subprocess boundary defeats `pyinstrument`).
   - `sensevoice_warm` (1 run) — first `SenseVoiceSTTClient().warm()` call.
     No HTML trace (one-shot).
   - `stt_hot_path` (3 per clip length) — `transcribe()` on short / medium /
     long. HTML trace per length.
   - `full_pipeline` (3 per clip length) — `orchestrator.handle_trigger_down/
     up` with a mock recorder feeding clip bytes and a mock wedge (`inapp`
     mode). HTML trace for the medium clip only.
   - `streaming_tick` (3 per buffer size) —
     `StreamingTranscriber._transcribe_worker` called directly with 5 s /
     15 s / 30 s buffers. HTML trace for the 30 s buffer.
   - `text_post_processing` (1000 iterations) — `scrub_text` +
     `apply_punctuation` + `correct_radiology` on a representative
     paragraph. One HTML trace over the batch.
4. **Markdown report** — summary table at the top, per-scenario sections with
   links to the HTML traces, environment block (Python version, OS, CPU,
   SenseVoice model revision) so runs on different machines are comparable.
   Filename pattern: `YYYY-MM-DD-HHMM-profile.md`. Every run writes a fresh
   timestamped report — subsequent same-day runs never overwrite prior ones.
5. **Initial-run artifact** — the first committed report uses its natural
   timestamped filename (e.g. `2026-04-22-1430-profile.md`) plus its HTML
   traces in a sibling folder of the same stem.

## Architecture

One script, helper modules alongside it, one output folder.

```
tools/
├── __init__.py                 (new — makes `python -m tools.profile_pipeline` work)
├── profile_pipeline.py         (entry point; CLI + scenario orchestration)
├── profiling/
│   ├── __init__.py
│   ├── benchmarks_setup.py    (ensure clips exist; download + transcode)
│   ├── scenarios.py           (one function per scenario)
│   ├── harness.py             (timing-pass + pyinstrument-pass runners)
│   ├── mocks.py               (MockRecorder, MockWedge, FixedLatencySTT)
│   └── report.py              (markdown writer)

benchmarks/                    (gitignored)
├── short.wav                  (~3 s, 16 kHz mono PCM)
├── medium.wav                 (~10 s)
├── long.wav                   (~30 s, concatenated from LibriSpeech snippets)
└── transcripts.json           ({"short": "...", "medium": "...", "long": "..."})

docs/superpowers/profiling/
└── 2026-04-22-1430-profile.md           (timestamped; initial run's actual clock value)
└── 2026-04-22-1430-profile/
    ├── stt_hot_path_short.html
    ├── stt_hot_path_medium.html
    ├── stt_hot_path_long.html
    ├── full_pipeline_medium.html
    ├── streaming_tick_long.html
    └── text_post_processing.html
```

`tools/profiling/` is a package, not a folder dumped next to `hid_probe.py`,
so the modules don't clutter `tools/` or pollute the import namespace.
Adding `tools/__init__.py` lets us run the harness as `python -m
tools.profile_pipeline` — which is what the smoke test and docs assume.
The existing `hid_probe.py` is unaffected; it still runs via
`python tools/hid_probe.py ...`.

### `tools/profile_pipeline.py`

CLI entry point. Flags:
- `--quick` — skip `cold_import` and `sensevoice_warm` (fastest feedback for
  iterating on a specific hot spot).
- `--clips-dir PATH` — override default `benchmarks/` location.
- `--output-dir PATH` — override the date-stamped report folder.
- `--iterations N` — override the default 3 for STT hot-path, 20 for text
  post-processing batching is separate.
- `--dry-run` — substitute a `FixedLatencySTT` (sleeps 200 ms, returns canned
  text); used by the smoke test.

Exit code is non-zero only on harness failure (scenarios throwing). Slow
results are data, not errors.

### `tools/profiling/benchmarks_setup.py`

`ensure_clips(clips_dir: Path) -> None`

- If `short.wav`, `medium.wav`, `long.wav`, and `transcripts.json` exist,
  return immediately.
- Otherwise: download LibriSpeech test-clean (or a single speaker
  sub-archive, whichever is smallest that yields usable clips). Convert the
  chosen FLACs to 16 kHz mono PCM WAV using `soundfile`
  (`soundfile.read` returns float32; re-encode with `soundfile.write` at
  `subtype='PCM_16'`). No `ffmpeg` dependency — `soundfile` handles FLAC
  natively via `libsndfile`.
- Concatenate three short clips to synthesize `long.wav` (rather than
  depending on an individual 30 s recording existing in the corpus). Pad
  with 200 ms of silence between joined clips so they don't blur.
- Write `transcripts.json` from the LibriSpeech `.trans.txt` entries.
- On network failure, raise a `BenchmarksUnavailable` error with a clear
  message telling the user where to drop their own WAVs manually and re-run.

### `tools/profiling/scenarios.py`

One function per scenario. Each takes `(clips_dir: Path, iterations: int,
stt_factory: Callable[[], STTClient]) -> ScenarioResult` so the harness can
swap in the real or dry-run STT without each scenario knowing which.

`ScenarioResult` is a dataclass: `name`, `params` (dict — clip length, etc.),
`timings_ms` (dict of span name → list of floats, the raw per-iteration
samples — report.py computes min/median/p95).

### `tools/profiling/harness.py`

Two public functions:
- `run_timing_pass(scenario, ...)` — calls the scenario N times, returns the
  `ScenarioResult`.
- `run_discovery_pass(scenario, output_path, ...)` — wraps one invocation
  in a `pyinstrument.Profiler`, dumps HTML to `output_path`.

### `tools/profiling/mocks.py`

- `MockRecorder` — records nothing; `get_wav_bytes()` returns pre-loaded WAV
  bytes from whichever clip the scenario selected. `start()` / `stop()` are
  no-ops.
- `MockWedge` — `type_text(text)` stores last call, no OS interaction.
- `FixedLatencySTT` — used by `--dry-run` only. `transcribe(bytes)` sleeps
  200 ms, returns `"mock transcription"`. `supports_streaming = True`.

### `tools/profiling/report.py`

`write_report(results: list[ScenarioResult], output_dir: Path, env: dict)
-> Path`

- Writes `<output_dir>/<date>-initial-report.md` (filename passed in, not
  hard-coded — callers decide).
- Top block: environment (Python version, platform, CPU name via `platform.
  processor()`, SenseVoice model name, date).
- Summary table: one row per scenario × parameter, columns min / median / p95
  (ms), iterations, notes.
- Per-scenario section: table of raw timings + Markdown link to the
  pyinstrument HTML if one was recorded.

## Data flow

1. User runs `python -m tools.profile_pipeline` (or `python
   tools/profile_pipeline.py`).
2. CLI parses flags, resolves paths, builds env dict.
3. `benchmarks_setup.ensure_clips(clips_dir)`. First run downloads ~350 MB
   of LibriSpeech, picks three clips, writes WAVs + transcripts. Subsequent
   runs are a no-op.
4. Instantiate real `SenseVoiceSTTClient()` (or `FixedLatencySTT` if
   `--dry-run`). Call `.warm()` **once outside the measurement loop**
   (except in `sensevoice_warm`, whose whole point is to measure the warm).
5. For each scenario:
   a. Run warm-up iteration(s), discard results.
   b. Timing pass: N measured iterations → `ScenarioResult`.
   c. Discovery pass: one iteration inside a `pyinstrument.Profiler`, HTML
      saved.
6. `report.write_report(results, output_dir, env)`.
7. Print the report path.

## Error handling & edge cases

- **`sensevoice` extra not installed** — catch `ImportError` during STT
  construction. Skip STT-dependent scenarios (`sensevoice_warm`,
  `stt_hot_path`, `full_pipeline`). Still run `cold_import`,
  `streaming_tick` (under `FixedLatencySTT`), and `text_post_processing`.
  Report notes the skip.
- **Clips missing and no network** — raise `BenchmarksUnavailable` with a
  clear message. Don't silently fall back to synthetic audio; the user
  should know their report isn't based on the standard clips.
- **Wrong-format clip present** (rate, channel count, bit depth) — fail
  fast with the actual format in the error message. Don't attempt to fix
  in place.
- **`pyinstrument` not installed** — fail fast at script start with
  install hint. No "skip discovery pass" fallback; this tool is opt-in
  already and running without it produces a much weaker report.
- **First run takes longer because of clip download** — print progress
  explicitly (`"Downloading LibriSpeech test-clean (this one time)..."`).
- **Running on GPU hardware without `[gpu]` installed** — not relevant
  here; SenseVoice uses FunASR's own device resolution, not the Whisper
  GPU path.

## Back-compatibility

- No changes to runtime code paths. `LatencyTimer` is extended only if a
  scenario needs a span that doesn't exist. Proposed additions: none at
  spec time; revisit if the timing pass is missing a split we want.
- New dev dependency in `pyproject.toml [project.optional-dependencies] dev`:
  `pyinstrument>=4.6`. Pure Python, lightweight. Users who don't run
  profiles never install it via the dev extra regardless.

## Testing

### Unit (`tests/unit/test_profiling_harness.py`, new)

- `ensure_clips` is a no-op when all three WAVs + transcripts.json exist
  (monkeypatch download function; assert it's not called).
- `ensure_clips` raises `BenchmarksUnavailable` when both the files are
  missing and the download function is mocked to raise a network error.
- `report.write_report` given a fixed list of `ScenarioResult` objects
  produces a markdown file whose summary table rows match the inputs and
  whose env block contains the supplied Python version / platform / CPU.
- `run_timing_pass` calls the scenario N times and populates `timings_ms`
  with N entries per span.
- `run_discovery_pass` writes a non-empty HTML file at the target path.
  (Use a trivial scenario — `lambda: time.sleep(0.01)` — to avoid
  depending on SenseVoice.)
- `mocks.MockRecorder.get_wav_bytes()` returns the bytes it was primed
  with; `start/stop` are no-ops.
- `mocks.FixedLatencySTT.transcribe` sleeps ~200 ms and returns the canned
  string.

### Smoke (`tests/unit/test_profile_pipeline_dryrun.py`, new)

- Run `python -m tools.profile_pipeline --dry-run --iterations 1
  --clips-dir <tmpdir_with_stub_wavs>` as a subprocess. Assert:
  - exit code 0,
  - a report markdown file is written under the resolved output dir,
  - all six scenario names appear in the report.

Stub WAVs for the smoke test are 1 s of silence at 16 kHz mono, written
inline via the `wave` module. Full LibriSpeech clips are **not** used in
tests — this keeps CI fast and avoids a 350 MB download in the test path.

### Manual test plan (for the user after the slice lands)

1. First run: `python -m tools.profile_pipeline`. Confirm the
   LibriSpeech download progress prints, clips land in `benchmarks/`, a
   report lands under `docs/superpowers/profiling/`.
2. Open the markdown report; confirm the summary table populates and all
   scenario HTMLs open in a browser.
3. Re-run: confirm the clips step is a no-op (no re-download), the report
   path is new (date-stamped or suffixed — spec leaves that to planning).
4. `--quick`: confirm `cold_import` and `sensevoice_warm` rows are absent
   or marked skipped.

## Profiling pass (final plan step)

- Run the new harness on itself: `python -m tools.profile_pipeline` against
  the project in its post-implementation state. This is the "initial
  report" deliverable above — the standing profiling-pass step is
  literally satisfied by running the tool being built.
- Read the report together with the user. File a follow-up spec titled
  along the lines of `2026-04-XX-profiling-adjustments-design.md`
  capturing whatever the report flags (streaming re-transcribe, SenseVoice
  cold load, scrub regex cost — whatever actually appears).

## Dead-code + readability sweep (final plan step)

- `rg` pass for unused imports, one-shot helpers, stale comments in the
  new `tools/profiling/` modules.
- Re-read each module top-to-bottom. Target: each module under ~200 lines,
  single clear purpose, obvious from the name.
- Confirm no accidental duplication between `benchmarks_setup.py` and any
  future planned "download helper" — the LibriSpeech setup code belongs
  with the harness, not the app.
- Update `README.md`: one short section under "Testing" pointing at
  `tools/profile_pipeline.py` with a one-line command.

## Slice boundary check

This slice ends at a committed report and a working harness. No app
behavior changes. The user reads the report, and the follow-up spec —
"profiling adjustments" — picks which findings are worth acting on.
