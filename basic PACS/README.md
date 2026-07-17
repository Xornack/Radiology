# RustRadStack

A lightweight DICOM stack viewer (originally a Rust port of PyRadStack).

## Build

```powershell
cargo build --release
```

## Usage

Open the viewer with an empty window (load via File menu):

```powershell
cargo run
```

Open a single DICOM in a window:

```powershell
cargo run -- path\to\file.dcm
```

Open a folder of DICOMs and scroll through the stack:

```powershell
cargo run -- path\to\series\
```

The window opens maximized, scales the image to fit (preserving aspect ratio), and
shows the loaded folder name in the title bar.

**Controls:**
- **Mouse wheel** — navigate slices (~10 wheel units per slice)
- **Left-click drag (vertical)** — navigate slices (~10 pixels per slice; drag down = next slice)
- **Both-button drag** — adjust Window/Level (drag right/left = width, drag down/up = center)
- **Number keys 1–6** (or the **W/L menu**) — apply W/L preset:
  - 1 = Soft Tissue (C 40 / W 400)
  - 2 = Lung (C −600 / W 1500)
  - 3 = Bone (C 400 / W 1800)
  - 4 = Brain (C 40 / W 80)
  - 5 = Mediastinum (C 40 / W 350)
  - 6 = Liver (C 60 / W 160)
- **0** — clear preset / revert W/L to per-file DICOM tags
- **Measurement tools** (toolbar or hotkey): Pan/Scroll (**P**), 1D Line (**L**),
  2D Ortho (**O**), Circle ROI with HU stats (**C**). **Esc** cancels an in-progress
  measurement. Measurement labels can be dragged to reposition them.
- **Right-click** — select the nearest measurement (Shift adds to the selection);
  right-click drag draws a marquee selection box
- **Del / Backspace** — remove selected measurements ("Clear Slice" / "Clear All"
  buttons clear without a selection)
- Status bar shows "Slice X / N", the live W/L values (with the active preset name),
  and the pixel value under the cursor (HU when pixel spacing is available).

**Loading new series:** use **File → Open Folder…** or **File → Open File…** to switch
series mid-session. Native OS picker. Window/Level resets to per-file defaults on each
load. If the current series has measurements, loading a new one asks for confirmation
first (measurements are not saved).

**Supported file types:** DICOM (`.dcm`), plus JPG/JPEG/PNG (rendered as 8-bit grayscale;
the W/L override acts as a brightness/contrast adjustment). Mixed folders are supported;
DICOMs sort first by InstanceNumber, non-DICOMs alphabetically by filename. A folder that
directly contains images is loaded as one series — subfolders (sibling series) are only
scanned when the folder has no images of its own.

## Tests

```powershell
cargo test
```

## Roadmap

See [the design spec](../docs/superpowers/specs/2026-05-08-rust-port-design.md). Slice plan:

1. ✅ Slice 1 — CLI prints DICOM tags
2. ✅ Slice 2 — `apply_window` + `rrs-cli render` writes PNG
3. ✅ Slice 3 — folder scan + DICOM sort + `rrs-cli list`
4. ✅ Slice 4 — egui window displays a single DICOM
5. ✅ Slice 5 — egui app loads a folder, mouse wheel scrolls
6. ✅ Slice 6 — scroll polish: throttled wheel + left-click drag scroll
7. ✅ Slice 7 — both-button drag adjusts W/L
8. ✅ Slice 8 — File menu + Open Folder/File dialogs
9. ✅ Slice 9 — JPG/JPEG/PNG support in viewer + scan + sort
10. ✅ Slice 10 (this slice) — W/L presets (number keys 1–6) + status bar shows active preset

**MVP+ in progress.** Future slices: Nuitka-equivalent build (cargo packaging), recent-files list.

## Crate layout

- `src/lib.rs` — library entry; re-exports `errors` and `windowing`
- `src/errors.rs` — `RrsError`
- `src/loader.rs` — `scan_directory`
- `src/loading.rs` — `paths_for` (path → sorted Vec<PathBuf>)
- `src/presets.rs` — `WindowPreset` + `PRESETS` (canonical CT W/L list)
- `src/sorting.rs` — `sort_files`
- `src/stack.rs` — `ImageStack` data model
- `src/viewer.rs` — `ViewerApp` (egui)
- `src/windowing.rs` — `WindowSettings`, `read_metadata`, `extract_pixels`, `apply_window`
- `src/main.rs` — `rustradstack` GUI binary (the only binary — plain `cargo run` works)
- `tests/common/mod.rs` — synthetic DICOM builder
- `tests/*.rs` — integration tests

## Performance notes

Hot path on real files: `decode_pixel_data` (decoding) dominates; the W/L pass is
negligible. (Historical slice-era numbers, measured through the since-removed
`rrs-cli`: full open → decode → W/L → PNG pipeline ~39ms on a real 512×512 MR.)

Series-load sorting reads headers only (`read_until(PixelData)`): 200 synthetic
256×256 slices sort in ~7ms vs ~19ms for full-file parses (larger real slices gain
more). Re-check with:

```powershell
cargo test --release --test perf -- --ignored --nocapture
```

Recently viewed slices are kept in an LRU decode cache (~256 MB budget), so
scrubbing back and forth doesn't re-read files from disk.

## Real-DICOM validation

Slice 2 was smoke-tested by rendering one slice from each of 6 anonymized
MR knee series (mix of 256×256 and 512×512, axial and sagittal). Resulting
PNGs displayed expected anatomy with correct W/L per file — no byte-order or
scaling artifacts. Real-data testing is currently manual; formal regression
tests against real files are deferred until a stable test-data location is
decided.
