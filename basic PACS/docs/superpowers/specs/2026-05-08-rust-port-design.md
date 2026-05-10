# PyRadStack → Rust Port (RustRadStack)

**Date:** 2026-05-08
**Status:** Approved for planning
**Author:** Matthew Harwood (with Claude Code)

## Problem

`PyRadStack` is a working Python/PyQt6 DICOM stack viewer (~300 LOC) — it loads a folder of DICOM/PNG/JPEG images, sorts DICOMs by `InstanceNumber`, applies Window/Level using DICOM tags, and lets the user scroll slices and adjust W/L by mouse. We want a Rust port. Goal is a working real Rust project, not a deep Rust learning exercise — we'll lean on existing crates rather than re-implementing parsers or GUIs from scratch.

## Non-goals

- A full-featured PACS or DICOM authoring tool.
- Network protocols (DICOMweb, DIMSE).
- Multi-series, multi-monitor, MPR/3D, measurements, annotations.
- A custom DICOM parser (we use `dicom-rs`).
- Compressed transfer syntax support beyond what `dicom-rs` already handles.
- Feature-parity at MVP — we ship a tight MVP first, then layer features back.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| DICOM library | `dicom-rs` (`/enet4/dicom-rs`) | Pure-Rust, well-maintained, covers tag access + pixel data + most transfer syntaxes. Skips months of parser work. |
| GUI framework | `egui` | Immediate-mode redraw maps cleanly to "wheel scrolled → advance slice → repaint". Built-in image display. Smallest learning curve and least boilerplate. |
| Image crate | `image` | `GrayImage` (`ImageBuffer<Luma<u8>, Vec<u8>>`) is the natural carrier for windowed pixel output. Easy to write to PNG and to convert to `egui::ColorImage`. |
| Errors | `thiserror` for the library; `anyhow` for binaries | Standard Rust split: precise error types in libs, ergonomic top-level handling in binaries. |
| Test data | Synthetic DICOMs built in-test via `dicom-rs` builders + `tempfile::TempDir` | Mirrors the Python `conftest.py` strategy. Drop in real DICOMs later when needed. |
| Rust edition | 2024 | Current stable. |
| Project layout | `basic PACS/rust_version/` (sibling of `python_version/`) | Keeps the comparison clean; same parent dir. |
| Crate name | `rustradstack` | Mirrors `pyradstack`. |

## Architecture

### Crate layout

```
basic PACS/rust_version/
├── Cargo.toml
├── README.md
└── src/
    ├── lib.rs              # re-exports the modules below
    ├── errors.rs           # RrsError enum
    ├── loader.rs           # scan_directory()
    ├── sorting.rs          # sort_files() with InstanceNumber + IPP fallback
    ├── windowing.rs        # apply_window(), extract_pixels(), WindowSettings
    ├── stack.rs            # ImageStack data model
    ├── viewer.rs           # egui app (added in slice 4)
    ├── main.rs             # GUI binary entry point (added in slice 4)
    └── bin/
        └── rrs-cli.rs      # CLI binary, slices 1–3
└── tests/
    ├── common/mod.rs       # synthetic DICOM builder helpers
    ├── loader.rs
    ├── sorting.rs
    └── windowing.rs
```

- One library + two binaries in one crate. CLI (`rrs-cli`) and GUI (`rustradstack`) both call into `lib.rs`.
- Module names mirror Python so the ports read side-by-side.
- Inline `#[cfg(test)] mod tests` for pure-function unit tests; cross-module / fixture-heavy tests go in `tests/`.

### Core types

```rust
// loader.rs
pub fn scan_directory(dir: &Path) -> io::Result<Vec<PathBuf>>;

// sorting.rs
pub fn sort_files(paths: Vec<PathBuf>) -> Vec<PathBuf>;

// windowing.rs
pub struct WindowSettings { pub center: f64, pub width: f64, pub slope: f64, pub intercept: f64 }
pub fn apply_window(pixels: &[i32], dims: (u32, u32), w: WindowSettings) -> GrayImage;
pub fn extract_pixels(path: &Path) -> Result<(Vec<i32>, (u32, u32), WindowSettings), RrsError>;

// stack.rs
pub struct ImageStack {
    paths: Vec<PathBuf>,
    current: usize,
    override_window: Option<(f64, f64)>,  // user-adjusted W/L overrides DICOM tags
}
impl ImageStack {
    pub fn new(paths: Vec<PathBuf>) -> Self;
    pub fn len(&self) -> usize;
    pub fn current_slice(&self) -> usize;
    pub fn next_slice(&mut self) -> usize;
    pub fn prev_slice(&mut self) -> usize;
    pub fn set_slice(&mut self, i: usize) -> usize;
    pub fn get_image(&self, i: usize) -> Result<GrayImage, RrsError>;
}
```

