# RustRadStack — Slice 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute. Steps use `- [ ]` checkbox syntax.

**Goal:** Make the GUI take a folder of DICOMs, navigate slices with the mouse wheel, and display "Slice X / N" status text. End state: `cargo run --bin rustradstack -- folder/` opens a scrollable stack viewer. This completes the MVP.

**Architecture:** New `ImageStack` model in `src/stack.rs` owns `Vec<PathBuf>` + a current slice index + lazily-loaded image cache. `ViewerApp` from slice 4 grows: holds an `Option<ImageStack>` instead of a single image, handles `egui::Event::Scroll`, calls `stack.get_image(stack.current_slice())` on each navigation. Status text painted as an overlay in the central panel. Binary entry accepts both file and folder paths (file → 1-slice stack, folder → scanned + sorted stack).

**Tech Stack:** No new deps.

Working dir: `basic PACS/rust_version/`.

---

## Task 1: `ImageStack` data model

A small data structure holding sorted DICOM paths + a current index + a one-slot image cache so wheel scrolling doesn't re-decode the visible slice every frame.

**Files:**
- Create: `basic PACS/rust_version/src/stack.rs`
- Modify: `basic PACS/rust_version/src/lib.rs`
- Create: `basic PACS/rust_version/tests/stack.rs`

- [ ] **Step 1: Wire the new module**

In `src/lib.rs`, add `pub mod stack;` (in alphabetical order between `sorting` and `viewer`).

- [ ] **Step 2: Write failing tests**

Create `tests/stack.rs`:

```rust
mod common;

use common::{fresh_dir, write_synthetic, DicomFixture};
use rustradstack::stack::ImageStack;

#[test]
fn image_stack_reports_length_and_starts_at_index_0() {
    let dir = fresh_dir();
    let p1 = write_synthetic(dir.path(), "a.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    let p2 = write_synthetic(dir.path(), "b.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });

    let stack = ImageStack::new(vec![p1, p2]);
    assert_eq!(stack.len(), 2);
    assert_eq!(stack.current(), 0);
    assert!(!stack.is_empty());
}

#[test]
fn image_stack_next_and_prev_clamp_at_bounds() {
    let dir = fresh_dir();
    let p1 = write_synthetic(dir.path(), "a.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    let p2 = write_synthetic(dir.path(), "b.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });
    let p3 = write_synthetic(dir.path(), "c.dcm", DicomFixture { instance_number: Some(3), ..Default::default() });

    let mut stack = ImageStack::new(vec![p1, p2, p3]);
    assert_eq!(stack.next(), 1);
    assert_eq!(stack.next(), 2);
    assert_eq!(stack.next(), 2, "should clamp at last index");
    assert_eq!(stack.prev(), 1);
    assert_eq!(stack.prev(), 0);
    assert_eq!(stack.prev(), 0, "should clamp at first index");
}

#[test]
fn image_stack_get_current_image_returns_correct_dimensions() {
    let dir = fresh_dir();
    let p1 = write_synthetic(
        dir.path(),
        "a.dcm",
        DicomFixture { rows: Some(8), cols: Some(8), ..Default::default() },
    );
    let stack = ImageStack::new(vec![p1]);

    let img = stack.get_current_image().expect("get image");
    assert_eq!(img.dimensions(), (8, 8));
}

#[test]
fn image_stack_empty_reports_correctly() {
    let stack = ImageStack::new(vec![]);
    assert_eq!(stack.len(), 0);
    assert!(stack.is_empty());
}
```

- [ ] **Step 3: Run — expect FAIL**

```powershell
cargo test --test stack
```

Expected: compile error (`unresolved import rustradstack::stack::ImageStack`).

- [ ] **Step 4: Implement `src/stack.rs`**

