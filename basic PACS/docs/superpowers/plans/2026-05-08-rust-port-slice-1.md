# RustRadStack — Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up a Rust crate that opens a DICOM file via `dicom-rs`, extracts pixel data + window/level metadata, and exposes a CLI (`rrs-cli info <file>`) that prints the same tags PyRadStack uses today (PatientName, Modality, Rows, Cols, InstanceNumber, W/L center & width, RescaleSlope, RescaleIntercept).

**Architecture:** Single Cargo crate at `basic PACS/rust_version/` with library + two binaries (CLI today, GUI in slice 4). Library exposes `windowing::extract_pixels(&Path) -> Result<(Vec<i32>, (u32, u32), WindowSettings), RrsError>`. CLI binary `rrs-cli` is a thin wrapper with a `info` subcommand.

**Tech Stack:** Rust 2024 edition, `dicom-object` + `dicom-dictionary-std` + `dicom-pixeldata` (for tag access and pixel decoding), `thiserror` (library errors), `anyhow` (binary errors), `tempfile` + synthetic DICOM builder (tests).

**Reference docs:** [Design spec](../specs/2026-05-08-rust-port-design.md). Working dir for all commands below: `basic PACS/rust_version/` (relative to the worktree root) unless stated otherwise.

---

## Task 1: Cargo project skeleton

**Files:**
- Create: `basic PACS/rust_version/Cargo.toml`
- Create: `basic PACS/rust_version/src/lib.rs`
- Create: `basic PACS/rust_version/src/bin/rrs-cli.rs`
- Create: `basic PACS/rust_version/.gitignore`

- [ ] **Step 1: Create the crate**

From the worktree root, run:

```powershell
New-Item -ItemType Directory -Path "basic PACS/rust_version" -Force | Out-Null
Set-Location "basic PACS/rust_version"
cargo init --lib --edition 2024 --name rustradstack
```

Expected: a `Cargo.toml`, `src/lib.rs`, and `.gitignore` are created. (`cargo init` reuses the current directory.)

- [ ] **Step 2: Add the runtime dependencies**

Run (still in `basic PACS/rust_version/`):

```powershell
cargo add dicom-object dicom-dictionary-std dicom-pixeldata
cargo add thiserror anyhow
cargo add image
```

Expected: `cargo add` reports new entries written to `Cargo.toml`. Versions are whatever is current on crates.io; we don't pin until we hit a real incompatibility.

- [ ] **Step 3: Add the dev-only test dependencies**

```powershell
cargo add --dev tempfile
cargo add --dev dicom-core dicom-encoding
```

(`dicom-core` and `dicom-encoding` are needed by the synthetic-DICOM builder in Task 3 — for constructing `DataElement`s and writing them out.)

Expected: new `[dev-dependencies]` section in `Cargo.toml`.

- [ ] **Step 3a: Ensure `Cargo.lock` is committed**

`cargo init --lib` adds `Cargo.lock` to `.gitignore`. Because this crate also produces binaries, we want `Cargo.lock` checked in for reproducible builds. Edit `basic PACS/rust_version/.gitignore` and remove the `Cargo.lock` line if present. The file should look like:

```
/target
```

- [ ] **Step 4: Replace `src/lib.rs` with module declarations**

Overwrite `src/lib.rs` with:

```rust
//! RustRadStack — DICOM stack viewer library.

pub mod errors;
pub mod windowing;

pub use errors::RrsError;
```

- [ ] **Step 5: Create the CLI binary stub**

Create `src/bin/rrs-cli.rs` containing:

```rust
fn main() {
    println!("rrs-cli — coming soon");
}
```

- [ ] **Step 6: Verify the build**

```powershell
cargo build
```

