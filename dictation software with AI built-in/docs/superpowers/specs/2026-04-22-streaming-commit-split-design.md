# Design: VAD-based streaming commit/split

**Date:** 2026-04-22
**Status:** Approved for implementation planning
**Slice:** First adjustment from the 2026-04-22 profiling pass —
addresses `streaming_tick` scaling, the largest finding in
`docs/superpowers/profiling/2026-04-22-0204-profile.md`.

## Purpose

The streaming transcriber re-transcribes the full growing buffer on every
tick. Measured cost: 301 ms at 5 s, 599 ms at 15 s, 1563 ms at 30 s — the
1.5 s tick budget is blown by the 30 s mark, so partials stop keeping up
on long dictations.

This spec replaces the "re-transcribe the world" approach with a
commit-pointer + voice-activity-detection split. Each streaming tick
transcribes only the audio since the last commit, not the whole buffer.
Silence gaps of 600 ms+ mark safe commit points; everything before a
commit is locked in and never re-transcribed.

The goal is partial latency that scales with **partial length since the
last commit**, not with total dictation length. Expected behavior at a
30 s dictation with a few natural pauses: per-tick p95 around 300-400 ms
instead of 1.5 s.

## Non-goals

- Wedge mode. It doesn't stream; its `Stop`-path one-shot transcribe is a
  separate latency story and isn't addressed here.
- Replacing the energy-based VAD with `webrtcvad` / `silero-vad`. The
  DIY energy VAD is the zero-dep starting point; upgrading is a follow-up
  if the simple VAD misfires on real clinical audio.
- Visual distinction between committed and partial text. Today all
  dictated text renders in one dictation color; that stays.
- Incremental STT APIs from specific engines (SenseVoice streaming,
  faster-whisper chunked). Keeps the change engine-agnostic.
- Changing the post-processing contract: partials still only get
  `apply_punctuation`; `scrub_text` + `correct_radiology` still run once
  on the final concatenated text at Stop.
- WER / accuracy comparison against today's path as a gating criterion.
  This slice measures latency only; accuracy regression guard via
  manual testing during the plan's manual-test step.

## Scope of this slice

1. **Energy-based VAD** — new module `src/core/vad.py` with one function
   `find_commit_point(samples: np.ndarray, sample_rate: int) -> Optional[int]`.
2. **Recorder slice access** — `AudioRecorder.get_wav_bytes_slice(start_sample, end_sample) -> bytes`. Used by the streaming transcriber to encode only the partial region.
3. **StreamingTranscriber rework** — maintains `_commit_sample_idx` and a
   list `_committed_text`. Emits a new `commit_ready(str)` signal when
   a commit happens; existing `partial_ready(str)` keeps its signature.
4. **MainWindow rework** — replaces the `_partial_start` / `_partial_len`
   pair with a `_committed_end` / `_partial_end` pair. New `on_commit`
   slot locks in the current partial region. Existing public helpers
   (`begin_streaming`, `update_partial`, `commit_partial`) keep their
   names and semantics; internals adjust.
5. **Orchestrator Stop-path change** — reads `streaming.committed_text`
   and transcribes only the remaining partial region on Stop, then runs
   full post-processing on the concatenated result. When streaming was
   never active (e.g. a very short dictation with one empty partial) it
   falls back to the existing whole-buffer transcribe.
6. **New profiling scenario** — `scenario_streaming_commit` in
   `tools/profiling/scenarios.py`. Uses the same clip lengths as
   `streaming_tick` but drives the new commit-path. Regression guard for
   future profiling passes. Keep the existing `streaming_tick` scenario
   as-is so the before/after comparison stays visible in the report.

## Architecture

### `src/core/vad.py` (new)

```python
def find_commit_point(
    samples: np.ndarray,
    sample_rate: int = 16000,
    min_silence_ms: int = 600,
    min_chunk_ms: int = 2000,
    rms_window_ms: int = 30,
) -> Optional[int]:
    """Return sample index of a good commit point, or None.

    A commit point is the end of a silence gap of at least `min_silence_ms`
    that starts after `min_chunk_ms` of audio. Threshold is self-calibrated:
    max(0.002, 0.15 * rolling_max_rms) over `rms_window_ms` windows.

    Returns the sample index at the END of the silence gap (so the next
    partial starts at the first audible sample after the pause — words
    aren't clipped mid-syllable).
    """
```