```rust
//! Scrollable stack of DICOM slices with one-slot image cache.

use std::path::PathBuf;

use dicom_object::open_file;
use image::GrayImage;

use crate::errors::RrsError;
use crate::windowing::{apply_window, extract_pixels};

/// Sorted DICOM series with a current-slice cursor and one-slot image cache.
///
/// Slices are loaded on demand via `get_current_image`. The cache holds the most
/// recently loaded slice so repeated calls (e.g. across egui repaints) don't
/// re-decode the same file.
pub struct ImageStack {
    paths: Vec<PathBuf>,
    current: usize,
    cache: std::cell::RefCell<Option<(usize, GrayImage)>>,
}

impl ImageStack {
    #[must_use]
    pub fn new(paths: Vec<PathBuf>) -> Self {
        Self { paths, current: 0, cache: std::cell::RefCell::new(None) }
    }

    #[must_use]
    pub fn len(&self) -> usize {
        self.paths.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.paths.is_empty()
    }

    #[must_use]
    pub fn current(&self) -> usize {
        self.current
    }

    /// Advance one slice (saturating at last index). Returns the new index.
    pub fn next(&mut self) -> usize {
        if self.current + 1 < self.paths.len() {
            self.current += 1;
        }
        self.current
    }

    /// Go back one slice (saturating at 0). Returns the new index.
    pub fn prev(&mut self) -> usize {
        self.current = self.current.saturating_sub(1);
        self.current
    }

    /// Load the current slice (using the cache when possible).
    ///
    /// # Errors
    /// Returns `RrsError` if the underlying DICOM can't be opened or decoded.
    /// Returns an `RrsError::UnsupportedPixels` with the message "empty stack"
    /// if the stack contains no paths.
    pub fn get_current_image(&self) -> Result<GrayImage, RrsError> {
        if self.paths.is_empty() {
            return Err(RrsError::UnsupportedPixels("empty stack".into()));
        }

        // Cached?
        {
            let cache = self.cache.borrow();
            if let Some((idx, img)) = cache.as_ref() {
                if *idx == self.current {
                    return Ok(img.clone());
                }
            }
        }

        let path = &self.paths[self.current];
        let obj = open_file(path).map_err(|e| RrsError::Dicom(e.to_string()))?;
        let (pixels, dims, ws) = extract_pixels(&obj)?;
        let img = apply_window(&pixels, dims, ws);

        *self.cache.borrow_mut() = Some((self.current, img.clone()));
        Ok(img)
    }
}
```

> **Note on cache impl:** The `RefCell` lets `get_current_image(&self)` mutate the cache without requiring `&mut self`, which keeps the egui `update(...)` borrow rules tractable. Cloning the `GrayImage` from cache is a heap allocation (~256KB for 512×512); negligible at scroll speed but worth noting if profiling later flags it.

- [ ] **Step 5: Run — expect GREEN**

```powershell
cargo test --test stack
```

Expected: 4 tests pass.

- [ ] **Step 6: Run full suite**

```powershell
cargo test
```

