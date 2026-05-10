# RustRadStack

A Rust port of [PyRadStack](../python_version/), a lightweight DICOM stack viewer.
Slice 1 ships a CLI; the GUI viewer lands in slice 4.

## Build

```powershell
cargo build --release
```

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

## CLI usage

Print key tags from a DICOM file:

```powershell
cargo run --bin rrs-cli -- info path\to\file.dcm
```

Output:

```
File:             path\to\file.dcm
PatientName:      Smith^John
Modality:         CT
InstanceNumber:   3
Rows x Cols:      512 x 512
WindowCenter:     40
WindowWidth:      400
RescaleSlope:     1
RescaleIntercept: 0
```

Render a DICOM as an 8-bit grayscale PNG (W/L from file's tags):

```powershell
cargo run --bin rrs-cli -- render path\to\file.dcm out.png
```

List DICOM files in a folder, sorted by InstanceNumber:

```powershell
cargo run --bin rrs-cli -- list path\to\series\
```

Output:

```
24 DICOM(s) in path\to\series\:
     1  image-000001.dcm
     2  image-000002.dcm
     ...
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

**MVP complete.** Future slices may add: drag-W/L controls, file menu, JPG/PNG support, W/L presets.

## Crate layout

- `src/lib.rs` — library entry; re-exports `errors` and `windowing`
- `src/errors.rs` — `RrsError`
- `src/loader.rs` — `scan_directory`
- `src/sorting.rs` — `sort_files`
- `src/stack.rs` — `ImageStack` data model
- `src/viewer.rs` — `ViewerApp` (egui)
- `src/windowing.rs` — `WindowSettings`, `read_metadata`, `extract_pixels`, `apply_window`
- `src/bin/rrs-cli.rs` — CLI binary
- `src/main.rs` — `rustradstack` GUI binary
- `tests/common/mod.rs` — synthetic DICOM builder
- `tests/*.rs` — integration tests

## Performance notes

Release-build, Windows, median of 3 runs:

| Operation | Synthetic 8×8 | Real MR 512×512 |
|---|---|---|
| `rrs-cli render` (full pipeline: open → decode → W/L → encode → write PNG) | ~20ms | ~39ms |
| `rrs-cli list` (24-file MR series, sort by InstanceNumber) | — | ~38ms |
| `rustradstack` GUI cold-start to image visible (real 512×512 MR) | — | binary load: ~80ms (no-args exit, before window creation; headless environment — window-open time not measurable) |
| `rustradstack` GUI scroll through 24-slice MR series | — | deferred to user manual test |

Hot path on real files: `decode_pixel_data` (decoding) and `image::save` (PNG encoding) dominate. The W/L pass is negligible. These numbers compare against later slices.

## Real-DICOM validation

Slice 2 was smoke-tested by rendering one slice from each of 6 anonymized
MR knee series (mix of 256×256 and 512×512, axial and sagittal). Resulting
PNGs displayed expected anatomy with correct W/L per file — no byte-order or
scaling artifacts. Real-data testing is currently manual; formal regression
tests against real files are deferred until a stable test-data location is
decided.
