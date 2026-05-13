# RustRadStack — Slice 10 Implementation Plan (W/L presets)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute. Steps use `- [ ]` checkbox syntax.

**Goal:** Add a `presets` module with the six canonical CT W/L settings (Soft Tissue, Lung, Bone, Brain, Mediastinum, Liver), bind them to number keys `1`–`6`, and `0` clears the override. The viewer shows the active preset name in the status bar; W/L drag clears the preset name back to nothing ("Custom").

**Architecture:**
- **New module** `src/presets.rs` — pure data + types. `WindowPreset { name, center, width }` and `PRESETS: &[WindowPreset]`. Re-exported from `lib.rs`.
- **`src/viewer.rs`** — new field `active_preset_name: Option<&'static str>` on `ViewerApp`. New input pass reads `egui::Key::Num0..=Num6`. Status bar branches on `active_preset_name`. Existing W/L drag clears the name. `load_path` clears the name.

**Tech Stack:** No new deps. `egui::Key::Num0..=Num9` is already in the eframe API.

Working dir: `basic PACS/rust_version/`.

Test count baseline (post-slice-9): 33 tests. Slice-10 target: 37 tests (+3 unit + 1 integration).

---

## Task 1: `presets` module + unit tests

**Files:**
- Create: `basic PACS/rust_version/src/presets.rs`
- Modify: `basic PACS/rust_version/src/lib.rs`
- Create: `basic PACS/rust_version/tests/presets.rs`

- [ ] **Step 1: Create `src/presets.rs` with the type and constant**

```rust
//! Hardcoded W/L presets for common radiology display modes.
//!
//! Six canonical CT settings — daily-use across PACS workstations. Pure data;
//! no GUI deps so callers can use the values without pulling in egui.

/// A named (center, width) pair.
pub struct WindowPreset {
    pub name: &'static str,
    pub center: f64,
    pub width: f64,
}

/// Canonical CT W/L presets, in order. Indexing is 0-based; the viewer maps
/// number keys 1..=N to `PRESETS[N-1]`.
pub const PRESETS: &[WindowPreset] = &[
    WindowPreset { name: "Soft Tissue", center:   40.0, width:  400.0 },
    WindowPreset { name: "Lung",        center: -600.0, width: 1500.0 },
    WindowPreset { name: "Bone",        center:  400.0, width: 1800.0 },
    WindowPreset { name: "Brain",       center:   40.0, width:   80.0 },
    WindowPreset { name: "Mediastinum", center:   40.0, width:  350.0 },
    WindowPreset { name: "Liver",       center:   60.0, width:  160.0 },
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn presets_list_non_empty() {
        assert!(!PRESETS.is_empty());
    }

    #[test]
    fn preset_widths_positive_and_finite() {
        for p in PRESETS {
            assert!(p.width > 0.0, "preset {} has non-positive width: {}", p.name, p.width);
            assert!(p.center.is_finite(), "preset {} center not finite", p.name);
            assert!(p.width.is_finite(), "preset {} width not finite", p.name);
        }
    }

    #[test]
    fn preset_names_unique() {
        let mut names: Vec<&str> = PRESETS.iter().map(|p| p.name).collect();
        names.sort_unstable();
        let original_len = names.len();
        names.dedup();
        assert_eq!(names.len(), original_len, "duplicate preset name(s)");
    }
}
```

- [ ] **Step 2: Re-export from `src/lib.rs`**

Add the `pub mod presets;` line in alphabetical order alongside the existing `pub mod` lines. The full file should read:

```rust
//! `RustRadStack` — DICOM stack viewer library.

pub mod errors;
pub mod loader;
pub mod loading;
pub mod presets;
pub mod sorting;
pub mod stack;
pub mod viewer;
pub mod windowing;

pub use errors::RrsError;
```

- [ ] **Step 3: Create `tests/presets.rs` (smoke integration test)**

```rust
//! Smoke test for the public `presets` module.

use rustradstack::presets::{PRESETS, WindowPreset};

#[test]
fn lung_preset_is_negative_600_over_1500() {
    let lung: &WindowPreset = PRESETS.iter().find(|p| p.name == "Lung")
        .expect("Lung preset should exist");
    assert_eq!(lung.center, -600.0);
    assert_eq!(lung.width, 1500.0);
}
```

- [ ] **Step 4: Run — expect GREEN**

```powershell
cargo test --test presets ; cargo test presets::tests
```

Both should pass: 1 integration test + 3 unit tests.

- [ ] **Step 5: Full suite**

```powershell
cargo test
```

