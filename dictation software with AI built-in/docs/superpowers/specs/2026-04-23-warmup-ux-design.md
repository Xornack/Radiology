# Design: first-dictation warm-up UX

**Date:** 2026-04-23
**Status:** Approved for implementation planning
**Slice:** Second adjustment from the 2026-04-22 profiling pass. Fixes the
perceived-broken behavior when the user hits Record during the ~13 s
SenseVoice cold-load window. Scope: tiny.

## Purpose

Today, `main.py` fires `stt.warm()` in a daemon thread at startup. The UI
has no idea it's running. If the user hits Record before the model
finishes loading, the trigger quietly waits on the STT lock for ~13 s on
first launch (or ~4 s on subsequent launches within the same process).
From the user's perspective, the app froze.

This spec wires a small coordinator around the existing warm thread so
the UI can show the state, disable Record while warming, and re-enable
cleanly when ready.

## Non-goals

- Progress bar or percent-done display. FunASR doesn't expose
  per-step progress, so anything we showed would be fake.
- Preloading on a trigger other than startup. The natural moment is
  when the app launches — anything else is guessing.
- Speeding up the warm itself (investigation-heavy, separate spec if
  ever warranted).
- Changing the STT client `warm()` interface. The coordinator wraps
  existing behavior; clients don't need to know about it.

## Scope of this slice

1. **`src/ui/warmup_coordinator.py` (new).** A small `QObject`:
   - Method: `warm_in_background(stt_client) -> None` — spawns a daemon
     thread that calls `stt.warm()` if the client has that attribute.
   - Signals: `ready()` and `failed(str)`. Emitted on thread completion.
     Qt's default AutoConnection routes these to the GUI thread.
2. **`MainWindow.set_warming(on: bool)` (new).**
   - When `on=True`: status → "Warming model…" with a neutral warming
     color; Record button disabled.
   - When `on=False`: status → "Ready"; Record button re-enabled (if
     no other lock is holding it).
   - No new widgets. Reuses the existing status label and Record button.