- Pixels held as `i32` internally (DICOM stored values are 8/12/16-bit, can be signed). Float math only inside `apply_window`.
- `WindowSettings` bundles the four numbers that travel together; avoids long parameter lists.
- `ImageStack` owns paths and slice index. User-set W/L is `Option`-typed so we can fall back to per-slice DICOM tags when not overridden (matches Python).

### Data flow

```
folder path
   ↓ loader::scan_directory
Vec<PathBuf>
   ↓ sorting::sort_files
Vec<PathBuf>  (DICOMs first by InstanceNumber/IPP, others by name)
   ↓ ImageStack::new
ImageStack
   ↓ get_image(i)
windowing::extract_pixels (i32 + dims + tag-derived WindowSettings)
   ↓ windowing::apply_window
GrayImage (u8)
   ↓ slice 4+: convert to egui::ColorImage and upload as a TextureHandle
on screen
```

One-way pipeline; each stage is independently testable.

### Error handling

```rust
#[derive(thiserror::Error, Debug)]
pub enum RrsError {
    #[error("I/O: {0}")] Io(#[from] std::io::Error),
    #[error("DICOM: {0}")] Dicom(/* #[from] from dicom-rs's read-error type — exact name verified at implementation */ String),
    #[error("missing tag {0}")] MissingTag(&'static str),
    #[error("unsupported pixel format: {0}")] UnsupportedPixels(String),
}
```

- Library code returns `Result<_, RrsError>` for fallible ops.
- Binaries (`main.rs`, `rrs-cli.rs`) wrap with `anyhow::Result` for top-level display.
- Sort fallback (missing `InstanceNumber`) is *not* an error — sort key is `f64::INFINITY` and the file goes to the end, matching Python's `float("inf")` behavior.

### Testing strategy

- **Synthetic DICOM builder** in `tests/common/mod.rs` using `dicom_object::InMemDicomObject` + `dicom_core::DataElement` to write minimal valid DICOMs (PixelData + Rows/Columns/InstanceNumber/W-L tags) into `tempfile::TempDir`. Analog of Python `conftest.py`.
- **Inline unit tests** for pure functions (W/L math, sort ordering, scan filtering).
- **Integration tests** in `tests/` for end-to-end flows.
- **GUI tests deferred** — egui has a test harness but it's brittle; rely on manual smoke-test of the GUI binary, like the Python pytest-qt strategy effectively did.

## MVP scope

The MVP (slices 1–5) covers:

1. Recursive folder scan for `.dcm` files (no JPG/PNG yet).
2. DICOM sorting by `InstanceNumber`, fallback `ImagePositionPatient[2]`, fallback file order.
3. Window/Level using DICOM tags + `RescaleSlope`/`Intercept`.
4. Mouse-wheel slice navigation.
5. Status text "Slice X / N".
6. Lazy per-slice loading.

Out-of-MVP (later slices, separate plans):
- JPG/PNG support.
- Left-click drag = scroll slices.
- Both-button drag = adjust W/L.
- File menu / Open Folder dialog (MVP takes folder via CLI arg).
- W/L presets, thumbnail strip, keyboard shortcuts.

## Slicing plan

| # | Slice | Adds | Output |
|---|---|---|---|
| 1 | Cargo project + `windowing::extract_pixels` + CLI prints DICOM tags | `dicom-rs` integration, error type, synthetic-DICOM test fixture | `rrs-cli info file.dcm` prints PatientName, Rows, Cols, InstanceNumber, W/L, slope/intercept |
| 2 | `windowing::apply_window` + CLI writes PNG | W/L math, `image` crate | `rrs-cli render file.dcm out.png` |
| 3 | `loader::scan_directory` + `sorting::sort_files` + CLI lists ordered series | folder + sort modules | `rrs-cli list folder/` prints sorted file names |
| 4 | `ImageStack` + minimal egui window displays one DICOM | egui scaffold, `GrayImage → ColorImage` upload, `eframe` app skeleton | `cargo run -- file.dcm` opens a window with one DICOM |
| 5 | egui app loads a folder; mouse wheel scrolls; "Slice X/N" label | folder→stack wiring, wheel input handling, status text | MVP done — `cargo run -- folder/` is a working scrollable viewer |

Per the user's standing plan template: every implementation plan ends with a profiling pass and a dead-code / readability refactor pass. Each slice's plan will include those two final phases.

## Open questions / deferred decisions

- **CI:** Not in MVP. Add later if/when the repo gets a GitHub remote with PRs.
- **Packaging:** Not in MVP. The Python version uses Nuitka; the Rust binary is a `cargo build --release`. Distribution format (installer? portable exe?) deferred until v1.
- **Name in window title:** "RustRadStack" unless user wants something different.
- **Color images:** All current work is grayscale (DICOM CT/MR are typically single-channel). Color DICOMs (US, photographs) are out of MVP and will need a separate plan.