Expected: clean build, no errors. (Will warn about empty modules — that's fine; they get filled in next.)

- [ ] **Step 7: Commit**

```powershell
git add "basic PACS/rust_version/Cargo.toml" "basic PACS/rust_version/Cargo.lock" "basic PACS/rust_version/src" "basic PACS/rust_version/.gitignore"
git commit -m "feat(rust): cargo skeleton for rustradstack with dicom-rs deps"
```

---

## Task 2: Error type + WindowSettings type

**Files:**
- Create: `basic PACS/rust_version/src/errors.rs`
- Create: `basic PACS/rust_version/src/windowing.rs`

- [ ] **Step 1: Create `src/errors.rs`**

```rust
//! Library-wide error type.

use std::io;

#[derive(thiserror::Error, Debug)]
pub enum RrsError {
    #[error("I/O error: {0}")]
    Io(#[from] io::Error),

    #[error("DICOM error: {0}")]
    Dicom(String),

    #[error("missing DICOM tag: {0}")]
    MissingTag(&'static str),

    #[error("unsupported pixel format: {0}")]
    UnsupportedPixels(String),
}
```

We use `String` for the `Dicom` variant rather than wrapping a specific dicom-rs error type — this avoids coupling our error to a particular dicom-rs version's error layout. Call sites convert with `.map_err(|e| RrsError::Dicom(e.to_string()))`.

- [ ] **Step 2: Create `src/windowing.rs` with the `WindowSettings` struct**

```rust
//! DICOM window/level math and pixel extraction.

/// Window/Level + rescale parameters needed to convert stored pixel values
/// to a displayable 8-bit image.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct WindowSettings {
    pub center: f64,
    pub width: f64,
    pub slope: f64,
    pub intercept: f64,
}

impl Default for WindowSettings {
    fn default() -> Self {
        Self {
            center: 128.0,
            width: 256.0,
            slope: 1.0,
            intercept: 0.0,
        }
    }
}
```

- [ ] **Step 3: Verify the build**

```powershell
cargo build
```

Expected: clean build.

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/src/errors.rs" "basic PACS/rust_version/src/windowing.rs"
git commit -m "feat(rust): add RrsError and WindowSettings types"
```

---

## Task 3: Synthetic DICOM test fixture

**Files:**
- Create: `basic PACS/rust_version/tests/common/mod.rs`
- Create: `basic PACS/rust_version/tests/fixture_smoke.rs`

This task builds the test helper that synthesizes minimal DICOM files in a `TempDir`. It's the analog of the Python `conftest.py` fixture and is the foundation for every later test.

- [ ] **Step 1: Create `tests/common/mod.rs` with the builder**

```rust
//! Synthetic DICOM builders used by integration tests.

use std::path::{Path, PathBuf};
use tempfile::TempDir;

use dicom_core::dicom_value;
use dicom_core::value::PrimitiveValue;
use dicom_core::{DataElement, VR};
use dicom_dictionary_std::tags;
use dicom_object::{FileMetaTableBuilder, InMemDicomObject};

/// Parameters for a synthetic DICOM file. All fields are optional;
/// sensible defaults are used when omitted.
#[derive(Default)]
pub struct DicomFixture {
    pub patient_name: Option<&'static str>,
    pub modality: Option<&'static str>,
    pub rows: Option<u16>,
    pub cols: Option<u16>,
    pub instance_number: Option<i32>,
    pub window_center: Option<f64>,
    pub window_width: Option<f64>,
    pub rescale_slope: Option<f64>,
    pub rescale_intercept: Option<f64>,
    /// Stored pixel values (raw, pre-rescale). Length must be rows*cols.
    /// If None, a flat ramp from 0..(rows*cols) is generated.
    pub pixels: Option<Vec<u16>>,
}

/// Write a synthetic DICOM into the given temp dir; returns the resulting path.
pub fn write_synthetic(dir: &Path, name: &str, fx: DicomFixture) -> PathBuf {
    let rows = fx.rows.unwrap_or(4);
    let cols = fx.cols.unwrap_or(4);
    let pixels = fx
        .pixels
        .unwrap_or_else(|| (0..(rows as u32 * cols as u32)).map(|v| v as u16).collect());
    assert_eq!(pixels.len(), rows as usize * cols as usize);

    let mut obj = InMemDicomObject::new_empty();

    // Required identifying / display tags
    obj.put(DataElement::new(
        tags::PATIENT_NAME,
        VR::PN,
        PrimitiveValue::from(fx.patient_name.unwrap_or("Test^Patient")),
    ));
    obj.put(DataElement::new(
        tags::MODALITY,
        VR::CS,
        PrimitiveValue::from(fx.modality.unwrap_or("CT")),
    ));
    obj.put(DataElement::new(
        tags::INSTANCE_NUMBER,
        VR::IS,
        PrimitiveValue::from(fx.instance_number.unwrap_or(1).to_string()),
    ));

    // Image-pixel-module tags
    obj.put(DataElement::new(tags::ROWS, VR::US, dicom_value!(U16, rows)));
    obj.put(DataElement::new(tags::COLUMNS, VR::US, dicom_value!(U16, cols)));
    obj.put(DataElement::new(tags::BITS_ALLOCATED, VR::US, dicom_value!(U16, 16)));
    obj.put(DataElement::new(tags::BITS_STORED, VR::US, dicom_value!(U16, 16)));
    obj.put(DataElement::new(tags::HIGH_BIT, VR::US, dicom_value!(U16, 15)));
    obj.put(DataElement::new(tags::PIXEL_REPRESENTATION, VR::US, dicom_value!(U16, 0)));
    obj.put(DataElement::new(tags::SAMPLES_PER_PIXEL, VR::US, dicom_value!(U16, 1)));
    obj.put(DataElement::new(
        tags::PHOTOMETRIC_INTERPRETATION,
        VR::CS,
        PrimitiveValue::from("MONOCHROME2"),
    ));

    // W/L + rescale
    obj.put(DataElement::new(
        tags::WINDOW_CENTER,
        VR::DS,
        PrimitiveValue::from(fx.window_center.unwrap_or(40.0).to_string()),
    ));
    obj.put(DataElement::new(
        tags::WINDOW_WIDTH,
        VR::DS,
        PrimitiveValue::from(fx.window_width.unwrap_or(400.0).to_string()),
    ));
    obj.put(DataElement::new(
        tags::RESCALE_SLOPE,
        VR::DS,
        PrimitiveValue::from(fx.rescale_slope.unwrap_or(1.0).to_string()),
    ));
    obj.put(DataElement::new(
        tags::RESCALE_INTERCEPT,
        VR::DS,
        PrimitiveValue::from(fx.rescale_intercept.unwrap_or(-1024.0).to_string()),
    ));

    // Pixel data (Explicit VR Little Endian, uncompressed, 16-bit unsigned)
    let pixel_bytes: Vec<u8> = pixels.iter().flat_map(|p| p.to_le_bytes()).collect();
    obj.put(DataElement::new(
        tags::PIXEL_DATA,
        VR::OW,
        PrimitiveValue::from(pixel_bytes),
    ));

    // File meta with Explicit VR Little Endian transfer syntax
    let meta = FileMetaTableBuilder::new()
        .transfer_syntax("1.2.840.10008.1.2.1") // Explicit VR Little Endian
        .media_storage_sop_class_uid("1.2.840.10008.5.1.4.1.1.2") // CT Image Storage
        .media_storage_sop_instance_uid("1.2.3.4.5.6.7.8.9.0")
        .build()
        .expect("file meta build");

    let path = dir.join(name);
    let file_obj = obj.with_meta(meta);
    file_obj.write_to_file(&path).expect("write synthetic DICOM");
    path
}

/// Convenience: a fresh `TempDir` so individual tests don't have to manage it.
pub fn fresh_dir() -> TempDir {
    tempfile::tempdir().expect("create tempdir")
}
```

> **Note on builder API:** the exact constructors above (`FileMetaTableBuilder`, `InMemDicomObject::new_empty`, `with_meta`, `write_to_file`) come from `dicom-object`'s public API. If a method name differs in the version pulled by `cargo add`, adjust accordingly using `cargo doc --open -p dicom-object`. The semantic shape (build a meta table, build an object, write to disk) is what matters.

- [ ] **Step 2: Create a smoke test that just exercises the fixture**

`tests/fixture_smoke.rs`:

```rust
mod common;

use common::{fresh_dir, write_synthetic, DicomFixture};
use dicom_dictionary_std::tags;
use dicom_object::open_file;

#[test]
fn synthetic_fixture_roundtrips_through_dicom_rs() {
    let dir = fresh_dir();
    let path = write_synthetic(
        dir.path(),
        "smoke.dcm",
        DicomFixture {
            patient_name: Some("Smoke^Test"),
            modality: Some("MR"),
            instance_number: Some(7),
            ..Default::default()
        },
    );

    let obj = open_file(&path).expect("read synthetic DICOM");
    let name = obj
        .element(tags::PATIENT_NAME)
        .unwrap()
        .to_str()
        .unwrap()
        .into_owned();
    assert_eq!(name, "Smoke^Test");

    let modality = obj
        .element(tags::MODALITY)
        .unwrap()
        .to_str()
        .unwrap()
        .into_owned();
    assert_eq!(modality, "MR");

    let instance: i32 = obj
        .element(tags::INSTANCE_NUMBER)
        .unwrap()
        .to_int()
        .unwrap();
    assert_eq!(instance, 7);
}
```

- [ ] **Step 3: Run the smoke test**

```powershell
cargo test --test fixture_smoke -- --nocapture
```

Expected: PASS. If it fails, the fixture builder has a wrong API call — fix it now before proceeding (the rest of the plan depends on this builder working).

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/tests"
git commit -m "test(rust): synthetic DICOM fixture + smoke test"
```

---

## Task 4: `windowing::extract_pixels` (TDD)

**Files:**
- Create: `basic PACS/rust_version/tests/windowing.rs`
- Modify: `basic PACS/rust_version/src/windowing.rs`

- [ ] **Step 1: Write the failing integration test**

Create `tests/windowing.rs`:

```rust
mod common;

use common::{fresh_dir, write_synthetic, DicomFixture};
use rustradstack::windowing::{extract_pixels, WindowSettings};

#[test]
fn extract_pixels_returns_dims_and_window_settings() {
    let dir = fresh_dir();
    let path = write_synthetic(
        dir.path(),
        "ct.dcm",
        DicomFixture {
            rows: Some(4),
            cols: Some(4),
            window_center: Some(40.0),
            window_width: Some(400.0),
            rescale_slope: Some(1.0),
            rescale_intercept: Some(-1024.0),
            ..Default::default()
        },
    );

    let (pixels, dims, ws) = extract_pixels(&path).expect("extract");

    assert_eq!(dims, (4, 4));
    assert_eq!(pixels.len(), 16);
    // Default ramp is 0..16 stored values.
    assert_eq!(pixels[0], 0);
    assert_eq!(pixels[15], 15);
    assert_eq!(
        ws,
        WindowSettings {
            center: 40.0,
            width: 400.0,
            slope: 1.0,
            intercept: -1024.0,
        }
    );
}

```

- [ ] **Step 2: Run it — expect FAIL**

```powershell
cargo test --test windowing
```

Expected: compilation error like `unresolved import rustradstack::windowing::extract_pixels`.

- [ ] **Step 3: Implement `extract_pixels` in `src/windowing.rs`**

Append to `src/windowing.rs`:

```rust
use std::path::Path;

use dicom_dictionary_std::tags;
use dicom_object::open_file;
use dicom_pixeldata::PixelDecoder;

use crate::errors::RrsError;

/// Read a DICOM file and return (stored pixel values as i32, (rows, cols), window settings).
///
/// Stored values are pre-rescale — call sites apply slope/intercept inside `apply_window`.
/// Returns an error if the file can't be parsed or pixel decoding fails.
pub fn extract_pixels(
    path: &Path,
) -> Result<(Vec<i32>, (u32, u32), WindowSettings), RrsError> {
    let obj = open_file(path).map_err(|e| RrsError::Dicom(e.to_string()))?;

    let rows: u32 = read_u32(&obj, tags::ROWS, "Rows")?;
    let cols: u32 = read_u32(&obj, tags::COLUMNS, "Columns")?;

    let center = read_f64_or_default(&obj, tags::WINDOW_CENTER, 128.0);
    let width = read_f64_or_default(&obj, tags::WINDOW_WIDTH, 256.0);
    let slope = read_f64_or_default(&obj, tags::RESCALE_SLOPE, 1.0);
    let intercept = read_f64_or_default(&obj, tags::RESCALE_INTERCEPT, 0.0);

    let decoded = obj
        .decode_pixel_data()
        .map_err(|e| RrsError::Dicom(e.to_string()))?;
    let frame: Vec<i32> = decoded
        .to_ndarray::<i32>()
        .map_err(|e| RrsError::Dicom(e.to_string()))?
        .into_raw_vec_and_offset()
        .0;

    if frame.len() != (rows * cols) as usize {
        return Err(RrsError::UnsupportedPixels(format!(
            "decoded {} values, expected {}x{}={}",
            frame.len(),
            rows,
            cols,
            rows * cols
        )));
    }

    Ok((frame, (rows, cols), WindowSettings { center, width, slope, intercept }))
}

fn read_u32(
    obj: &dicom_object::DefaultDicomObject,
    tag: dicom_core::Tag,
    name: &'static str,
) -> Result<u32, RrsError> {
    let elt = obj.element(tag).map_err(|_| RrsError::MissingTag(name))?;
    elt.to_int::<u32>()
        .map_err(|e| RrsError::Dicom(format!("{name}: {e}")))
}

fn read_f64_or_default(
    obj: &dicom_object::DefaultDicomObject,
    tag: dicom_core::Tag,
    default: f64,
) -> f64 {
    obj.element(tag)
        .ok()
        .and_then(|e| e.to_float64().ok())
        .unwrap_or(default)
}
```

> **Note on pixel decode API:** `dicom-pixeldata` exposes a `PixelDecoder` trait that adds `decode_pixel_data()` to DICOM objects, plus a `to_ndarray::<T>()` method on the decoded result. If the exact method names differ in the version you pulled, run `cargo doc --open -p dicom-pixeldata` and adjust — the semantic operation (decode bytes → ndarray of integers → flat Vec) stays the same.

- [ ] **Step 4: Run the tests — expect PASS**

```powershell
cargo test --test windowing
```

Expected: both tests PASS.

If `decode_pixel_data` or `to_ndarray` API is different in the installed version, the compile will fail with a clear message; fix the names per the docs before continuing.

- [ ] **Step 5: Commit**

```powershell
git add "basic PACS/rust_version/src/windowing.rs" "basic PACS/rust_version/tests/windowing.rs"
git commit -m "feat(rust): windowing::extract_pixels reads dims, pixels, W/L"
```

---

## Task 5: CLI `info` subcommand

**Files:**
- Modify: `basic PACS/rust_version/src/bin/rrs-cli.rs`

- [ ] **Step 1: Replace `src/bin/rrs-cli.rs` with the real CLI**

```rust
//! `rrs-cli` — command-line interface for RustRadStack.
//!
//! Subcommands:
//!   info <FILE>   Print key DICOM tags from a single file.

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use anyhow::{anyhow, Context, Result};

use dicom_dictionary_std::tags;
use dicom_object::open_file;
use rustradstack::windowing::extract_pixels;

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
    let mut args = env::args().skip(1);
    let cmd = args.next().ok_or_else(|| anyhow!(USAGE))?;
    match cmd.as_str() {
        "info" => {
            let path: PathBuf = args
                .next()
                .ok_or_else(|| anyhow!("info requires a path argument\n\n{USAGE}"))?
                .into();
            cmd_info(&path)
        }
        other => Err(anyhow!("unknown subcommand: {other}\n\n{USAGE}")),
    }
}

const USAGE: &str = "Usage:\n  rrs-cli info <FILE>";

fn cmd_info(path: &std::path::Path) -> Result<()> {
    // Read tags directly via dicom-object for the metadata-only fields
    // (PatientName, Modality), then call extract_pixels for dims + W/L.
    let obj = open_file(path).with_context(|| format!("opening {}", path.display()))?;

    let patient_name = obj
        .element(tags::PATIENT_NAME)
        .ok()
        .and_then(|e| e.to_str().ok().map(|s| s.into_owned()))
        .unwrap_or_else(|| "(missing)".into());
    let modality = obj
        .element(tags::MODALITY)
        .ok()
        .and_then(|e| e.to_str().ok().map(|s| s.into_owned()))
        .unwrap_or_else(|| "(missing)".into());
    let instance_number: Option<i32> = obj
        .element(tags::INSTANCE_NUMBER)
        .ok()
        .and_then(|e| e.to_int().ok());

    let (_pixels, (rows, cols), ws) =
        extract_pixels(path).with_context(|| format!("extracting pixels from {}", path.display()))?;

    println!("File:            {}", path.display());
    println!("PatientName:     {patient_name}");
    println!("Modality:        {modality}");
    println!(
        "InstanceNumber:  {}",
        instance_number
            .map(|n| n.to_string())
            .unwrap_or_else(|| "(missing)".into())
    );
    println!("Rows x Cols:     {rows} x {cols}");
    println!("WindowCenter:    {}", ws.center);
    println!("WindowWidth:     {}", ws.width);
    println!("RescaleSlope:    {}", ws.slope);
    println!("RescaleIntercept:{}", ws.intercept);

    Ok(())
}
```

- [ ] **Step 2: Build and confirm no errors**

```powershell
cargo build --bin rrs-cli
```

Expected: clean build.

- [ ] **Step 3: Add an integration test that invokes the CLI**

Create `tests/cli_info.rs`:

```rust
mod common;

use std::process::Command;

use common::{fresh_dir, write_synthetic, DicomFixture};

#[test]
fn cli_info_prints_expected_fields() {
    let dir = fresh_dir();
    let path = write_synthetic(
        dir.path(),
        "case.dcm",
        DicomFixture {
            patient_name: Some("Smith^John"),
            modality: Some("CT"),
            instance_number: Some(3),
            window_center: Some(40.0),
            window_width: Some(400.0),
            ..Default::default()
        },
    );

    let bin = env!("CARGO_BIN_EXE_rrs-cli");
    let out = Command::new(bin)
        .args(["info"])
        .arg(&path)
        .output()
        .expect("run rrs-cli");
    assert!(
        out.status.success(),
        "rrs-cli failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );

    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(stdout.contains("PatientName:     Smith^John"), "stdout: {stdout}");
    assert!(stdout.contains("Modality:        CT"), "stdout: {stdout}");
    assert!(stdout.contains("InstanceNumber:  3"), "stdout: {stdout}");
    assert!(stdout.contains("Rows x Cols:     4 x 4"), "stdout: {stdout}");
    assert!(stdout.contains("WindowCenter:    40"), "stdout: {stdout}");
    assert!(stdout.contains("WindowWidth:     400"), "stdout: {stdout}");
}
```

- [ ] **Step 4: Run the integration test — expect PASS**

```powershell
cargo test --test cli_info
```

Expected: PASS.

- [ ] **Step 5: Run the full test suite**

```powershell
cargo test
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/bin/rrs-cli.rs" "basic PACS/rust_version/tests/cli_info.rs"
git commit -m "feat(rust): rrs-cli info subcommand prints DICOM tags"
```

---

## Task 6: README for `rust_version`

**Files:**
- Create: `basic PACS/rust_version/README.md`

- [ ] **Step 1: Write the README**

```markdown
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
```

- [ ] **Step 2: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): README for rust_version with CLI usage and roadmap"
```

---

## Task 7: Profiling pass (per standing plan template)

This is the user's standing plan-template requirement: every plan ends with a profiling pass before the refactor pass. For slice 1 the surface area is small, so this is a quick smoke check rather than full profiling.

**Files:**
- None (read-only / measurement only)

- [ ] **Step 1: Build in release mode**

```powershell
cargo build --release --bin rrs-cli
```

Expected: clean release build.

- [ ] **Step 2: Time `info` on a synthetic DICOM**

```powershell
cargo test --release --test cli_info -- --nocapture
```

Note the test wall-clock time. Run it three times; record the median.

- [ ] **Step 3: Document findings**

Append a short section to `basic PACS/rust_version/README.md` under a new `## Performance notes` heading:

