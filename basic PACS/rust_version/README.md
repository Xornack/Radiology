# RustRadStack

A Rust port of [PyRadStack](../python_version/), a lightweight DICOM stack viewer.
Slice 1 ships a CLI; the GUI viewer lands in slice 4.

## Build

```powershell
cargo build --release
```

## CLI usage

Print key tags from a DICOM file:

```powershell
cargo run --bin rrs-cli -- info path\to\file.dcm
```

Output:

```
File:            path\to\file.dcm
PatientName:     Smith^John
Modality:        CT
InstanceNumber:  3
Rows x Cols:     512 x 512
WindowCenter:    40
WindowWidth:     400
RescaleSlope:    1
RescaleIntercept:-1024
```

## Tests

```powershell
cargo test
```

## Roadmap

See [the design spec](../docs/superpowers/specs/2026-05-08-rust-port-design.md). Slice plan:

1. **Slice 1 (this slice)** — CLI prints DICOM tags
2. Slice 2 — `apply_window` + `rrs-cli render` writes PNG
3. Slice 3 — folder scan + DICOM sort + `rrs-cli list`
4. Slice 4 — egui window displays a single DICOM
5. Slice 5 — egui app loads a folder, mouse wheel scrolls

## Crate layout

- `src/lib.rs` — library entry; re-exports `errors` and `windowing`
- `src/errors.rs` — `RrsError`
- `src/windowing.rs` — `WindowSettings`, `extract_pixels`
- `src/bin/rrs-cli.rs` — CLI binary
- `tests/common/mod.rs` — synthetic DICOM builder
- `tests/*.rs` — integration tests

## Performance notes

Slice 1 baseline (4x4 synthetic DICOM, release build, Windows):
- `cargo test --release --test cli_info`: ~20ms total, median of 3 runs.
- Hot path: `dicom_object::open_file` (file I/O + parse). Pixel decode is dominated by parser overhead at this size.

These numbers exist to compare against later slices. Real-world (512x512) latency will be measured when a real DICOM is wired in.