Expected: 37 tests pass (33 from slice 9 + 3 unit + 1 integration).

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/presets.rs" "basic PACS/rust_version/src/lib.rs" "basic PACS/rust_version/tests/presets.rs"
git commit -m "feat(rust): add W/L presets module (6 canonical CT settings)"
```

---

## Task 2: Viewer keyboard handling + status bar wiring

**Files:**
- Modify: `basic PACS/rust_version/src/viewer.rs`

This task is GUI-side; no automated tests (per the existing pattern — egui tests are deferred). Manual smoke is Task 4.

- [ ] **Step 1: Add field to `ViewerApp`**

Locate the `pub struct ViewerApp { ... }` block at the top of `src/viewer.rs`. Add a new field:

```rust
    /// Name of the active preset, or None if user is on file defaults or has
    /// dragged W/L manually ("Custom" mode). Cleared on W/L drag and on
    /// `load_path`. Set by digit-key preset application.
    active_preset_name: Option<&'static str>,
```

- [ ] **Step 2: Initialise the field in `new`, `empty`, and `load_path`**

Both `ViewerApp::new` and `ViewerApp::empty` build the struct; add `active_preset_name: None` to both literal constructions.

In `load_path`, the success arm currently resets `texture`, `texture_key`, `wheel_accum`, `drag_accum`, `load_error`. Add one more line:

```rust
                self.active_preset_name = None;
```

- [ ] **Step 3: Add input pass for preset keys**

In `ui()`, after the existing wheel/drag input block but before the both-button-W/L block, add:

```rust
        // Preset keys: 1-6 apply PRESETS[N-1]; 0 clears the override.
        let preset_index = ctx.input(|i| {
            for (n, key) in [
                (1usize, egui::Key::Num1), (2, egui::Key::Num2), (3, egui::Key::Num3),
                (4, egui::Key::Num4), (5, egui::Key::Num5), (6, egui::Key::Num6),
            ] {
                if i.key_pressed(key) { return Some(n); }
            }
            None
        });
        let clear_pressed = ctx.input(|i| i.key_pressed(egui::Key::Num0));

        if let Some(stack) = self.stack.as_mut() {
            if let Some(n) = preset_index
                && let Some(preset) = crate::presets::PRESETS.get(n - 1)
            {
                stack.set_override_window(Some((preset.center, preset.width)));
                self.active_preset_name = Some(preset.name);
            } else if clear_pressed {
                stack.set_override_window(None);
                self.active_preset_name = None;
            }
        }
```

- [ ] **Step 4: Clear preset name when user drags W/L**

In the existing both-button-drag W/L adjustment block, after the line that calls `stack.set_override_window(Some((new_center, new_width)))`, add:

```rust
            self.active_preset_name = None;
```

- [ ] **Step 5: Update the status bar to show the preset name**

Find the existing status bar at the bottom of `ui()`:

```rust
if let Some(stack) = &self.stack {
    let current = stack.current() + 1;
    let total = stack.len();
    ui.with_layout(
        egui::Layout::bottom_up(egui::Align::Center),
        |ui| { ui.label(format!("Slice {current} / {total}")); },
    );
}
```

Replace the `format!` call so it appends the preset name when one is active:

```rust
            let label = if let Some(name) = self.active_preset_name {
                format!("Slice {current} / {total} — {name}")
            } else {
                format!("Slice {current} / {total}")
            };
            ui.label(label);
```

- [ ] **Step 6: Repaint trigger**

The existing block at the bottom triggers a repaint while wheel or drag is active. Preset application is a one-shot event (key press), so no continuous repaint is needed — egui already repaints on key events. No change required here.

- [ ] **Step 7: Build**

```powershell
cargo build
```

Expected: clean build. If a borrow-checker error appears around the preset block (because `self.stack.as_mut()` is taken before `self.active_preset_name = ...`), restructure as:

```rust
let pname: Option<&'static str> = if let Some(stack) = self.stack.as_mut() {
    if let Some(n) = preset_index
        && let Some(preset) = crate::presets::PRESETS.get(n - 1)
    {
        stack.set_override_window(Some((preset.center, preset.width)));
        Some(preset.name)
    } else if clear_pressed {
        stack.set_override_window(None);
        None
    } else {
        self.active_preset_name  // unchanged
    }
} else {
    self.active_preset_name
};
self.active_preset_name = pname;
```

Same applies to the W/L drag block — set `active_preset_name = None` outside the `if let Some(stack) = self.stack.as_mut()` scope. If neither restructure is needed (Rust 2024 NLL is lenient enough), the simple form from Step 3 is fine — try that first.

- [ ] **Step 8: Full test suite (sanity)**

```powershell
cargo test
```

Expected: 37 tests pass — the viewer changes don't have automated tests, but nothing existing should regress.

- [ ] **Step 9: Commit**

```powershell
git add "basic PACS/rust_version/src/viewer.rs"
git commit -m "feat(rust): viewer applies W/L presets via number keys 0-6"
```

---

## Task 3: README controls update

**Files:**
- Modify: `basic PACS/rust_version/README.md`

- [ ] **Step 1: Add presets to the Controls block**

In the existing **Controls** list (under the GUI usage section), add new bullets after the both-button-drag entry:

```markdown
- **Number keys 1-6** — apply W/L preset:
  - 1 = Soft Tissue (C 40 / W 400)
  - 2 = Lung (C -600 / W 1500)
  - 3 = Bone (C 400 / W 1800)
  - 4 = Brain (C 40 / W 80)
  - 5 = Mediastinum (C 40 / W 350)
  - 6 = Liver (C 60 / W 160)