```markdown
## Performance notes

Slice 1 baseline (4x4 synthetic DICOM, release build, Windows):
- `cargo test --release --test cli_info`: ~__ms total.
- Hot path: `dicom-object::open_file` (file I/O + parse). Pixel decode is dominated by parser overhead at this size.

These numbers exist to compare against later slices. Real-world (512x512) latency will be measured when a real DICOM is wired in.
```

Fill in the actual median number you observed. (If there's no quick way to time it, run `Measure-Command { cargo test --release --test cli_info }` in PowerShell — it prints a `TotalMilliseconds` field.)

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "perf(rust): record slice-1 baseline timings in README"
```

---

## Task 8: Dead-code / readability refactor pass (per standing plan template)

**Files:** any of the slice-1 source files, depending on what clippy says.

- [ ] **Step 1: Run clippy with all warnings**

```powershell
cargo clippy --all-targets -- -W clippy::pedantic -W clippy::nursery
```

Expected: a list of suggestions. `pedantic` and `nursery` are noisier than the defaults — that's intentional, this is the cleanup pass.

- [ ] **Step 2: Apply each suggestion that improves the code**

Walk through clippy's output. For each lint:
- If the suggested fix makes the code clearer, apply it.
- If it's a stylistic nit that the user disagrees with (e.g. `must_use_candidate` on every public function), allow it locally with `#[allow(clippy::lint_name)]` rather than silencing globally.
- If it's structural (e.g. "this struct should derive `Eq`"), apply it.

- [ ] **Step 3: Read each file with fresh eyes**

Open `src/lib.rs`, `src/errors.rs`, `src/windowing.rs`, `src/bin/rrs-cli.rs`, `tests/common/mod.rs` — top to bottom, no other tabs.

For each file, ask:
- Is there any code I can delete and still pass all tests?
- Are there any comments that explain *what* (delete them) versus *why* (keep them)?
- Are there any helpers (`read_u32`, `read_f64_or_default`) that are only called once and could be inlined for clarity? Or vice versa: any duplication that should be a helper?

Apply changes. Comment density per the user's standing preference: sparse why-only comments + a short intent line above each non-trivial function.

- [ ] **Step 4: Run the full suite to confirm no regressions**

```powershell
cargo test
cargo clippy --all-targets
```

Expected: all tests PASS; clippy clean (or with documented `#[allow]`s).

- [ ] **Step 5: Commit**

```powershell
git add "basic PACS/rust_version"
git commit -m "refactor(rust): clippy pass + readability cleanup for slice 1"
```

---

## Done criteria

Slice 1 is done when:

- [ ] `cargo build --release` is clean
- [ ] `cargo test` is green (smoke fixture, windowing, cli_info — at least 4 tests)
- [ ] `cargo clippy --all-targets` is clean
- [ ] `cargo run --bin rrs-cli -- info <synthetic>.dcm` prints the expected fields
- [ ] README documents CLI usage and roadmap
- [ ] Performance notes section captures slice-1 baseline timing

## Out of scope (for later slices)

- `apply_window` / W/L → 8-bit conversion (slice 2)
- `loader::scan_directory` (slice 3)
- `sorting::sort_files` (slice 3)
- `ImageStack` model (slice 4)
- egui viewer (slices 4–5)