- Pure function over a numpy array. No state, no I/O, trivially testable.
- Self-calibrating threshold removes a config knob the user would have
  to tune per-microphone.
- Returns `None` if there's no qualifying commit point. Caller continues
  without committing.

### `src/hardware/recorder.py` (addition)

`get_wav_bytes_slice(start_sample: int, end_sample: int) -> bytes`
encodes only `self._buffer[start_sample:end_sample]` to a 16 kHz mono
PCM WAV. Same format as `get_wav_bytes()` so STT consumers don't care.

The existing `get_wav_bytes()` is kept — it's still used by the Stop
path's fallback (short dictations with no commits) and by the profiling
harness's `streaming_tick` regression scenario.

### `src/core/streaming.py` (rework)

New instance state:
- `_commit_sample_idx: int = 0` — start of the unconunitted region.
- `_committed_text: list[str] = []` — ordered list of committed chunk
  transcriptions, already through `apply_punctuation`.

New signal: `commit_ready = pyqtSignal(str)` — emitted once per commit
with the committed chunk's text. Fires on the Qt main thread (same
auto-connection pattern as `partial_ready`).

Reworked `_transcribe_worker(partial_region_wav: bytes,
commit_candidate_wav: Optional[bytes])`:
1. If `commit_candidate_wav` is not None:
   a. Transcribe it.
   b. If non-empty and `_active`: `apply_punctuation`, emit
      `commit_ready(text)`, append to `_committed_text`, advance
      `_commit_sample_idx` locally.
   c. If transcribe fails or returns empty: do not advance
      `_commit_sample_idx` — the commit is abandoned. Next tick retries.
2. Transcribe `partial_region_wav`.
3. If non-empty and `_active`: `apply_punctuation`, emit
   `partial_ready(text)`.

Reworked `_tick` (runs on the Qt main thread via QTimer):
1. If `_in_flight` or not `_active`: return.
2. Read the current sample count from the recorder (add a cheap
   `AudioRecorder.get_sample_count() -> int`; reads under the same lock
   that guards `_buffer`).
3. Partial region: `[_commit_sample_idx, now_sample_count]`.
4. If partial region < `min_audio_seconds` worth of samples: return.
5. Ask `find_commit_point(samples_of_partial_region, sample_rate)` for a
   commit point.
6. Build `commit_candidate_wav` (if VAD returned a point) and
   `partial_region_wav` (the post-commit remainder, or the whole partial
   region if no commit).
7. Spawn worker thread as today; worker updates shared state via the
   signals.

The "find a commit point within the last 10 s of a >30 s partial region"
fallback from the design summary lives inside
`find_commit_point` — not in `_tick`. Keeps the tick logic simple.

### `src/ui/main_window.py` (rework)

Existing anchors (`_partial_start`, `_partial_len`) are replaced with
`_committed_end: int` and `_partial_end: int`. Invariant:
`insertion_origin ≤ _committed_end ≤ _partial_end`, where
`insertion_origin` is the cursor position at `begin_streaming()` (stored
implicitly as the initial value of `_committed_end`).

- `begin_streaming()`: `self._committed_end = self._partial_end =
  cursor.position()`.
- `update_partial(text)`: select `[self._committed_end,
  self._partial_end]`, remove, re-insert `text` in dictation format,
  update `_partial_end = _committed_end + len(text)`.
- `on_commit(text: str)`: select `[_committed_end, _partial_end]`,
  replace with `text` in dictation format, set `_committed_end =
  _partial_end = _committed_end + len(text)`. The replacement matters
  because the commit transcription of `[commit_idx, commit_point]` can
  differ from the previous partial's transcription of the strictly
  shorter `[commit_idx, previous_end]` — STT engines revise with more
  context. Trust the commit text (longer audio, more context) over the
  displayed partial.
- `commit_partial(final_text)`: same as today, but uses
  `[_committed_end, _partial_end]` as the region. On empty final_text,
  the region is removed and anchors reset to `-1`.

### `src/core/orchestrator.py` (Stop path)

`handle_trigger_up(mode)` currently: stops recorder, transcribes full
buffer, runs scrub + punctuation + (optional) lexicon, optionally calls
wedge, returns text.