3. **`main.py` wiring changes:**
   - Replace the bare `threading.Thread(target=stt.warm, ...)` with a
     `WarmupCoordinator` instance.
   - Immediately call `window.set_warming(True)` before kicking off
     the warm.
   - Connect `coordinator.ready` → `window.set_warming(False)`.
   - Connect `coordinator.failed(msg)` → status "STT failed — {msg}".
     Keep Record disabled in that case (a failed warm means
     `transcribe` will also fail; no point enabling Record).
   - Same coordinator used on `on_stt_changed` so backend swaps get
     the same UX (today's code silently spawns a new warm thread).
   - Guard `handle_trigger` with a `warming` flag — F4, HID, and
     button clicks are no-ops while warming. A nudge status
     ("Still warming — please wait") tells the user what's happening
     instead of silent rejection.

## Architecture

```
src/ui/warmup_coordinator.py     (new)
├── WarmupCoordinator(QObject)
│   ├── ready = pyqtSignal()
│   ├── failed = pyqtSignal(str)
│   └── warm_in_background(stt) -> None

src/ui/main_window.py            (extend)
├── set_warming(on: bool)         (new method)
└── _warming: bool                (new attribute, default False)

src/main.py                      (rewire)
├── warmup = WarmupCoordinator()
├── warmup.ready.connect(lambda: window.set_warming(False))
├── warmup.failed.connect(...)
├── warmup.warm_in_background(stt)    # replaces raw Thread
└── handle_trigger guards on `window._warming`
```

## Data flow

### App launch
1. `main.py` builds the STT client, constructs the window, constructs
   `WarmupCoordinator`, wires signals.
2. Before starting the warm thread, calls `window.set_warming(True)`.
   Status → "Warming model…". Record disabled.
3. `coordinator.warm_in_background(stt)` spawns a daemon thread that
   calls `stt.warm()`.
4. On completion, daemon thread emits `ready()` (or `failed(msg)`).
5. GUI thread receives the signal (Qt AutoConnection), runs
   `window.set_warming(False)`. Status → "Ready". Record enabled.

### User presses Record mid-warm
1. `handle_trigger(True)` is called (from F4 / HID / button).
2. Guard at the top: `if window._warming: window.set_status("Still
   warming — please wait", "#f9e2af"); return`.
3. Trigger is dropped. `recording_state["active"]` unchanged. No
   recorder start, no orchestrator call.

### STT backend swap
1. `on_stt_changed(backend)` in `main.py` builds a new client.
2. Before assigning it to `orchestrator.stt_client` /
   `streaming.stt_client`, calls `window.set_warming(True)` and
   `coordinator.warm_in_background(new_client)`.
3. Same signal plumbing as startup. Record disabled during swap-warm,
   enabled when ready.

### Warm failure
1. Thread catches exception from `stt.warm()`, emits `failed(msg)`.
2. Status → "STT failed — {msg}" in the error color.
3. Record stays disabled. User can still switch STT backend via the
   combo (which triggers a fresh coordinator cycle) — so they aren't
   stuck.

## Error handling & edge cases

- **Client has no `warm()` method** (e.g. the HTTP Whisper client):
  coordinator detects via `hasattr(stt, "warm")` and emits `ready()`
  immediately without spawning a thread. Record enables right away.
- **`warm()` raises** (model download failed, bad auth, etc.):
  coordinator catches in the thread, emits `failed(msg)` on the GUI
  thread. Stringified exception is shown in the status bar.
- **User swaps STT backend while the old one is still warming:** the
  new coordinator call spawns a second thread for the new client.
  The old thread continues in the background but its `ready` signal
  is routed through a coordinator that's still alive; the outdated
  signal would fire after the new warm's already done. Mitigation:
  `WarmupCoordinator` keeps a monotonic `_generation` counter,
  increments it on each `warm_in_background`, and discards signals
  whose generation doesn't match the current. Simple and safe.
- **App quit during warm:** the warm thread is daemon, dies with the
  process. Coordinator doesn't need to join.
- **Radiology mode toggle / mic combo / mode toggle pressed during
  warm:** existing UI lock rules apply (mic combo is already locked
  during recording; same logic extends to "while warming" — but
  trivially, since not recording means the existing
  `set_recording_state` path isn't involved). No extra work needed
  here.

## Back-compatibility

- `WarmupCoordinator` is additive — no existing caller of `stt.warm()`
  changes behavior. `SenseVoiceSTTClient`, `LocalWhisperClient`, and
  friends are unchanged.
- `main.py`'s current raw `threading.Thread(target=stt.warm, ...)`
  pattern is replaced in two places (startup, `on_stt_changed`) with
  coordinator calls. No semantic change beyond "the UI now knows."
- `MainWindow.set_warming` is additive. Callers that don't use it get
  today's behavior.

## Testing

### Unit — `tests/unit/test_warmup_coordinator.py` (new)

- `warm_in_background` with an STT whose `warm()` returns normally
  fires `ready` exactly once. (Uses `qtbot.waitSignal`.)
- `warm_in_background` with an STT whose `warm()` raises fires
  `failed(msg)` exactly once with the exception's string; `ready`
  does not fire.
- `warm_in_background` with an STT that has NO `warm` attribute
  fires `ready` immediately (no thread needed — shortcut path).
- Generation guard: calling `warm_in_background` twice in rapid
  succession, where the first `warm()` is slow and the second is
  fast, emits `ready` only once (the second invocation — from the
  current generation).

### Unit — `tests/unit/test_main_window.py` (extension)

- `set_warming(True)` disables Record and sets a warming status.
- `set_warming(False)` re-enables Record and sets "Ready" status.
- `set_warming(True)` while recording (defensive): status updates,
  but the Record button's state is controlled by
  `set_recording_state` — noted here so the test author doesn't
  write an over-specified assertion.

### Manual test plan

1. Launch app. Status bar shows "Warming model…" for ~13 s (cold) or
   ~4 s (warm cache). Record button greyed.
2. Press F4 during that window. Status briefly shows "Still warming —
   please wait"; no recording starts.
3. Wait for Ready. Record works normally.
4. Switch STT backend via the combo. Status shows "Warming model…"
   again during the new client's warm. Record re-enables when done.
5. (Optional) Set `STT_BACKEND=whisper-http` and relaunch — the HTTP
   client has no `warm()`, so status should skip "Warming…" entirely
   and go straight to "Ready".

## Profiling pass (final plan step)

Not really applicable to a UX-shaped fix. The warm cost is unchanged;
we're just surfacing it. A re-run of `python -m tools.profile_pipeline`
to confirm no regression in the other scenarios is the closing check.

## Dead-code + readability sweep (final plan step)

- Remove the raw `threading.Thread(target=stt.warm, ...)` call and
  the inline comment attached to it in `main.py` — it's superseded
  by the coordinator.
- Re-read `warmup_coordinator.py`, the edited `main.py` block, and
  the new `set_warming` path in `main_window.py`. Target: each
  change <30 lines, single clear purpose.
- Grep for any other `stt.warm()` direct call to make sure we didn't
  miss a call site. Expected: only the two we edit, and the lazy
  call inside `stt_client.transcribe()` which is intentional (final
  fallback if the coordinator didn't run for any reason).

## Slice boundary

Land at a stable, user-facing improvement. User launches the app,
sees warming, waits, records normally. If the "Still warming" nudge
feels noisy or the warming color is wrong, tune in a follow-up.
