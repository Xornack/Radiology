# RustRadStack — Slice 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute. Steps use `- [ ]` checkbox syntax.

**Goal:** Open an egui window via `eframe` that displays a single DICOM file. New binary `rustradstack` (the GUI), separate from `rrs-cli`. No mouse controls yet — just "I see the image."

**Architecture:** `eframe::App` impl in a new `src/viewer.rs` module owns a `Option<egui::TextureHandle>` for the current image. Texture is uploaded once at startup from a `GrayImage` produced by the slice-1/2/3 pipeline (open → extract → window). `src/main.rs` is the GUI binary entry: parses one DCM path arg, runs the pipeline, hands the resulting GrayImage to the app, calls `eframe::run_native`.

**Tech Stack:** `eframe = "0.31"` (which transitively pulls in `egui` and the windowing backend). No new lib code beyond `viewer.rs`.

Working dir: `basic PACS/rust_version/`.

---

## Task 1: Add `eframe` dependency

**Files:**
- Modify: `basic PACS/rust_version/Cargo.toml`

- [ ] **Step 1: Add the dep**

From `basic PACS/rust_version/`:

```powershell
cargo add eframe
```

Expected: `cargo add` reports a new entry. The version cargo picks should be the latest stable (0.31.x at time of writing). If the resolver picks something incompatible with `image = "0.25.6"` or other crates, accept whatever version cargo settles on.

- [ ] **Step 2: Verify the build still passes**

```powershell
cargo build
```

Expected: clean build. Adding `eframe` pulls in a lot of windowing backend code; first build will take a while. No source code uses it yet — the build just verifies the deps resolve.

- [ ] **Step 3: Commit**

```powershell
git add "basic PACS/rust_version/Cargo.toml" "basic PACS/rust_version/Cargo.lock"
git commit -m "build(rust): add eframe dep for slice-4 GUI binary"
```

---

## Task 2: `viewer::ViewerApp` skeleton

A minimal `eframe::App` that holds an optional `TextureHandle` and paints it centered. No interactions in this slice.

**Files:**
- Create: `basic PACS/rust_version/src/viewer.rs`
- Modify: `basic PACS/rust_version/src/lib.rs`

- [ ] **Step 1: Wire the new module**

In `src/lib.rs`, add:

```rust
pub mod viewer;
```

(Insert in alphabetical order between `sorting` and `windowing`.)

- [ ] **Step 2: Create `src/viewer.rs`**

```rust
//! egui-based image viewer.

use eframe::egui;
use image::GrayImage;

/// State for the GUI viewer. Holds at most one uploaded image.
pub struct ViewerApp {
    /// Pre-windowed grayscale image to display. `None` until set_image is called.
    pending: Option<GrayImage>,
    /// Cached GPU texture once uploaded.
    texture: Option<egui::TextureHandle>,
}

impl ViewerApp {
    #[must_use]
    pub fn new() -> Self {
        Self { pending: None, texture: None }
    }

    /// Provide the image to display. Texture upload happens on the next frame.
    pub fn set_image(&mut self, img: GrayImage) {
        self.pending = Some(img);
        self.texture = None;
    }
}

impl Default for ViewerApp {
    fn default() -> Self {
        Self::new()
    }
}

impl eframe::App for ViewerApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Upload pending image to a texture on the first frame after set_image.
        if let Some(img) = self.pending.take() {
            let (w, h) = img.dimensions();
            let pixels = img.into_raw();
            // egui ColorImage expects RGBA. Expand grayscale → RGBA by replicating.
            let rgba: Vec<u8> = pixels.iter().flat_map(|&v| [v, v, v, 255]).collect();
            let color_img = egui::ColorImage::from_rgba_unmultiplied([w as usize, h as usize], &rgba);
            self.texture = Some(ctx.load_texture("dicom-frame", color_img, egui::TextureOptions::default()));
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
        });
    }
}
```

> **API note:** egui's exact widget for displaying a texture varies slightly across 0.2x versions. `ui.image((tex.id(), size))` is the 0.27+ pattern. If your installed version is different, the compiler error usually says what to call instead. The semantic shape (load_texture → display) is what matters.

- [ ] **Step 3: Verify it compiles**

```powershell
cargo build --lib
```

Expected: clean. Tests don't exercise this module yet (GUI code is hard to test without an event loop; we'll smoke-test via the binary in Task 4).

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/src/lib.rs" "basic PACS/rust_version/src/viewer.rs"
git commit -m "feat(rust): viewer::ViewerApp egui skeleton with texture upload"
```

---

## Task 3: GUI binary entry point

**Files:**
- Create: `basic PACS/rust_version/src/main.rs`

- [ ] **Step 1: Create `src/main.rs`**

This is a NEW binary alongside `rrs-cli`. It opens a single DICOM passed as argv[1].

```rust
//! `rustradstack` GUI binary — slice 4 displays a single DICOM in an egui window.

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use anyhow::{anyhow, Context, Result};

use dicom_object::open_file;
use rustradstack::viewer::ViewerApp;
use rustradstack::windowing::{apply_window, extract_pixels};

