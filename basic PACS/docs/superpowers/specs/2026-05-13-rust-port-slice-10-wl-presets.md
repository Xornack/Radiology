# RustRadStack — Slice 10 design: W/L presets

**Date:** 2026-05-13
**Status:** Approved (no-questions mode)
**Author:** Matthew Harwood (with Claude Code)

## Problem

The viewer has DICOM-tag-derived W/L and a both-button-drag adjust, but nothing in
between. Daily radiology workflow leans heavily on a handful of canonical
window/level settings — Soft Tissue, Lung, Bone, Brain, Mediastinum, Liver — and
PACS workstations universally bind these to number keys. PyRadStack does not have
this; RustRadStack should.

## Non-goals

- User-configurable presets / persistence to disk (defer).
- Letter-key shortcuts (`L`/`B`/`S` style) — number keys are unambiguous; defer.
- Per-modality automatic preset selection (defer).
- Showing W/L values numerically in the status bar (only the preset name shows for now).
- Touchbar / on-screen preset buttons.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Preset list | Hardcoded in code | Six entries; YAGNI on a config file |
| Preset module | New `src/presets.rs` | Tiny, pure, no GUI deps — testable in isolation |
| Key bindings | `1`–`6` apply preset N; `0` clears override | Universal PACS convention; matches typical workstations |
| Application path | `stack.set_override_window(Some((c, w)))` | Reuses existing override mechanism; non-DICOM ignores override (existing behavior) |
| Active preset name | Tracked in `ViewerApp::active_preset_name` | Cleared on W/L drag (→ "Custom") and on new-folder load |
| Status bar | Append " — &lt;Preset name&gt;" when active | Smallest UI change; preserves existing "Slice X / N" |

## Preset values

These are conventional CT HU values — common across PACS workstations.

| # | Name | Center | Width |
|---|---|---|---|
| 1 | Soft Tissue | 40 | 400 |
| 2 | Lung | -600 | 1500 |
| 3 | Bone | 400 | 1800 |
| 4 | Brain | 40 | 80 |
| 5 | Mediastinum | 40 | 350 |
| 6 | Liver | 60 | 160 |

## Architecture

### New module: `src/presets.rs`

```rust
//! Hardcoded W/L presets for common radiology display modes.

pub struct WindowPreset {
    pub name: &'static str,
    pub center: f64,
    pub width: f64,
}

pub const PRESETS: &[WindowPreset] = &[
    WindowPreset { name: "Soft Tissue", center:   40.0, width:  400.0 },
    WindowPreset { name: "Lung",        center: -600.0, width: 1500.0 },
    WindowPreset { name: "Bone",        center:  400.0, width: 1800.0 },
    WindowPreset { name: "Brain",       center:   40.0, width:   80.0 },
    WindowPreset { name: "Mediastinum", center:   40.0, width:  350.0 },
    WindowPreset { name: "Liver",       center:   60.0, width:  160.0 },
];
```

Pure data — no `egui` dependency. Re-exported from `lib.rs`.

### Viewer integration

`ViewerApp` gains one field:

```rust
active_preset_name: Option<&'static str>,
```

Cleared in three places:
- `load_path` — new folder loaded, override reset, name reset.
- Both-button W/L drag — user is now in "Custom" mode.
- `0` key — explicit clear (also clears override).

Set in one place:
- Digit-key press `1`–`6` — applies preset, sets name.

UI change in the status bar:

```rust
let label = match self.active_preset_name {
    Some(name) => format!("Slice {current} / {total} — {name}"),
    None => format!("Slice {current} / {total}"),
};
```

Keyboard handling block is added next to the existing wheel/drag input pass:

```rust
let preset_index = ctx.input(|i| {
    for (n, key) in [
        (1, egui::Key::Num1), (2, egui::Key::Num2), (3, egui::Key::Num3),
        (4, egui::Key::Num4), (5, egui::Key::Num5), (6, egui::Key::Num6),
    ] {
        if i.key_pressed(key) { return Some(n); }
    }
    None
});
let clear_pressed = ctx.input(|i| i.key_pressed(egui::Key::Num0));
```

Applied with explicit branches in the `if let Some(stack) = self.stack.as_mut()` block.

### Tests

- `src/presets.rs` inline unit tests: list non-empty, all centers/widths finite, no duplicate names, widths positive.
- `tests/presets.rs`: smoke test that imports the public API and verifies one well-known entry (Lung -600/1500).
- Viewer keypress wiring is GUI-side — no automated test (matches the existing pattern; egui tests deferred).

## Risks

- Float-comparison edge case: a user could drag W/L to *exactly* a preset's values and the name wouldn't reappear. Acceptable — name is set on explicit key press only.
- Number keys clash with future numeric input (e.g. "jump to slice 42"). Defer — no such feature yet.
- Pressing `1` while a JPG/PNG slice is current sets the override (silently ignored on that slice) but applies as soon as the user scrolls to a DICOM. That matches existing W/L override semantics — fine.

## Slicing

One slice, 4 tasks + 2 standard-template tail tasks:

1. `presets` module + unit tests.
2. Viewer keyboard handling + status bar wiring + `active_preset_name` field.
3. README controls section update.
4. Manual GUI smoke (user; deferred if headless).
5. **Profiling pass** — verify preset switch is a no-op cost on top of the existing W/L drag path.
6. **Dead-code / readability refactor pass** — clippy + small cleanups.

## Done criteria

- `cargo build --release` clean.
- `cargo test` green — current 33 + new presets tests (+3 unit, +1 integration ≈ 37).
- `cargo clippy --all-targets` clean.
- README documents keys.
- Manual smoke: pressing `2` on a CT chest slice visibly switches to lung window; pressing `0` reverts; both-button drag now shows no preset name in status bar.