`StreamingTranscriber` exposes a public accessor
`get_committed_snapshot() -> tuple[list[str], int]` returning a copy
of `_committed_text` and the current `_commit_sample_idx`. The
orchestrator uses this instead of touching private attributes. The
snapshot is taken *after* `streaming.stop()` so no tick can mutate
state mid-read.

New Stop path for in-app mode:
1. Stop recorder.
2. If a `streaming` handle is wired in: read
   `(committed_text, commit_idx) = streaming.get_committed_snapshot()`.
3. If `committed_text` is non-empty AND `commit_idx > 0`:
   a. Transcribe only
      `recorder.get_wav_bytes_slice(commit_idx, current_end)`.
   b. `final_text = " ".join(committed_text + [final_partial_text])`.
4. Otherwise (no streaming handle, or no commits ever happened):
   transcribe the whole buffer as today.
5. Run `scrub_text` + `apply_punctuation` + optional `correct_radiology`
   on the full text. (`apply_punctuation` is idempotent — running it
   again on the concatenated text, after each committed chunk already
   went through it, is safe and cheap.)
6. Return.

Back-compat: the `streaming` handle is injected into
`DictationOrchestrator` as an optional constructor parameter. When
absent, the orchestrator behaves exactly as today — wedge-mode tests
and any other callers don't need updates.

## Data flow

### In-app recording

1. Record → `recorder.start()`, `begin_streaming()`. Stream state:
   `_commit_sample_idx = 0`, `_committed_text = []`,
   `_committed_end = _partial_end = cursor.position()`.
2. t=1.5 s tick: partial region is `[0, 24000]` (1.5 s @ 16 kHz). No
   silence gap long enough to qualify. No commit. Transcribe partial →
   `partial_ready("The patient has")` → UI replaces
   `[_committed_end, _partial_end]` with the text.
3. t=3.0 s tick: partial region is `[0, 48000]`. VAD finds silence at
   samples 37000-47000 (625 ms silence, starting after 2.3 s of audio —
   qualifies). Commit point = 47000.
   - Transcribe `[0, 47000]` → `"The patient has a cough"`, emit
     `commit_ready("The patient has a cough")`, append,
     `_commit_sample_idx = 47000`.
   - UI `on_commit`: `_committed_end = _partial_end` (the already-
     displayed text is now locked in).
   - Transcribe `[47000, 48000]` (62 ms) → returns empty (too short).
     `partial_ready` skipped.
4. t=4.5 s tick: partial region is `[47000, 72000]` (1.5 s). No commit.
   Transcribe → `partial_ready("and") → UI replaces
   `[_committed_end, _partial_end]` with `"and"`, `_partial_end`
   advances 3 chars.
5. ... and so on.
6. Stop: `streaming.stop()` → `_active = False`. Orchestrator:
   `committed_text = "The patient has a cough"`,
   final_partial_audio = `[_commit_sample_idx, now]`, transcribes that,
   gets `"and no fever"`, concatenates `"The patient has a cough and no
   fever"`, runs full post-processing, returns.

### Short dictation (no commit ever fires)

`_committed_text` is `[]`, `_commit_sample_idx` is `0`. Orchestrator
falls through to the whole-buffer path. Behaves exactly like today.

## Error handling & edge cases

- **Commit transcribe returns empty** — do nothing. `_commit_sample_idx`
  stays put. Next tick re-tries the same region plus whatever grew.
- **Commit transcribe raises** — caught in the worker as today; logged;
  `_commit_sample_idx` not advanced; next tick retries.
- **Partial transcribe raises** — unchanged from today.
- **VAD returns None** on every tick for the whole dictation — behaves
  exactly like the old "re-transcribe the growing buffer" path, i.e.
  today's behavior (minus the 30 s fallback commit point). This
  degenerate case happens if the user talks through without pauses
  longer than 600 ms for the whole session; a 30 s continuous-talk
  dictation with no pauses is rare in clinical speech but we model it
  anyway.
- **30 s hard cap on partial region** — if `_commit_sample_idx` is more
  than 30 s behind the current sample and VAD still doesn't find a
  natural commit point, force a commit at the quietest 100 ms window
  inside the last 10 s of the partial region. Implemented inside
  `find_commit_point` so callers don't need to special-case it.