- **0** — clear preset / revert W/L to per-file DICOM tags
```

Below the existing status-bar mention, note:

```markdown
Status bar shows "Slice X / N — <Preset>" when a preset is active.
W/L drag clears the preset name (you're now in custom W/L).
```

- [ ] **Step 2: Update Roadmap**

Append:

```markdown
10. ✅ Slice 10 — W/L presets (number keys 1-6) + status bar shows active preset
```

Update the "MVP+ in progress" line's future-slice list — strike "W/L presets" since it's now done. Leave Nuitka-equivalent build and recent-files list.

- [ ] **Step 3: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): README documents W/L presets (slice 10)"
```

---

## Task 4: Manual GUI smoke

**Files:** none changed. This is verification only.

- [ ] **Step 1: Build release**

```powershell
cargo build --release
```

- [ ] **Step 2: Open a real CT chest series**

```powershell
.\target\release\rustradstack.exe path\to\some\CT\series\
```

If no CT series is locally available, skip this manual step and document "deferred to user manual test."

- [ ] **Step 3: Press number keys and verify**

- Press `2` (Lung) — image should appear dramatically darker with lung field brightened (large window, low center). Status bar shows "Slice X / N — Lung".
- Press `3` (Bone) — image lightens dramatically; soft tissue washes out. Status bar shows "Bone".
- Press `0` — revert to file defaults. Status bar shows "Slice X / N" (no preset).
- Both-button drag — W/L changes; status bar drops the preset name.
- Press `1` after drag — Soft Tissue applies; preset name reappears.

If headless: defer to user.

**No commit for this task — verification only.**

---

## Task 5: Profiling pass

**Files:** none changed unless a regression is found.

The preset path mutates `override_window` and triggers a texture re-upload — the same code path as W/L drag. No new performance concerns expected.

- [ ] **Step 1: Time a preset application**

In a release build, open a 24-slice MR series and press `1`, `2`, `3`, `4`, `5`, `6` in sequence. The image should redraw within one frame each time. If the redraw is visibly delayed (>50ms), profile with `cargo flamegraph` or `tracing` (defer instrumentation to a follow-up slice if it's not trivial).

- [ ] **Step 2: Document in README's Performance Notes**

Add one row to the existing performance table if the timing is interesting; skip if it's <10ms (same magnitude as W/L drag).

If nothing visible to add, note "preset switch is indistinguishable from W/L drag in latency" and move on.

- [ ] **Step 3: No commit unless a change was made.**

---

## Task 6: Clippy + readability refactor pass

**Files:** any files clippy flags.

- [ ] **Step 1: Run clippy with pedantic and nursery**

```powershell
cargo clippy --all-targets -- -W clippy::pedantic -W clippy::nursery
```

Apply suggestions that improve clarity. Specific items to look for:

- Unused imports introduced during slice-10 edits.
- The preset-key input pass could be extracted into a small helper if it grows. As of this slice it's 8 lines — inline is fine.
- `crate::presets::PRESETS` is referenced once in `viewer.rs`; a `use crate::presets::PRESETS;` at the top might read cleaner. Apply if clippy flags it; otherwise leave inline-qualified.

- [ ] **Step 2: Confirm green**

```powershell
cargo test
cargo clippy --all-targets
```

Expected: 37 tests pass; clippy clean.

- [ ] **Step 3: Commit**

```powershell
git add "basic PACS/rust_version"
git commit -m "refactor(rust): clippy + readability cleanup for slice 10"
```

---

## Done criteria

- [ ] `cargo build --release` clean
- [ ] `cargo test` green — 37 tests (33 prior + 3 unit `presets::tests` + 1 integration `tests/presets.rs`)
- [ ] `cargo clippy --all-targets` clean
- [ ] Manual smoke (or deferred to user): pressing `2` on a CT chest slice switches to Lung W/L; `0` reverts; W/L drag clears the preset name in the status bar
- [ ] README documents the new keys

## Out of scope (for future slices)

- User-configurable preset values (config file / settings dialog).
- Letter-key shortcuts (`L`/`B`/`S`).
- Per-modality auto-selection of a default preset.
- Persisting last-used preset across sessions.
- On-screen preset buttons.
- Showing numeric W/L values in the status bar (only the preset name appears in slice 10).