Expected: 7 unit + 21 integration = 28 tests (4 new on top of slice-3's 24).

- [ ] **Step 7: Commit**

```powershell
git add "basic PACS/rust_version/src/lib.rs" "basic PACS/rust_version/src/stack.rs" "basic PACS/rust_version/tests/stack.rs"
git commit -m "feat(rust): ImageStack model with cursor + one-slot cache"
```

---

## Task 2: Update `ViewerApp` to take an `ImageStack`

Replace the single-image storage with a stack. Mouse wheel handling lands here too.

**Files:**
- Modify: `basic PACS/rust_version/src/viewer.rs`

- [ ] **Step 1: Rewrite `ViewerApp` to hold a stack**

Replace the slice-4 `ViewerApp` impl with:

```rust
//! egui-based image viewer.

use eframe::egui;

use crate::stack::ImageStack;

/// State for the GUI viewer. Holds a stack and the currently-uploaded texture.
pub struct ViewerApp {
    stack: Option<ImageStack>,
    texture: Option<egui::TextureHandle>,
    /// Index whose pixels are currently in `texture`. Re-upload when this != stack.current().
    texture_idx: Option<usize>,
}

impl ViewerApp {
    #[must_use]
    pub fn new(stack: ImageStack) -> Self {
        Self { stack: Some(stack), texture: None, texture_idx: None }
    }

    /// Construct an empty viewer (no stack). Used for error cases.
    #[must_use]
    pub fn empty() -> Self {
        Self { stack: None, texture: None, texture_idx: None }
    }
}

impl eframe::App for ViewerApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Handle mouse-wheel scroll. egui exposes scroll as part of input state.
        let wheel_y = ctx.input(|i| i.smooth_scroll_delta.y);
        if let Some(stack) = self.stack.as_mut() {
            if wheel_y > 0.0 {
                stack.prev();
            } else if wheel_y < 0.0 {
                stack.next();
            }
        }

        // Re-upload texture if the current slice changed.
        if let Some(stack) = &self.stack {
            let need_upload = self.texture_idx != Some(stack.current());
            if need_upload {
                if let Ok(img) = stack.get_current_image() {
                    let (w, h) = img.dimensions();
                    let pixels = img.into_raw();
                    let rgba: Vec<u8> = pixels.iter().flat_map(|&v| [v, v, v, 255]).collect();
                    let color_img = egui::ColorImage::from_rgba_unmultiplied(
                        [w as usize, h as usize],
                        &rgba,
                    );
                    self.texture = Some(ctx.load_texture(
                        "dicom-frame",
                        color_img,
                        egui::TextureOptions::default(),
                    ));
                    self.texture_idx = Some(stack.current());
                }
            }
        }

        egui::CentralPanel::default().show(ctx, |ui| {
            ui.vertical_centered(|ui| {
                if let Some(tex) = &self.texture {
                    let size = tex.size_vec2();
                    ui.image((tex.id(), size));
                } else {
                    ui.label("(no image loaded)");
                }
            });

            // Status bar: "Slice X / N"
            if let Some(stack) = &self.stack {
                let current = stack.current() + 1;
                let total = stack.len();
                ui.with_layout(
                    egui::Layout::bottom_up(egui::Align::Center),
                    |ui| ui.label(format!("Slice {current} / {total}")),
                );
            }
        });

        // Request a repaint when the wheel was scrolled (otherwise egui idles).
        if wheel_y != 0.0 {
            ctx.request_repaint();
        }
    }
}
```

> **Notes on egui input:**
> - `i.smooth_scroll_delta.y` is the integrated wheel delta on egui 0.27+. Some versions use `i.scroll_delta.y`. If your version differs, the compile error tells you what's available.
> - The convention of "wheel up = prev slice, wheel down = next slice" matches PyRadStack and standard PACS behavior. Some users prefer the opposite — that's a personal preference we'll surface as a flag in a future slice if anyone asks.

- [ ] **Step 2: Verify it compiles**

```powershell
cargo build --lib
```

Expected: clean. (No tests yet — viewer is GUI-only.)

- [ ] **Step 3: Commit**

```powershell
git add "basic PACS/rust_version/src/viewer.rs"
git commit -m "feat(rust): ViewerApp scrolls stack with mouse wheel + status text"
```

---

## Task 3: Update `main.rs` to accept folder argument

The GUI binary now takes either a single `.dcm` or a folder path. Folder → scan + sort → `ImageStack` → ViewerApp.

**Files:**
- Modify: `basic PACS/rust_version/src/main.rs`

- [ ] **Step 1: Replace `src/main.rs`**

```rust
//! `rustradstack` GUI binary — slice 5 loads a folder of DICOMs and scrolls them.

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use anyhow::{anyhow, Context, Result};

use rustradstack::loader::scan_directory;
use rustradstack::sorting::sort_files;
use rustradstack::stack::ImageStack;
use rustradstack::viewer::ViewerApp;

const USAGE: &str = "Usage:\n  rustradstack <FILE.dcm>\n  rustradstack <FOLDER>";

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("error: {e:#}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<()> {
    let arg: PathBuf = env::args()
        .nth(1)
        .ok_or_else(|| anyhow!(USAGE))?
        .into();

    let paths: Vec<PathBuf> = if arg.is_dir() {
        let scanned = scan_directory(&arg)
            .with_context(|| format!("scanning {}", arg.display()))?;
        sort_files(scanned)
    } else if arg.is_file() {
        vec![arg.clone()]
    } else {
        return Err(anyhow!("{} is neither a file nor a directory", arg.display()));
    };

    if paths.is_empty() {
        return Err(anyhow!("no DICOM files found in {}", arg.display()));
    }

    let stack = ImageStack::new(paths);
    let app = ViewerApp::new(stack);

    let options = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_inner_size([800.0, 600.0])
            .with_title("RustRadStack"),
        ..Default::default()
    };
    eframe::run_native(
        "RustRadStack",
        options,
        Box::new(|_cc| Ok(Box::new(app))),
    )
    .map_err(|e| anyhow!("eframe run_native failed: {e}"))
}
```

- [ ] **Step 2: Build**

```powershell
cargo build --bin rustradstack
```

Expected: clean.

- [ ] **Step 3: Smoke-test on a single file (regression check from slice 4)**

```powershell
cargo run --bin rustradstack -- "DICOM_test_files\series-000001\image-000001.dcm"
```

Expected: window opens, shows the image, "Slice 1 / 1" at the bottom. Wheel does nothing useful (one slice). Close to exit.

- [ ] **Step 4: Smoke-test on a folder (the main slice-5 deliverable)**

```powershell
cargo run --bin rustradstack -- "DICOM_test_files\series-000001"
```

Expected: window opens, shows image-000001.dcm, "Slice 1 / 24" at the bottom. **Scroll the mouse wheel** — should advance through all 24 slices, status updating, image swapping. Wheel up = previous slice. Should clamp at slice 1 and slice 24.

If scrolling doesn't work, check:
- The wheel-delta sign / threshold in `viewer.rs`
- Whether `ctx.request_repaint()` is being called
- The cache is being invalidated when `stack.current()` changes

- [ ] **Step 5: Commit**

```powershell
git add "basic PACS/rust_version/src/main.rs"
git commit -m "feat(rust): rustradstack GUI accepts folder, scrolls with mouse wheel"
```

---

## Task 4: README + roadmap update

- [ ] **Step 1: Update GUI usage section**

Replace the slice-4 GUI usage section with:

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

Mouse wheel navigates slices. Status bar shows "Slice X / N".
````

- [ ] **Step 2: Update Roadmap**

```markdown
1. ✅ Slice 1 — CLI prints DICOM tags
2. ✅ Slice 2 — `apply_window` + `rrs-cli render` writes PNG
3. ✅ Slice 3 — folder scan + DICOM sort + `rrs-cli list`
4. ✅ Slice 4 — egui window displays a single DICOM
5. ✅ Slice 5 — egui app loads a folder, mouse wheel scrolls

**MVP complete.** Future slices may add: drag-W/L controls, file menu, JPG/PNG support, W/L presets.
```

- [ ] **Step 3: Update Crate layout**

Add the `stack` line:

```markdown
- `src/stack.rs` — `ImageStack` data model
```

(Insert between `sorting.rs` and `viewer.rs`.)

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): README documents folder loading and scroll; MVP done"
```

---

## Task 5: Profiling pass

- [ ] **Step 1: Build release**

```powershell
cargo build --release --bin rustradstack
```

- [ ] **Step 2: Subjective scroll-latency test**

```powershell
.\target\release\rustradstack.exe "DICOM_test_files\series-000001"
```

Scroll quickly through all 24 slices. Subjective check:
- Does scrolling feel responsive (each wheel tick → visible slice change without lag)?
- Does the cache prevent re-decoding the same slice on repeated repaints (egui repaints often)?
- Any frame-rate drops or hitches?

If scrolling lags, the bottleneck is likely `extract_pixels` → `apply_window` per wheel event. Two optimizations to consider in future slices (NOT this one):
- Pre-decode all slices in the background after stack creation
- Cache a small ring buffer of recently-viewed slices instead of just one

- [ ] **Step 3: Update README perf table**

Append:

```markdown
| `rustradstack` GUI scroll through 24-slice MR series | — | subjective (record what you saw) |
```

Replace the right cell with a brief subjective note ("smooth", "noticeable lag", etc.).

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "perf(rust): record slice-5 GUI scroll responsiveness note"
```