- **Stop during an in-flight tick** — as today, set `_active = False`;
  the tick worker's results are discarded. Clean final transcribe at
  Stop.
- **Recorder buffer truncated / reset between ticks** — not a supported
  state. `start()` is only called once per session; the buffer grows
  monotonically during `[start, stop)`. Reset happens inside `start()`,
  which the session boundary owns.
- **Backend doesn't support a given partial length** — SenseVoice
  handles anything from 60 ms up. If a backend chokes on sub-second
  audio, the worker catches the exception and `partial_ready` is
  skipped for that tick — same as today's failure mode.
- **`correct_radiology` only runs on Stop, not on partials**. Committed
  chunks don't go through it; the final concatenated text does. This
  means partials briefly show un-corrected text (e.g. "plural" instead
  of "pleural") before the final swap at Stop. Matches current
  behavior; not a regression.

## Back-compatibility

- `DictationOrchestrator.__init__` grows an optional `streaming=None`
  parameter. Existing tests that construct the orchestrator without it
  are unaffected.
- `handle_trigger_up(mode="wedge")` is unchanged — wedge mode doesn't
  stream, so the committed-text path is unused.
- `StreamingTranscriber.partial_ready` keeps its signature. A new
  `commit_ready` is additive. Existing consumers (only `main.py` today)
  get a new signal to wire; they don't need to handle it (the
  `update_partial` path alone still produces correct UX under
  "VAD never fires" fallback conditions, just without the latency win).

## Testing

### Unit — `tests/unit/test_vad.py` (new)

- Silence-surrounded tone fixture: tone(1 s) + silence(800 ms) + tone(1 s).
  `find_commit_point` returns an index inside the silence, specifically
  within 50 ms of the silence end.
- All-silence fixture: returns None (no qualifying audio before the
  silence to commit).
- Short-silence fixture: tone(1 s) + silence(300 ms) + tone(1 s) — 300
  ms is below `min_silence_ms`. Returns None.
- Short-chunk fixture: silence(100 ms) + silence(800 ms) + tone(1 s) —
  only 100 ms of audio exists before the 800 ms silence; below
  `min_chunk_ms`. Returns None.
- 30 s cap fallback: tone(35 s continuous, low RMS variance).
  `find_commit_point` returns an index inside the last 10 s at a local
  RMS minimum. (Asserts the index is > `35 s - 10 s = 25 s` in samples.)
- Self-calibrated threshold: the same tone-silence-tone fixture played
  back at different amplitudes (0.3, 0.7, 1.0 of full-scale) all yield
  a commit point near the silence end. Threshold doesn't need config.

### Unit — `tests/unit/test_streaming.py` (new)

- `_tick` with a fake STT and a recorder priming a silence-between-
  tones buffer: after a tick, `commit_ready` fires exactly once with
  the STT's return text for the first half; `_commit_sample_idx`
  advances past the silence.
- `_tick` with a buffer that has no silence: `commit_ready` never fires;
  `_commit_sample_idx` stays at 0; `partial_ready` fires with the
  full-partial transcription.
- `_tick` with a failing STT on the commit transcribe:
  `_commit_sample_idx` stays put; the partial transcribe still runs.
- `_transcribe_worker` rejects late results when `_active` is False (the
  race condition where Stop is called during a tick) — matches today's
  guard.

### Unit — `tests/unit/test_recorder.py` (extension)

- `get_wav_bytes_slice(start, end)` returns a WAV whose PCM frame count
  equals `end - start`. Header sample rate is 16000, channels 1, 16-bit.
- `get_wav_bytes_slice(0, 0)` returns a valid empty-WAV header (PCM
  frame count 0). Never a crash.
- `get_wav_bytes_slice(start, end)` with out-of-bounds indices raises
  a clear error (not silent truncation — that would hide bugs).

### Unit — `tests/unit/test_main_window.py` (extension)

- After `begin_streaming()`, `_committed_end == _partial_end ==
  cursor.position()`.
- `update_partial("one") → update_partial("one two") → on_commit("one
  two") → update_partial("three")`: editor text is `"one two" + "three"`
  at the anchor; the `"one two"` region is unaffected by subsequent
  updates. Style is dictation-color for both.
- `on_commit("...")` with `_committed_end == _partial_end` (empty
  partial region): no-op.