const USAGE: &str = "Usage: rustradstack <FILE.dcm>";

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
    let dcm: PathBuf = env::args()
        .nth(1)
        .ok_or_else(|| anyhow!(USAGE))?
        .into();

    let obj = open_file(&dcm).with_context(|| format!("opening {}", dcm.display()))?;
    let (pixels, dims, ws) = extract_pixels(&obj)
        .with_context(|| format!("extracting pixels from {}", dcm.display()))?;
    let img = apply_window(&pixels, dims, ws);

    let mut app = ViewerApp::new();
    app.set_image(img);

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

> **API note:** The `eframe::run_native` callback signature changed across versions. In 0.27+ it returns `Result<Box<dyn App>, Box<dyn Error + Send + Sync>>`. If you get a type-mismatch on the closure, check `cargo doc -p eframe` for the current `AppCreator` signature.

- [ ] **Step 2: Build the GUI binary**

```powershell
cargo build --bin rustradstack
```

Expected: clean build. (May take a while on first build of `eframe`'s dependency tree.)

- [ ] **Step 3: Manually smoke-test the binary**

```powershell
cargo run --bin rustradstack -- "DICOM_test_files\series-000001\image-000001.dcm"
```

Expected: a window pops up titled "RustRadStack" with the MR knee image displayed centered. Close the window to exit.

If the window opens blank or shows "(no image loaded)", check:
- The texture upload happened (add a `eprintln!` in the `if let Some(img)` block)
- The `ColorImage` dimensions match the image dims
- The widget call (`ui.image(...)`) matches your egui version's API

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/src/main.rs"
git commit -m "feat(rust): rustradstack GUI binary opens single DICOM in egui window"
```

---

## Task 4: README + roadmap update

**Files:**
- Modify: `basic PACS/rust_version/README.md`

- [ ] **Step 1: Add a GUI section before the existing CLI usage**

Add a new section just below the `## Build` section:

````markdown
## GUI usage

Open a single DICOM in a window:

```powershell
cargo run --bin rustradstack -- path\to\file.dcm
```

Slice 4 displays the image; mouse-wheel scrolling and folder loading land in slice 5.
````

- [ ] **Step 2: Update Roadmap**

```markdown
1. ✅ Slice 1 — CLI prints DICOM tags
2. ✅ Slice 2 — `apply_window` + `rrs-cli render` writes PNG
3. ✅ Slice 3 — folder scan + DICOM sort + `rrs-cli list`
4. **Slice 4 (this slice)** — egui window displays a single DICOM
5. Slice 5 — egui app loads a folder, mouse wheel scrolls
```

- [ ] **Step 3: Update Crate layout**

Add the two new entries:

```markdown
- `src/viewer.rs` — `ViewerApp` (egui)
- `src/main.rs` — `rustradstack` GUI binary
```

(Insert `viewer.rs` between `sorting.rs` and `windowing.rs`, then `main.rs` after `bin/rrs-cli.rs`.)

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): README documents rustradstack GUI binary"
```

---

## Task 5: Profiling pass

This slice's perf concern is "how long until the window appears with the image." Subjective but measurable with the test pipeline (synthetic DICOM end-to-end including eframe init is too slow to unit-test, but we can time the headless pre-GUI pipeline).

- [ ] **Step 1: Build release**

```powershell
cargo build --release --bin rustradstack
```

Expected: clean release build. Slow first time — many crates compile.

- [ ] **Step 2: Manually time "click to image visible" on a real DICOM**

```powershell
.\target\release\rustradstack.exe "DICOM_test_files\series-000001\image-000001.dcm"
```

Note subjective: how long between hitting Enter and the image appearing? On a modern machine with a 512×512 MR slice, expect <1s.

- [ ] **Step 3: Update README perf table**

Append a new row to the existing perf table:

```markdown
| `rustradstack` GUI cold-start to image visible (real 512×512 MR) | — | ~XXms |
```

Replace `~XXms` with a rough subjective estimate (e.g. "~500ms" or "instant"). This is informal — the GUI's perceived performance includes window-system latency that's hard to measure precisely.

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "perf(rust): record slice-4 GUI cold-start subjective timing"
```

---

## Task 6: Clippy / refactor pass

- [ ] **Step 1: Run clippy**

```powershell
cargo clippy --all-targets -- -W clippy::pedantic -W clippy::nursery
```

- [ ] **Step 2: Apply suggestions that improve clarity**

Pay attention to:
- `viewer.rs` — the RGBA expansion might be flagged for an `iter().flat_map()` chain. If clippy suggests a more efficient form, take it.
- `main.rs` — error handling is idiomatic anyhow; few changes likely.

- [ ] **Step 3: Confirm green**

```powershell
cargo test
cargo clippy --all-targets
```

Expected: 24 tests still pass (no new tests in this slice — viewer is GUI code, smoke-tested manually); clippy clean.

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version"
git commit -m "refactor(rust): clippy pass + readability cleanup for slice 4"
```

---

## Done criteria

- [ ] `cargo build --release --bin rustradstack` clean
- [ ] `cargo test` still green (24 tests; no new tests in this slice)
- [ ] `cargo clippy --all-targets` clean
- [ ] `cargo run --bin rustradstack -- <file.dcm>` opens a window showing the DICOM
- [ ] README documents the GUI binary; slice 4 marked current

## Out of scope (for slice 5)

- Folder loading (slice 5)
- Mouse wheel scroll (slice 5)
- ImageStack model (slice 5)
- W/L drag controls (later)
- File menu / Open Folder dialog (later)
- Pan/zoom (later)