---

## Task 6: Clippy / refactor pass

- [ ] **Step 1: Run clippy**

```powershell
cargo clippy --all-targets -- -W clippy::pedantic -W clippy::nursery
```

- [ ] **Step 2: Apply suggestions that improve clarity**

Pay attention to:
- `stack.rs` — the `RefCell` cache might trip `interior_mutability` lints. The pattern is justified for this use case; allow with a brief reason if necessary.
- `viewer.rs` — the RGBA expansion logic appears in both slice-4 and slice-5. If both still exist after this slice (they shouldn't — slice 5 replaces slice-4's `set_image`), de-dupe.

- [ ] **Step 3: Read each modified file with fresh eyes**

`src/stack.rs`, `src/viewer.rs`, `src/main.rs`, `tests/stack.rs`. Apply readability fixes inline.

- [ ] **Step 4: Confirm green**

```powershell
cargo test
cargo clippy --all-targets
```

Expected: 28 tests pass; clippy clean.

- [ ] **Step 5: Commit**

```powershell
git add "basic PACS/rust_version"
git commit -m "refactor(rust): clippy pass + readability cleanup for slice 5"
```

---

## Done criteria

- [ ] `cargo build --release` clean
- [ ] `cargo test` green — 28 tests (7 unit + 21 integration: 1 fixture_smoke, 2 windowing, 1 cli_info, 2 cli_render, 4 loader, 4 sorting, 2 cli_list, 4 stack)
- [ ] `cargo clippy --all-targets` clean
- [ ] `cargo run --bin rustradstack -- DICOM_test_files\series-000001` shows a window
- [ ] Mouse wheel scrolls through all 24 slices, image visibly changing
- [ ] Status bar shows "Slice X / N" updating with scroll
- [ ] Wheel clamps at slice 1 and slice 24 (no panic, no wrap-around)
- [ ] Single-file mode (`rustradstack file.dcm`) still works
- [ ] README marks all 5 slices done; "MVP complete"

## Out of scope (for post-MVP slices)

- Left-click drag to scroll slices (Python has it; defer)
- Both-button drag to adjust W/L (Python has it; defer)
- File menu / Open Folder dialog (Python has it; defer)
- JPG/PNG support in loader (descoped from MVP)
- W/L presets (lung/bone/abdomen)
- Pan/zoom
- Multi-series support
- Pre-decode worker thread
