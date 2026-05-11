# RustRadStack — Slice 6 Implementation Plan (scroll polish)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute. Steps use `- [ ]` checkbox syntax.

**Goal:** Tame the mouse-wheel scroll (currently advances 1 slice per wheel tick — way too fast on high-res wheels) and add left-click drag scrolling. Both behaviors mirror PyRadStack's interaction model and the standard PACS workstation convention.

**Architecture:** All changes live in `src/viewer.rs`. New `ViewerApp` fields hold accumulated wheel delta and drag-Y delta + drag-active flag. Per frame: read wheel delta and add to accumulator; when accumulator crosses ±sensitivity threshold, advance/retreat one slice and subtract the consumed portion (no lost motion). For drag: on `PointerButton::Primary` press, mark drag active; while held, accumulate `pointer_delta.y` and step slices the same way; on release, reset accumulator. Drag-down = next slice, drag-up = previous slice (matches Python's `_handle_scroll_drag` direction convention).

**Tech Stack:** No new deps. egui 0.27+ exposes `i.smooth_scroll_delta`, `i.pointer.is_decidedly_dragging()`, `i.pointer.delta()`, `i.pointer.button_down(PointerButton::Primary)`. (Exact method names verified at impl time.)

Working dir: `basic PACS/rust_version/` (worktree root: `basic PACS/.claude/worktrees/scroll-polish/`).

---

## Task 1: Add `scroll_speed` constants + accumulator state to `ViewerApp`

Pure refactor — no behavior change yet. Sets up the state fields and constants Tasks 2 and 3 will populate.

**Files:** Modify `basic PACS/rust_version/src/viewer.rs`

- [ ] **Step 1: Add scroll-tuning constants and state fields**

In `src/viewer.rs`, add at the top of the file (after the existing `use` block, before `pub struct ViewerApp`):

```rust
/// Wheel delta units per slice advance. Higher = slower scroll.
/// Matches PyRadStack's `_DRAG_SCROLL_SENSITIVITY = 10`.
const WHEEL_SENSITIVITY: f32 = 10.0;

/// Pixels of left-click drag per slice advance.
const DRAG_SENSITIVITY: f32 = 10.0;
```

Then extend the `ViewerApp` struct to add three new fields:

```rust
pub struct ViewerApp {
    stack: Option<ImageStack>,
    texture: Option<egui::TextureHandle>,
    texture_idx: Option<usize>,
    /// Accumulated wheel delta; consumed in WHEEL_SENSITIVITY chunks per slice step.
    wheel_accum: f32,
    /// Accumulated left-click drag dy; consumed in DRAG_SENSITIVITY chunks per slice step.
    drag_accum: f32,
}
```

Update both `ViewerApp::new` and `ViewerApp::empty` constructors to initialize the new fields to `0.0`:

```rust
impl ViewerApp {
    #[must_use]
    pub fn new(stack: ImageStack) -> Self {
        Self {
            stack: Some(stack),
            texture: None,
            texture_idx: None,
            wheel_accum: 0.0,
            drag_accum: 0.0,
        }
    }

    #[must_use]
    pub fn empty() -> Self {
        Self {
            stack: None,
            texture: None,
            texture_idx: None,
            wheel_accum: 0.0,
            drag_accum: 0.0,
        }
    }
}
```

(Note: clippy may flag `missing_const_for_fn` on these constructors since they only do struct init. The slice-5 implementation marked the original two-field versions as candidates with `#[allow(clippy::missing_const_for_fn)]`. Now that the bodies have more lines and would still qualify, keep the same `#[allow]` if it was there, or add it. Behavior is unchanged.)

- [ ] **Step 2: Verify it compiles and tests pass**

```powershell
cargo build
cargo test
```

Expected: clean build, 27 tests still pass. The new fields aren't read by anything yet — that's Tasks 2 and 3.

- [ ] **Step 3: Commit**

```powershell
git add "basic PACS/rust_version/src/viewer.rs"
git commit -m "refactor(rust): add scroll sensitivity constants and accumulator state to ViewerApp"
```

---

## Task 2: Throttle wheel scroll with `WHEEL_SENSITIVITY` accumulator

Replace the current 1-slice-per-tick wheel handler with an accumulator-and-threshold pattern. Wheel-up advances one slice per +10 units of delta; wheel-down per -10 units. Leftover delta carries to the next event.

**Files:** Modify `basic PACS/rust_version/src/viewer.rs`

- [ ] **Step 1: Replace the wheel-handling block in `fn ui`**

Find the current wheel handler in `viewer.rs`. It looks like:

```rust
let wheel_y = ctx.input(|i| i.smooth_scroll_delta.y);
if let Some(stack) = self.stack.as_mut() {
    if wheel_y > 0.0 {
        stack.prev();
    } else if wheel_y < 0.0 {
        stack.next();
    }
}
```

Replace with:

```rust
// Accumulate wheel delta and consume in WHEEL_SENSITIVITY chunks so high-res wheels
// don't blow past slices. wheel_y > 0 = scroll up = previous slice (matches PACS).
let wheel_y = ctx.input(|i| i.smooth_scroll_delta.y);
if let Some(stack) = self.stack.as_mut() {
    self.wheel_accum += wheel_y;
    while self.wheel_accum >= WHEEL_SENSITIVITY {
        stack.prev();
        self.wheel_accum -= WHEEL_SENSITIVITY;
    }
    while self.wheel_accum <= -WHEEL_SENSITIVITY {
        stack.next();
        self.wheel_accum += WHEEL_SENSITIVITY;
    }
}
```

Note: the `while` loop (rather than `if`) handles a single wheel event that delivers multiple sensitivity-units worth of delta in one tick — common when the OS coalesces fast wheeling. Each loop iteration steps one slice.

The repaint logic at the bottom of `fn ui` should still trigger on `wheel_y != 0.0`. Keep it.

- [ ] **Step 2: Build and run tests**

```powershell
cargo build
cargo test
```

Expected: 27 tests still pass (no new tests; viewer.rs has no unit tests, only smoke-test by binary).

- [ ] **Step 3: Manual smoke-test (if you have a display)**

```powershell
cargo run --release --bin rustradstack -- "C:\Users\harwo\OneDrive\Documents\Radiology\basic PACS\rust_version\DICOM_test_files\series-000001"
```

Scroll the wheel — should now feel about 10× slower than before. One physical wheel "click" should advance one slice (most consumer mice produce ~100-120 delta units per click; with sensitivity 10 that's 10 slices per click... hmm).

> **Tuning note:** If 10 turns out to be too fast OR too slow on your hardware, the constant is a one-line edit in viewer.rs. Don't tune it in this task — get the mechanism right and the user can tune the value after manual testing.

If headless, just confirm `cargo build` succeeds; the wheel logic isn't testable in unit tests without a full egui harness.

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/src/viewer.rs"
git commit -m "feat(rust): throttle wheel scroll with WHEEL_SENSITIVITY accumulator"
```

---

## Task 3: Left-click drag scroll

Track left-mouse-button press/release. While held, accumulate `pointer.delta().y` and step slices in `DRAG_SENSITIVITY` chunks. Drag down = next slice, drag up = previous slice (matches Python's `_handle_scroll_drag`).

**Files:** Modify `basic PACS/rust_version/src/viewer.rs`

- [ ] **Step 1: Add the drag-handling block after wheel handling in `fn ui`**

After the wheel-handling block from Task 2 (and BEFORE the texture upload logic), add:

```rust
// Left-click drag = scroll. Accumulate dy while button held; consume in
// DRAG_SENSITIVITY chunks. Drag down = next slice (positive dy in egui coords).
if let Some(stack) = self.stack.as_mut() {
    let (button_down, dy) = ctx.input(|i| {
        let down = i.pointer.button_down(egui::PointerButton::Primary);
        let dy = if down { i.pointer.delta().y } else { 0.0 };
        (down, dy)
    });
    if button_down {
        self.drag_accum += dy;
        while self.drag_accum >= DRAG_SENSITIVITY {
            stack.next();
            self.drag_accum -= DRAG_SENSITIVITY;
        }
        while self.drag_accum <= -DRAG_SENSITIVITY {
            stack.prev();
            self.drag_accum += DRAG_SENSITIVITY;
        }
    } else {
        // Reset on release so the next drag starts fresh.
        self.drag_accum = 0.0;
    }
}
```

> **API note:** `i.pointer.delta()` returns the per-frame pointer movement as `egui::Vec2`. `i.pointer.button_down(egui::PointerButton::Primary)` returns whether the left button is currently held. If method names differ in eframe 0.34's egui (e.g., `is_pointer_button_down` instead), the compile error will say so — adjust to the available API. The semantic operation is "left button held + per-frame dy".

Also: ensure egui repaints continuously while dragging by adding `ctx.request_repaint()` if `button_down` is true. Without this, the drag would only register at the moments egui decides to repaint for other reasons (e.g., focus change), making slow drags feel laggy. Add this just before the existing wheel-driven repaint check or merge them:

```rust
// Request continuous repaint while wheel scrolling or dragging.
if wheel_y != 0.0 || ctx.input(|i| i.pointer.button_down(egui::PointerButton::Primary)) {
    ctx.request_repaint();
}
```

(Replace the existing wheel-only `if wheel_y != 0.0 { ctx.request_repaint(); }` with this combined version.)

- [ ] **Step 2: Build and run tests**

```powershell
cargo build
cargo test
```

Expected: 27 tests still pass.

- [ ] **Step 3: Manual smoke-test (if you have a display)**

```powershell
cargo run --release --bin rustradstack -- "C:\Users\harwo\OneDrive\Documents\Radiology\basic PACS\rust_version\DICOM_test_files\series-000001"
```

Press left mouse button on the image, drag down — should advance through slices. Drag up — should go back. Release the button — drag accumulator resets (so the next click starts fresh, doesn't carry leftover delta).

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/src/viewer.rs"
git commit -m "feat(rust): left-click drag scroll with DRAG_SENSITIVITY accumulator"
```

---

## Task 4: README + roadmap update

**Files:** Modify `basic PACS/rust_version/README.md`

- [ ] **Step 1: Update GUI usage section**

Find the existing `## GUI usage` section (after slice 5 it documents wheel scroll). Update the controls description to mention both interactions:

````markdown
## GUI usage

Open a single DICOM in a window:

```powershell
cargo run --bin rustradstack -- path\to\file.dcm
```

Open a folder of DICOMs and scroll through the stack:

```powershell
cargo run --bin rustradstack -- path\to\series\
```

**Controls:**
- **Mouse wheel** — navigate slices (~10 wheel units per slice)
- **Left-click drag (vertical)** — navigate slices (~10 pixels per slice; drag down = next slice)
- Status bar shows "Slice X / N"
````

(Use real triple-backtick markdown fences.)

- [ ] **Step 2: Update Roadmap**

Append a "post-MVP" line after the existing 5-slice list:

```markdown
1. ✅ Slice 1 — CLI prints DICOM tags
2. ✅ Slice 2 — `apply_window` + `rrs-cli render` writes PNG
3. ✅ Slice 3 — folder scan + DICOM sort + `rrs-cli list`
4. ✅ Slice 4 — egui window displays a single DICOM
5. ✅ Slice 5 — egui app loads a folder, mouse wheel scrolls
6. ✅ Slice 6 (this slice) — scroll polish: throttled wheel + left-click drag scroll

**MVP complete.** Future slices may add: drag-W/L controls (both-button drag), file menu, JPG/PNG support, W/L presets.
```

- [ ] **Step 3: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): README documents throttled wheel + drag scroll"
```

---

## Task 5: Clippy / refactor pass

Per the user's standing plan template. (Profile pass skipped — no perf-shaped change in this slice; scroll responsiveness will be assessed manually by the user.)

**Files:** likely just `basic PACS/rust_version/src/viewer.rs`

- [ ] **Step 1: Run clippy**

```powershell
cargo clippy --all-targets -- -W clippy::pedantic -W clippy::nursery
```

- [ ] **Step 2: Apply suggestions that improve clarity**

Pay attention to:
- The two `while ... -= SENSITIVITY` loops in the wheel handler — clippy may suggest a more idiomatic form (e.g., `let steps = (self.wheel_accum / WHEEL_SENSITIVITY).trunc() as i32;`). Apply if clearer; otherwise keep the loop form (it's explicit about what's happening).
- Same thing for the drag handler.
- The `#[allow(clippy::missing_const_for_fn)]` on `new` and `empty` may need to stay (struct init with new fields still qualifies).

Reject pedantic nits with targeted `#[allow(clippy::lint_name)]` + reason.

- [ ] **Step 3: Read `viewer.rs` with fresh eyes**

The file has grown — Task 1 added 2 fields + 2 lines per constructor; Task 2 replaced ~5 lines with ~12; Task 3 added ~15. The `fn ui` body is now denser. Consider whether the wheel and drag handlers should be extracted into private helper functions (`fn handle_wheel(&mut self, dy: f32)`, `fn handle_drag(&mut self, button_down: bool, dy: f32)`) for clarity. Apply if it actually reads better; skip if the inline form is fine.

- [ ] **Step 4: Confirm green**

```powershell
cargo test
cargo clippy --all-targets
```

Expected: 27 tests pass; clippy clean.

- [ ] **Step 5: Commit**

```powershell
git add "basic PACS/rust_version"
git commit -m "refactor(rust): clippy pass + readability cleanup for slice 6"
```

---

## Done criteria

- [ ] `cargo build --release` clean
- [ ] `cargo test` green — 27 tests
- [ ] `cargo clippy --all-targets` clean
- [ ] Manual scroll test (user): wheel feels ~10× slower than slice 5
- [ ] Manual drag test (user): left-click drag scrolls slices, releases cleanly
- [ ] README documents both controls

## Out of scope (for future slices)

- Both-button drag for W/L adjustment (Python has it; defer)
- Configurable sensitivity via CLI flag or settings file (defer until user asks)
- Right-click drag for pan (Python doesn't have; defer)
- Pinch zoom on touch devices (defer)
- Keyboard arrow key navigation (defer)