- `commit_partial(final_text)` with a prior `on_commit` call: replaces
  only the `[_committed_end, _partial_end]` region. `final_text == ""`
  removes the partial but leaves committed text intact.
- After `commit_partial(...)` finishes, the editor's current char
  format reverts to the editor default (the existing guard from the
  editable-transcript slice still applies).

### Unit — `tests/unit/test_orchestrator.py` (extension)

- `handle_trigger_up(mode="inapp")` with `streaming=None` (today's
  default): whole-buffer transcribe as today.
- `handle_trigger_up(mode="inapp")` with a `streaming` mock whose
  `get_committed_snapshot()` returns
  `(["The patient has a cough"], 47000)`: orchestrator calls
  `recorder.get_wav_bytes_slice(47000, end)`, concatenates committed +
  final_partial, runs full post-processing, returns the full string.
- `handle_trigger_up(mode="wedge")` with a `streaming` mock present —
  wedge mode ignores the streaming handle and does a whole-buffer
  transcribe as today.

### Integration — `tests/integration/test_streaming_pipeline.py` (new)

- End-to-end: MockRecorder primed with
  `tone(2 s) + silence(800 ms) + tone(2 s)`, FixedLatencySTT that maps
  each slice to a canned string. Exercise a couple of ticks and then a
  Stop. Assert:
  - `on_commit` fired exactly once on the main window.
  - Final editor text equals `committed + " " + final_partial` with
    `apply_punctuation` applied.
  - `_committed_end` reflects the committed span's end.

### Profiling — `tools/profiling/scenarios.py` (extension)

Add `scenario_streaming_commit(ctx) -> ScenarioResult` that runs the
new path. Clip lengths 5 s / 15 s / 30 s with a synthesized
tone-silence-tone pattern inside each (440 Hz sine at 0.3 amplitude,
alternating with 600 ms silence every 2.5 s) so VAD has commit points
to find. Span keys: `"5s"`, `"15s"`, `"30s"` — parallels
`streaming_tick` so the report rows line up visually.

Test (`tests/unit/test_profiling_scenarios.py`, extension): the new
scenario returns a `ScenarioResult` with the three expected span keys
and one sample per buffer size per iteration.

Keep `scenario_streaming_tick` as the regression baseline. The next
report shows both; the win is the gap between them at the 30 s row.

### Manual test plan (post-implementation)

1. Launch app, dictate a three-sentence paragraph in-app mode with
   natural pauses. Partials appear per-tick as today.
2. Scroll back mid-dictation — committed text stays stable; only the
   tail moves.
3. Dictate a 45 s paragraph. Partial region never blows past ~400 ms
   on the status bar's latency display.
4. Stop mid-word. Final text includes the half-word plus the natural
   completion from the STT.
5. Dictate without any pause >600 ms for 20 s. Fallback commit at
   the 30 s mark; first commit is at t=30 s, not earlier.
6. Switch to Wedge mode — behavior unchanged, no regressions from
   the streaming changes.

## Profiling pass (final plan step)

- `python -m tools.profile_pipeline` — new report has the
  `streaming_commit` row. Target: p95 ≤ 400 ms at the 30 s buffer
  size. Compare to `streaming_tick`'s p95 at the same row (should
  be ~1.5 s, per the 2026-04-22 baseline report).
- If p95 is higher than expected, inspect the new scenario's
  pyinstrument HTML trace for the hot call.

## Dead-code + readability sweep (final plan step)

- `rg` for unused imports / orphaned helpers across the touched files
  (`streaming.py`, `main_window.py`, `orchestrator.py`, `recorder.py`,
  new `vad.py`).
- Re-read each touched module top-to-bottom. Target: each file stays
  under 250 lines, single clear purpose. The `main_window.py` file is
  already ~400 lines (editable-transcript slice pushed it up) — this
  slice adds a bit more; if it crosses 500, add a follow-up to extract
  a `DictationEditor` widget. Do not extract in this slice.
- Confirm the `_partial_start` / `_partial_len` pair is completely
  removed from `main_window.py` — no leftover references from the
  earlier slice.

## Slice boundary check

This slice ends at a stable, usable working state. User exercises the
new streaming behavior, files any issues, confirms. Candidate next
slices (from the same 2026-04-22 profiling report): first-dictation
warm latency, or tiny optimization pass on `correct_radiology`.
