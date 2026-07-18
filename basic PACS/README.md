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

Open a study ("jacket") folder containing several series:

```powershell
cargo run -- path\to\study\
```

The window opens maximized, scales images to fit (preserving aspect ratio), and
shows the loaded folder name in the title bar.

**Studies, series strip, and viewports:** every load is treated as a study. Files
are grouped into series by `SeriesInstanceUID` (falling back to their folder), and
each series gets a thumbnail (its center slice) in the strip along the top, labelled
with the series description and slice count. The first series are hung into the
viewports automatically.

- **Layout buttons (1, 1×2, 2×2)** in the toolbar switch between one, two, or four
  viewports. Each viewport scrolls and windows independently.
- **Double-click a thumbnail** to hang that series in the active viewport;
  **drag a thumbnail onto any viewport** to hang it there (the target highlights).
- **Click a viewport** to make it active (accent border). Keyboard actions —
  presets, Esc, Del — go to the active viewport; the wheel scrolls whichever
  viewport the pointer is over.
- Tiles outlined in the strip are currently hung in a visible viewport.

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

**Loading:** use **File → Open Study…** (folder picker — every series inside is
loaded), **File → Open Folder…**, or **File → Open File…**. Window/Level resets to
per-file defaults on each load. If existing measurements would be discarded — by a
new study or by hanging a different series into a measured viewport — a confirmation
is asked first (measurements are not saved).

**Supported file types:** DICOM (`.dcm`), plus JPG/JPEG/PNG (rendered as 8-bit grayscale;
the W/L override acts as a brightness/contrast adjustment). Folders are scanned
recursively; DICOMs group into series by `SeriesInstanceUID` and sort by InstanceNumber
(falling back to `ImagePositionPatient` Z), non-DICOMs group per folder and sort
alphabetically. Series order follows `SeriesNumber`.

**Demo study:** generate a synthetic 4-series study for playing with the multi-viewport
features:

```powershell
cargo test --test gen_demo -- --ignored --nocapture
cargo run -- $env:TEMP\rrs_demo_study
```

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
10. ✅ Slice 10 — W/L presets (number keys 1–6) + status bar shows active preset
11. ✅ Measurement tools (line / ortho / circle ROI with HU stats) + review-fix hardening
12. ✅ Studies: multi-series jackets, thumbnail strip with drag-and-drop, 1×2 and 2×2 viewport layouts

**MVP+ in progress.** Future ideas: measurement export/persistence, viewer linking
(synchronized scroll), cargo packaging, recent-files list.

## Crate layout

- `src/lib.rs` — library entry; re-exports `errors` and `windowing`
- `src/errors.rs` — `RrsError`
- `src/loader.rs` — `scan_directory`
- `src/study.rs` — `Study`/`Series` + `load_study` (scan → group by SeriesInstanceUID → sort)
- `src/presets.rs` — `WindowPreset` + `PRESETS` (canonical CT W/L list)
- `src/stack.rs` — `ImageStack` data model
- `src/viewer.rs` — `ViewerApp` (egui): viewports, layouts, thumbnail strip
- `src/windowing.rs` — `WindowSettings`, `read_metadata`, `extract_pixels`, `apply_window`
- `src/main.rs` — `rustradstack` GUI binary (the only binary — plain `cargo run` works)
- `tests/common/mod.rs` — synthetic DICOM builder
- `tests/*.rs` — integration tests (`gen_demo` and `perf` are `--ignored` manual utilities)

## Performance notes

Hot path on real files: `decode_pixel_data` (decoding) dominates; the W/L pass is
negligible. (Historical slice-era numbers, measured through the since-removed
`rrs-cli`: full open → decode → W/L → PNG pipeline ~39ms on a real 512×512 MR.)

Study loading reads headers only (`read_until(PixelData)`), one pass per file for
grouping + sorting: 200 synthetic 256×256 slices across 4 series load in ~10ms vs
~20ms for full-file parses (larger real slices gain much more). Re-check with:

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
