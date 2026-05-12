# RustRadStack — Slice 7 Implementation Plan (both-button W/L drag)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute. Steps use `- [ ]` checkbox syntax.

**Goal:** Hold left + right mouse buttons together → drag adjusts Window/Level for the whole stack. dx (horizontal) controls window WIDTH, dy (vertical) controls window CENTER. Sensitivity matches PyRadStack's `_WL_SENSITIVITY = 3.0` units per pixel. Each new folder/file load resets the override back to per-file tag values.

**Architecture:** `ImageStack` gains an `override_window: Option<(f64, f64)>` field (center, width). `get_current_image` checks the override before reading per-file W/L tags. Cache key extends from `(idx,)` to `(idx, Option<(f64, f64)>)` — same cache slot, but invalidates when override changes. `ViewerApp` adds a `wl_dirty` flag to know when to invalidate the texture (separate from texture_idx since W/L changes don't change the slice index). Mouse handler tracks both-buttons-held state and accumulates dx/dy per frame.

**Tech Stack:** No new deps.

Working dir: `basic PACS/rust_version/` (worktree root: `basic PACS/.claude/worktrees/wl-drag/`).

---

## Task 1: Add `override_window` to `ImageStack` (TDD)

Pure data-model change. After this task `ImageStack` can hold an override but nothing reads it yet — Task 2 wires it through `get_current_image`.

**Files:**
- Modify: `basic PACS/rust_version/src/stack.rs`
- Modify: `basic PACS/rust_version/tests/stack.rs`

- [ ] **Step 1: Add a failing test**

Append to `tests/stack.rs`:

```rust
#[test]
fn image_stack_override_window_round_trips() {
    let dir = fresh_dir();
    let p = write_synthetic(dir.path(), "a.dcm", DicomFixture::default());
    let mut stack = ImageStack::new(vec![p]);

    assert_eq!(stack.override_window(), None);

    stack.set_override_window(Some((100.0, 500.0)));
    assert_eq!(stack.override_window(), Some((100.0, 500.0)));

    stack.set_override_window(None);
    assert_eq!(stack.override_window(), None);
}
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
cargo test --test stack
```

Expected: compile error (`no method named override_window` or `set_override_window`).

- [ ] **Step 3: Implement override field + accessors**

Modify `src/stack.rs`. Add a new field to `ImageStack`:

```rust
pub struct ImageStack {
    paths: Vec<PathBuf>,
    current: usize,
    cache: std::cell::RefCell<Option<(usize, GrayImage)>>,
    /// User-set W/L (center, width) overriding per-file DICOM tags.
    /// `None` means "use the file's tags" (default).
    override_window: Option<(f64, f64)>,
}
```

Initialize to `None` in `new`:

```rust
pub fn new(paths: Vec<PathBuf>) -> Self {
    Self {
        paths,
        current: 0,
        cache: std::cell::RefCell::new(None),
        override_window: None,
    }
}
```

Add the accessors below the existing methods:

```rust
#[must_use]
pub fn override_window(&self) -> Option<(f64, f64)> {
    self.override_window
}

/// Set the user override W/L (or `None` to revert to per-file tags).
/// Invalidates the cached image so the next `get_current_image` re-renders.
pub fn set_override_window(&mut self, ws: Option<(f64, f64)>) {
    self.override_window = ws;
    self.cache.borrow_mut().take();
}
```

Note the cache invalidation in `set_override_window` — without it, a wheeling-then-W/L-drag-then-wheel-back sequence would show the cached old-W/L image when revisiting a slice.

- [ ] **Step 4: Run — expect GREEN**

```powershell
cargo test --test stack
```

Expected: 5 stack tests pass (4 original + 1 new).

- [ ] **Step 5: Run full suite**

```powershell
cargo test
```

Expected: 28 tests pass (27 from before + 1 new stack test).

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/stack.rs" "basic PACS/rust_version/tests/stack.rs"
git commit -m "feat(rust): ImageStack carries optional W/L override"
```

---

## Task 2: Wire `override_window` into `get_current_image`

`get_current_image` currently calls `extract_pixels` (returns `WindowSettings` from file tags) → `apply_window`. Change it so an active override replaces the W/L parts of `WindowSettings` before calling `apply_window`. Slope/intercept stay as the per-file values (override doesn't touch rescale).

**Files:**
- Modify: `basic PACS/rust_version/src/stack.rs`
- Modify: `basic PACS/rust_version/tests/stack.rs`

- [ ] **Step 1: Add a failing test**

Append to `tests/stack.rs`:

```rust
#[test]
fn image_stack_get_current_image_uses_override_when_set() {
    let dir = fresh_dir();
    // File W/L: center=128, width=256, slope=1, intercept=0 (defaults from DicomFixture)
    let p = write_synthetic(
        dir.path(),
        "a.dcm",
        DicomFixture {
            window_center: Some(128.0),
            window_width: Some(256.0),
            rescale_slope: Some(1.0),
            rescale_intercept: Some(0.0),
            // pixel ramp 0..16 with the default 4x4 dims
            ..Default::default()
        },
    );
    let mut stack = ImageStack::new(vec![p]);

    let img_default = stack.get_current_image().expect("default render");

    // Tighten window to [60, 70] (center=65, width=10) — most ramp values clamp.
    stack.set_override_window(Some((65.0, 10.0)));
    let img_overridden = stack.get_current_image().expect("override render");

    // Default window covers the whole [0, 256] range; ramp 0..15 produces gentle
    // gradient bytes ~0..15. Override clamps everything below 60 to 0 and
    // everything above 70 to 255 — much higher contrast. The overridden image's
    // pixel sum should be very different from the default's.
    let sum_default: u32 = img_default.as_raw().iter().map(|&b| u32::from(b)).sum();
    let sum_overridden: u32 = img_overridden.as_raw().iter().map(|&b| u32::from(b)).sum();
    assert_ne!(
        sum_default, sum_overridden,
        "override should produce visibly different pixels (default sum={sum_default}, overridden sum={sum_overridden})"
    );
}
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
cargo test --test stack
```

Expected: the test compiles but fails — both renders produce the same pixels because `get_current_image` ignores the override.

- [ ] **Step 3: Wire override into `get_current_image`**

Modify the body of `get_current_image` in `src/stack.rs`. The current body looks like:

```rust
let path = &self.paths[self.current];
let obj = open_file(path).map_err(|e| RrsError::Dicom(e.to_string()))?;
let (pixels, dims, ws) = extract_pixels(&obj)?;
let img = apply_window(&pixels, dims, ws);
```

Change to:

```rust
let path = &self.paths[self.current];
let obj = open_file(path).map_err(|e| RrsError::Dicom(e.to_string()))?;
let (pixels, dims, mut ws) = extract_pixels(&obj)?;
// User-set override replaces only center+width; slope/intercept stay file-derived.
if let Some((center, width)) = self.override_window {
    ws.center = center;
    ws.width = width;
}
let img = apply_window(&pixels, dims, ws);
```

- [ ] **Step 4: Run — expect GREEN**

```powershell
cargo test --test stack
```

Expected: 6 stack tests pass.

- [ ] **Step 5: Run full suite**

```powershell
cargo test
```

Expected: 29 tests pass.

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/stack.rs" "basic PACS/rust_version/tests/stack.rs"
git commit -m "feat(rust): ImageStack::get_current_image honors override W/L"
```

---

## Task 3: Both-button W/L drag in `ViewerApp`

Track when both Primary and Secondary buttons are held simultaneously. While both held: accumulate dx and dy from `pointer.delta()`, multiply by sensitivity, apply to override (center += dy * 3.0, width += dx * 3.0; clamp width to ≥1 to avoid degenerate window). Initial override values come from the current `ws` of the displayed slice — so the user starts dragging from where the file's W/L is.

**Files:** Modify `basic PACS/rust_version/src/viewer.rs`

- [ ] **Step 1: Add the W/L sensitivity constant + drag-base state**

Near the existing `WHEEL_SENSITIVITY` and `DRAG_SENSITIVITY` constants in `src/viewer.rs`, add:

```rust
/// W/L drag sensitivity — units of W/L per pixel of mouse motion.
/// Matches PyRadStack's `_WL_SENSITIVITY = 3.0`.
const WL_SENSITIVITY: f64 = 3.0;
```

(Note: `f64`, not `f32` — W/L values are f64 throughout the windowing pipeline.)

No new state field needed in `ViewerApp` for the W/L drag — we'll mutate `stack.override_window` directly each frame both buttons are held. The accumulator pattern from wheel/scroll isn't needed here because W/L changes are continuous (every pixel of motion changes W/L), not chunked.

- [ ] **Step 2: Add the W/L drag handler**

After the existing wheel + drag-scroll handlers in `fn ui` (and BEFORE the texture upload check), insert:

```rust
// Both-button drag = W/L adjustment. dx → width, dy → center.
// While both held, mutate stack.override_window each frame.
let (both_buttons_down, drag_delta) = ctx.input(|i| {
    let primary = i.pointer.button_down(egui::PointerButton::Primary);
    let secondary = i.pointer.button_down(egui::PointerButton::Secondary);
    let both = primary && secondary;
    let delta = if both { i.pointer.delta() } else { egui::Vec2::ZERO };
    (both, delta)
});
if both_buttons_down {
    if let Some(stack) = self.stack.as_mut() {
        // Read current W/L (override if set, otherwise file's tags from a fresh metadata read).
        // For simplicity, fall back to a midpoint default if metadata read fails (consistent
        // with extract_pixels' fallback behavior).
        let (current_center, current_width) = stack.override_window().unwrap_or_else(|| {
            current_file_window(stack).unwrap_or((128.0, 256.0))
        });
        let new_center = current_center + f64::from(drag_delta.y) * WL_SENSITIVITY;
        // Width: prevent degenerate (≤0); also clamp upward at a sane max so users can
        // recover from runaway drags. 1.0..=100_000.0 covers MR (1..15000) and CT (1..4000).
        let new_width = (current_width + f64::from(drag_delta.x) * WL_SENSITIVITY)
            .clamp(1.0, 100_000.0);
        stack.set_override_window(Some((new_center, new_width)));
    }
}
```

Then add this private free function below the `impl eframe::App` block (or near the existing `handle_wheel`/`handle_drag` helpers if they exist):

```rust
/// Read the current slice's W/L from its DICOM tags. Returns None if the file
/// can't be opened or metadata can't be read.
fn current_file_window(stack: &ImageStack) -> Option<(f64, f64)> {
    use dicom_object::open_file;
    use rustradstack::windowing::read_metadata;

    let path = stack.current_path()?;
    let obj = open_file(path).ok()?;
    let (_dims, ws) = read_metadata(&obj).ok()?;
    Some((ws.center, ws.width))
}
```

> **Note:** This requires a new `current_path` accessor on `ImageStack`. We'll add it in this task.

> **`use dicom_object::open_file`:** This is at function scope to avoid polluting the file's top-level imports. If clippy complains, hoist it to the top.

- [ ] **Step 3: Add `ImageStack::current_path`**

In `src/stack.rs`, add this accessor near the existing `current()`:

```rust
/// Path of the current slice, or `None` if the stack is empty.
#[must_use]
pub fn current_path(&self) -> Option<&std::path::Path> {
    self.paths.get(self.current).map(|p| p.as_path())
}
```

- [ ] **Step 4: Update repaint trigger**

Find the existing repaint check (probably triggers on wheel, drag-scroll, etc.). Add `both_buttons_down` to it:

```rust
if wheel_y != 0.0 || drag_button_down || both_buttons_down {
    ctx.request_repaint();
}
```

- [ ] **Step 5: Build + tests**

```powershell
cargo build
cargo test
```

Expected: 29 tests still pass. The W/L drag isn't unit-tested (GUI behavior).

- [ ] **Step 6: Smoke-test (if you have a display)**

```powershell
cargo run --release --bin rustradstack -- "C:\Users\harwo\OneDrive\Documents\Radiology\basic PACS\rust_version\DICOM_test_files\series-000001"
```

Hold left + right mouse buttons together, drag:
- Drag right → width increases (more contrast range, softer image)
- Drag left → width decreases (narrower contrast, harder edges)
- Drag down → center increases (brighter midtones)
- Drag up → center decreases (darker midtones)

Release either button → drag stops cleanly. Wheel scroll should still work; previous-slice scrolling shouldn't reset the W/L override.

- [ ] **Step 7: Commit**

```powershell
git add "basic PACS/rust_version/src/viewer.rs" "basic PACS/rust_version/src/stack.rs"
git commit -m "feat(rust): both-button drag adjusts W/L (matches PyRadStack)"
```

---

## Task 4: Reset override on new folder load

Currently the GUI binary doesn't have a "load new folder" path — it loads at startup and that's it. Slice 8 will add a File → Open Folder menu. For now, the only relevant case is: if a user constructs a new `ImageStack` (only happens at process startup currently), the override starts at None. That's already true via `ImageStack::new`'s initialization in Task 1. **No code change needed for this task — it's a verification step.**

- [ ] **Step 1: Confirm via existing test**

The `image_stack_override_window_round_trips` test from Task 1 already asserts `stack.override_window()` is None on a freshly-constructed stack. That covers the "new folder = fresh override" invariant for slice 7's scope.

When slice 8 adds the File → Open Folder dialog, that slice's plan should include a step: when swapping the stack, the new stack's override is None by construction (no extra work needed), and the texture cache should also be invalidated (which happens naturally because `ViewerApp::new` creates a fresh ViewerApp).

**No commit for this task** — it's an analysis/verification step. Move directly to Task 5.

---

## Task 5: README + clippy pass

**Files:** `basic PACS/rust_version/README.md`, possibly `src/viewer.rs` and `src/stack.rs` for clippy fixes.

- [ ] **Step 1: Update README Controls section**

Find the existing `**Controls:**` block in `## GUI usage`. Add a third bullet:

```markdown
**Controls:**
- **Mouse wheel** — navigate slices (~10 wheel units per slice)
- **Left-click drag (vertical)** — navigate slices (~10 pixels per slice; drag down = next slice)
- **Both-button drag** — adjust Window/Level (drag right/left = width, drag down/up = center)
- Status bar shows "Slice X / N"
```

Update the roadmap to mark slice 7 done:

```markdown
1. ✅ Slice 1 — CLI prints DICOM tags
2. ✅ Slice 2 — `apply_window` + `rrs-cli render` writes PNG
3. ✅ Slice 3 — folder scan + DICOM sort + `rrs-cli list`
4. ✅ Slice 4 — egui window displays a single DICOM
5. ✅ Slice 5 — egui app loads a folder, mouse wheel scrolls
6. ✅ Slice 6 — scroll polish: throttled wheel + left-click drag scroll
7. ✅ Slice 7 (this slice) — both-button drag adjusts W/L

**MVP+ in progress.** Future slices: file menu (Open Folder dialog), JPG/PNG support, Nuitka build, W/L presets.
```

- [ ] **Step 2: Commit README**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): README documents both-button W/L drag (slice 7)"
```

- [ ] **Step 3: Clippy pass**

```powershell
cargo clippy --all-targets -- -W clippy::pedantic -W clippy::nursery
```

Apply fixes that improve clarity. Pay attention to:
- `current_file_window` is a free function with implicit dependency on `rustradstack::windowing::read_metadata`. Clippy may flag the function-scope `use` statements; that's fine to allow (keeps top-level imports tidy).
- The override-write-on-every-frame approach in the W/L handler can trigger redundant cache invalidation. If clippy flags it, suppress with reason — the cost is one tombstone-write per drag frame, negligible.
- `ImageStack::current_path` returning `Option<&Path>` should be straightforward; check `must_use` is correct.

Confirm:

```powershell
cargo test
cargo clippy --all-targets
```

Expected: 29 tests pass, clippy clean.

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version"
git commit -m "refactor(rust): clippy pass + readability cleanup for slice 7"
```

---

## Done criteria

- [ ] `cargo build --release` clean
- [ ] `cargo test` green — 29 tests (7 unit + 22 integration: 5 in cli_*, 1 fixture_smoke, 4 loader, 4 sorting, 6 stack now, 2 windowing)
- [ ] `cargo clippy --all-targets` clean
- [ ] Manual smoke test: both-button drag adjusts W/L visibly; wheel scroll still works; switching slices preserves the override
- [ ] README documents both-button drag

## Out of scope (for slice 8/9)

- File menu / Open Folder dialog (slice 8)
- JPG/PNG support (slice 9)
- W/L presets (lung/bone/abdomen) — defer
- Reset-W/L keyboard shortcut — defer
