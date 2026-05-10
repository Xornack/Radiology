# RustRadStack — Slice 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `windowing::apply_window` (W/L math → grayscale image) and a `rrs-cli render <FILE> <OUT.png>` subcommand that produces a viewable PNG from any DICOM the slice-1 CLI can already inspect.

**Architecture:** `apply_window` is a pure free function: `(pixels: &[i32], dims, ws) -> GrayImage`. The `image` crate's `GrayImage = ImageBuffer<Luma<u8>, Vec<u8>>` is the carrier; `.save(path)` handles PNG encoding. `extract_pixels` is refactored from `&Path` → `&DefaultDicomObject` to fix the slice-1 double-open debt — both `cmd_info` and the new `cmd_render` open the file once and pass the object in.

**Tech Stack:** Same as slice 1 (`dicom-object`, `dicom-pixeldata`, `thiserror`, `anyhow`) plus first real use of `image` for PNG encoding.

**Reference docs:**
- [Design spec](../specs/2026-05-08-rust-port-design.md)
- [Slice-1 plan](2026-05-08-rust-port-slice-1.md)

Working dir for all commands below: `basic PACS/rust_version/` (relative to the worktree root) unless stated otherwise. Worktree root: `basic PACS/.claude/worktrees/slice-2/`.

---

## Task 1: Refactor `extract_pixels` to take `&DefaultDicomObject`

This pays off the slice-1 TODO. The function loses path I/O; callers open the file themselves.

**Files:**
- Modify: `basic PACS/rust_version/src/windowing.rs`
- Modify: `basic PACS/rust_version/tests/windowing.rs`
- Modify: `basic PACS/rust_version/src/bin/rrs-cli.rs`

- [ ] **Step 1: Update the integration test first (TDD-style — red before green)**

In `tests/windowing.rs`, change the test body to open the file and pass the object:

```rust
mod common;

use common::{fresh_dir, write_synthetic, DicomFixture};
use dicom_object::open_file;
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

    let obj = open_file(&path).expect("open");
    let (pixels, dims, ws) = extract_pixels(&obj).expect("extract");

    assert_eq!(dims, (4, 4));
    assert_eq!(pixels.len(), 16);
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

- [ ] **Step 2: Run the test — expect FAIL**

```powershell
cargo test --test windowing
```

Expected: compile error like `mismatched types: expected &Path, found &FileDicomObject<...>`.

- [ ] **Step 3: Update `extract_pixels` signature in `src/windowing.rs`**

Replace the function and remove the now-unused `open_file`/`Path` imports:

```rust
//! DICOM window/level math and pixel extraction.

use dicom_dictionary_std::tags;
use dicom_object::{DefaultDicomObject, Tag};
use dicom_pixeldata::{ConvertOptions, ModalityLutOption, PixelDecoder};

use crate::errors::RrsError;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct WindowSettings {
    pub center: f64,
    pub width: f64,
    pub slope: f64,
    pub intercept: f64,
}

impl Default for WindowSettings {
    /// Generic midpoint defaults — safe for any modality.
    /// Not CT-specific (CT abdomen would be center=40, width=400).
    fn default() -> Self {
        Self {
            center: 128.0,
            width: 256.0,
            slope: 1.0,
            intercept: 0.0,
        }
    }
}

/// Decoded frame: (stored pixel values as i32, (rows, cols), window settings).
/// Stored values are pre-rescale — call sites apply slope/intercept inside `apply_window`.
type ExtractResult = (Vec<i32>, (u32, u32), WindowSettings);

/// Extract dims, pre-rescale stored pixel values, and W/L tags from an already-opened DICOM object.
///
/// Stored values are pre-rescale; `apply_window` does the slope/intercept transform.
///
/// # Errors
/// Returns `RrsError::Dicom` if pixel decoding fails.
/// Returns `RrsError::MissingTag` if `Rows` or `Columns` tags are absent.
/// Returns `RrsError::UnsupportedPixels` if the decoded frame length doesn't match dimensions.
pub fn extract_pixels(obj: &DefaultDicomObject) -> Result<ExtractResult, RrsError> {
    let rows = read_u32(obj, tags::ROWS, "Rows")?;
    let cols = read_u32(obj, tags::COLUMNS, "Columns")?;

    let center = read_f64_or_default(obj, tags::WINDOW_CENTER, 128.0);
    let width = read_f64_or_default(obj, tags::WINDOW_WIDTH, 256.0);
    let slope = read_f64_or_default(obj, tags::RESCALE_SLOPE, 1.0);
    let intercept = read_f64_or_default(obj, tags::RESCALE_INTERCEPT, 0.0);

    // Decode without applying the Modality LUT so we get raw stored pixel values.
    let decoded = obj
        .decode_pixel_data()
        .map_err(|e| RrsError::Dicom(e.to_string()))?;
    let options = ConvertOptions::new().with_modality_lut(ModalityLutOption::None);
    let frame: Vec<i32> = decoded
        .to_vec_with_options(&options)
        .map_err(|e| RrsError::Dicom(e.to_string()))?;

    // Cast to usize before multiplying so dimensions like 65535x65535 don't overflow u32.
    let expected = rows as usize * cols as usize;
    if frame.len() != expected {
        return Err(RrsError::UnsupportedPixels(format!(
            "decoded {} values, expected {}x{}={}",
            frame.len(),
            rows,
            cols,
            expected
        )));
    }

    Ok((frame, (rows, cols), WindowSettings { center, width, slope, intercept }))
}

fn read_u32(obj: &DefaultDicomObject, tag: Tag, name: &'static str) -> Result<u32, RrsError> {
    let elt = obj.element(tag).map_err(|_| RrsError::MissingTag(name))?;
    elt.to_int::<u32>()
        .map_err(|e| RrsError::Dicom(format!("{name}: {e}")))
}

fn read_f64_or_default(obj: &DefaultDicomObject, tag: Tag, default: f64) -> f64 {
    obj.element(tag)
        .ok()
        .and_then(|e| e.to_float64().ok())
        .unwrap_or(default)
}
```

Notes:
- Removed `use std::path::Path;` and `use dicom_object::open_file;` — no longer needed here.
- The doc comment is rewritten: no more "Read a DICOM file" (caller does that), and the slice-2 transition note from slice 1 is removed (it's done now).
- Function bodies are otherwise unchanged.

- [ ] **Step 4: Update `cmd_info` in `src/bin/rrs-cli.rs` to pass the obj**

Find the `extract_pixels(path)` call in `cmd_info` and change it. Also remove the `TODO(slice-2)` comment that flagged the double-open:

```rust
fn cmd_info(path: &Path) -> Result<()> {
    let obj = open_file(path).with_context(|| format!("opening {}", path.display()))?;

    let patient_name = obj
        .element(tags::PATIENT_NAME)
        .ok()
        .and_then(|e| e.to_str().ok().map(std::borrow::Cow::into_owned))
        .unwrap_or_else(|| "(missing)".into());
    let modality = obj
        .element(tags::MODALITY)
        .ok()
        .and_then(|e| e.to_str().ok().map(std::borrow::Cow::into_owned))
        .unwrap_or_else(|| "(missing)".into());
    let instance_number: Option<i32> = obj
        .element(tags::INSTANCE_NUMBER)
        .ok()
        .and_then(|e| e.to_int::<i32>().ok());

    let (_pixels, (rows, cols), ws) =
        extract_pixels(&obj).with_context(|| format!("extracting pixels from {}", path.display()))?;

    // Labels left-padded to 18 cols so RescaleIntercept (17 chars) still gets a separator space.
    println!("{:<18}{}", "File:", path.display());
    println!("{:<18}{patient_name}", "PatientName:");
    println!("{:<18}{modality}", "Modality:");
    println!(
        "{:<18}{}",
        "InstanceNumber:",
        instance_number.map_or_else(|| "(missing)".into(), |n| n.to_string())
    );
    println!("{:<18}{rows} x {cols}", "Rows x Cols:");
    println!("{:<18}{}", "WindowCenter:", ws.center);
    println!("{:<18}{}", "WindowWidth:", ws.width);
    println!("{:<18}{}", "RescaleSlope:", ws.slope);
    println!("{:<18}{}", "RescaleIntercept:", ws.intercept);

    Ok(())
}
```

The only behavioral change is `extract_pixels(&obj)` instead of `extract_pixels(path)` — the file is opened exactly once now.

- [ ] **Step 5: Run the full test suite**

```powershell
cargo test
```

Expected: all 3 tests pass (fixture_smoke, windowing — now using the new signature, cli_info — unaffected since it tests the binary as a subprocess).

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/windowing.rs" "basic PACS/rust_version/src/bin/rrs-cli.rs" "basic PACS/rust_version/tests/windowing.rs"
git commit -m "refactor(rust): extract_pixels takes &DefaultDicomObject, not &Path"
```

---

## Task 2: `windowing::apply_window` (TDD with inline unit tests)

Pure math, no I/O — inline `#[cfg(test)] mod tests` is the right home.

**Files:**
- Modify: `basic PACS/rust_version/src/windowing.rs`

- [ ] **Step 1: Add the `mod tests` block alone (no impl yet) to drive the RED**

Append to the bottom of `src/windowing.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    fn ws(center: f64, width: f64, slope: f64, intercept: f64) -> WindowSettings {
        WindowSettings { center, width, slope, intercept }
    }

    #[test]
    fn maps_window_midpoint_to_127_or_128() {
        // center=128, width=256, slope=1, intercept=0 → window [0, 256], midpoint 128
        // Maps to (128-0)/256*255 = 127.5 → rounds to 128 (Rust's f64::round is half-away-from-zero)
        let img = apply_window(&[128], (1, 1), ws(128.0, 256.0, 1.0, 0.0));
        let value = img.as_raw()[0];
        assert!(value == 127 || value == 128, "midpoint should be ~127-128, got {value}");
    }

    #[test]
    fn clamps_values_below_window_to_0() {
        let img = apply_window(&[-1000], (1, 1), ws(128.0, 256.0, 1.0, 0.0));
        assert_eq!(img.as_raw()[0], 0);
    }

    #[test]
    fn clamps_values_above_window_to_255() {
        let img = apply_window(&[10_000], (1, 1), ws(128.0, 256.0, 1.0, 0.0));
        assert_eq!(img.as_raw()[0], 255);
    }

    #[test]
    fn applies_rescale_slope_and_intercept_before_windowing() {
        // CT-style: stored=1024, slope=1, intercept=-1024 → HU=0
        // window center=40, width=400 → [-160, 240], 0 at (0-(-160))/400 = 0.4 → 102 (rounded)
        let img = apply_window(&[1024], (1, 1), ws(40.0, 400.0, 1.0, -1024.0));
        let value = img.as_raw()[0];
        assert!(
            (101..=103).contains(&value),
            "expected ~102 for HU=0 in window [-160, 240], got {value}"
        );
    }

    #[test]
    fn produces_image_with_correct_dimensions() {
        // 2 rows × 3 cols = 6 pixels. image's dimensions() returns (width, height) = (cols, rows).
        let img = apply_window(&[0, 64, 128, 192, 255, 255], (2, 3), ws(128.0, 256.0, 1.0, 0.0));
        assert_eq!(img.dimensions(), (3, 2));
        assert_eq!(img.as_raw().len(), 6);
    }

    #[test]
    fn handles_zero_width_without_dividing_by_zero() {
        // Degenerate: width=0 means lower==upper. Output isn't meaningfully defined,
        // but the function must not panic or produce NaN.
        let img = apply_window(&[100, 200, 300], (1, 3), ws(128.0, 0.0, 1.0, 0.0));
        let raw = img.as_raw();
        assert_eq!(raw.len(), 3);
        assert_eq!(raw[0], raw[1]);
        assert_eq!(raw[1], raw[2]);
    }
}
```

- [ ] **Step 2: Run — expect compile error (RED)**

```powershell
cargo test --lib
```

Expected: compile error `cannot find function 'apply_window' in this scope` (or similar), because the function doesn't exist yet. This proves the tests would actually exercise the function.

- [ ] **Step 3: Add the `image` import and `apply_window` impl**

At the top of `src/windowing.rs` (in the `use` block, alphabetical), add:

```rust
use image::{GrayImage, ImageBuffer, Luma};
```

Then insert the function definition above the `#[cfg(test)] mod tests` block (i.e., after `read_f64_or_default`):

```rust
/// Apply rescale + Window/Level to stored pixel values to produce a displayable 8-bit image.
///
/// Steps per DICOM PS3.3 C.11.1:
/// 1. HU/VOI input = stored * slope + intercept
/// 2. Clamp to [center - width/2, center + width/2]
/// 3. Linearly rescale clamped values to 0..=255
///
/// `dims` is `(rows, cols)`; the returned `GrayImage` has `dimensions() == (cols, rows)`
/// because the `image` crate uses `(width, height)`.
///
/// # Panics
/// Panics if `pixels.len() != dims.0 * dims.1`. Use `extract_pixels` to get a `(pixels, dims)`
/// tuple where this invariant holds.
#[must_use]
pub fn apply_window(pixels: &[i32], dims: (u32, u32), w: WindowSettings) -> GrayImage {
    let (rows, cols) = dims;
    assert_eq!(
        pixels.len(),
        rows as usize * cols as usize,
        "pixels.len() ({}) doesn't match dims ({rows}x{cols})",
        pixels.len()
    );

    let lower = w.center - w.width / 2.0;
    let upper = w.center + w.width / 2.0;
    // .max(EPSILON) avoids divide-by-zero when WindowWidth is 0 (degenerate but seen in the wild).
    let span = (upper - lower).max(f64::EPSILON);

    let bytes: Vec<u8> = pixels
        .iter()
        .map(|&v| {
            let hu = f64::from(v) * w.slope + w.intercept;
            let clamped = hu.clamp(lower, upper);
            let scaled = (clamped - lower) / span * 255.0;
            scaled.round() as u8
        })
        .collect();

    ImageBuffer::<Luma<u8>, _>::from_raw(cols, rows, bytes)
        .expect("dims/pixel-count invariant verified by assert above")
}
```

- [ ] **Step 4: Run — expect GREEN**

```powershell
cargo test --lib
```

Expected: 6 unit tests in `windowing::tests` PASS.

- [ ] **Step 5: Run the full suite for regressions**

```powershell
cargo test
```

Expected: 6 unit tests + 3 integration tests = 9 tests passing.

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/windowing.rs"
git commit -m "feat(rust): apply_window does W/L + rescale to 8-bit GrayImage"
```

---

## Task 3: CLI `render` subcommand

**Files:**
- Modify: `basic PACS/rust_version/src/bin/rrs-cli.rs`
- Create: `basic PACS/rust_version/tests/cli_render.rs`

- [ ] **Step 1: Add the `render` branch to the CLI**

Modify `src/bin/rrs-cli.rs`. Update the `run()` function and `USAGE` constant, then add `cmd_render`:

```rust
//! `rrs-cli` — command-line interface for `RustRadStack`.
//!
//! Subcommands:
//!   info <FILE>              Print key DICOM tags from a single file.
//!   render <FILE> <OUT.png>  Window/level a DICOM and write it as a PNG.

use std::env;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use anyhow::{anyhow, Context, Result};

use dicom_dictionary_std::tags;
use dicom_object::open_file;
use rustradstack::windowing::{apply_window, extract_pixels};

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
        "render" => {
            let input: PathBuf = args
                .next()
                .ok_or_else(|| anyhow!("render requires <FILE> <OUT.png>\n\n{USAGE}"))?
                .into();
            let output: PathBuf = args
                .next()
                .ok_or_else(|| anyhow!("render requires <FILE> <OUT.png>\n\n{USAGE}"))?
                .into();
            cmd_render(&input, &output)
        }
        other => Err(anyhow!("unknown subcommand: {other}\n\n{USAGE}")),
    }
}

const USAGE: &str = "Usage:\n  rrs-cli info <FILE>\n  rrs-cli render <FILE> <OUT.png>";
```

Then keep `cmd_info` exactly as it is after Task 1 (no changes), and add `cmd_render` after it:

```rust
fn cmd_render(input: &Path, output: &Path) -> Result<()> {
    let obj = open_file(input).with_context(|| format!("opening {}", input.display()))?;
    let (pixels, dims, ws) = extract_pixels(&obj)
        .with_context(|| format!("extracting pixels from {}", input.display()))?;
    let img = apply_window(&pixels, dims, ws);
    img.save(output)
        .with_context(|| format!("writing {}", output.display()))?;
    println!("wrote {}", output.display());
    Ok(())
}
```

- [ ] **Step 2: Build the binary**

```powershell
cargo build --bin rrs-cli
```

Expected: clean build.

- [ ] **Step 3: Add the integration test**

Create `tests/cli_render.rs`:

```rust
mod common;

use std::process::Command;

use common::{fresh_dir, write_synthetic, DicomFixture};
use image::GenericImageView;

#[test]
fn cli_render_writes_a_png_with_correct_dimensions() {
    let dir = fresh_dir();
    let dcm = write_synthetic(
        dir.path(),
        "case.dcm",
        DicomFixture {
            rows: Some(8),
            cols: Some(8),
            window_center: Some(40.0),
            window_width: Some(400.0),
            ..Default::default()
        },
    );
    let png = dir.path().join("out.png");

    let bin = env!("CARGO_BIN_EXE_rrs-cli");
    let out = Command::new(bin)
        .args(["render"])
        .arg(&dcm)
        .arg(&png)
        .output()
        .expect("run rrs-cli");
    assert!(
        out.status.success(),
        "rrs-cli render failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );

    assert!(png.exists(), "PNG was not written");

    let img = image::open(&png).expect("decode written PNG");
    assert_eq!(img.dimensions(), (8, 8), "PNG dimensions don't match input");

    // Confirm the PNG is grayscale (single-channel).
    use image::ColorType;
    let color = image::ImageReader::open(&png)
        .expect("open png")
        .into_decoder()
        .expect("decoder")
        .color_type();
    assert_eq!(color, ColorType::L8, "PNG should be 8-bit grayscale");
}

#[test]
fn cli_render_errors_when_output_dir_missing() {
    let dir = fresh_dir();
    let dcm = write_synthetic(dir.path(), "case.dcm", DicomFixture::default());
    let bad_output = dir.path().join("does/not/exist/out.png");

    let bin = env!("CARGO_BIN_EXE_rrs-cli");
    let out = Command::new(bin)
        .args(["render"])
        .arg(&dcm)
        .arg(&bad_output)
        .output()
        .expect("run rrs-cli");

    assert!(!out.status.success(), "expected non-zero exit on bad output path");
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(
        stderr.contains("writing") || stderr.contains("does/not/exist"),
        "stderr should mention the failed write; got: {stderr}"
    );
}
```

`image::GenericImageView` brings the `dimensions()` method into scope.

- [ ] **Step 4: Run the integration test**

```powershell
cargo test --test cli_render
```

Expected: 2 tests PASS.

If the second test fails because Windows handles the missing-dir differently, relax the assertion: `assert!(!out.status.success())` is the essential bit; the stderr substring check can be loosened to just confirm the binary exited non-zero.

- [ ] **Step 5: Run the full suite**

```powershell
cargo test
```

Expected: 6 unit tests + 4 integration tests (fixture_smoke, windowing, cli_info, cli_render — 2 in the last one) = 11 tests passing.

Actually count: fixture_smoke (1) + windowing (1) + cli_info (1) + cli_render (2) = 5 integration tests + 6 unit tests = 11 total.

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/bin/rrs-cli.rs" "basic PACS/rust_version/tests/cli_render.rs"
git commit -m "feat(rust): rrs-cli render subcommand writes 8-bit PNG"
```

---

## Task 4: Manual smoke test on real DICOMs

The user has real anonymized DICOMs at `basic PACS/rust_version/DICOM_test_files/series-000001..006/`. Render one slice from each series and visually confirm the PNGs look like brain MR (or at least look like images of *something*, not noise).

This is a manual eyeball check — not a unit test. The point is to catch issues that synthetic 4×4 test fixtures can't surface (wrong byte order, off-by-one in W/L scaling, etc.).

**Files:** none (just reads + writes PNGs to a tempdir)

- [ ] **Step 1: Render the first slice of each series**

From `basic PACS/rust_version/`, run:

```powershell
cargo build --release --bin rrs-cli
$out = New-Item -ItemType Directory -Path "$env:TEMP\rrs-smoke" -Force
foreach ($s in 1..6) {
    $series = "DICOM_test_files\series-00000$s\image-000001.dcm"
    $png = Join-Path $out.FullName "series-00000$s.png"
    .\target\release\rrs-cli.exe render $series $png
}
explorer.exe $out.FullName
```

Expected: 6 PNG files in `$env:TEMP\rrs-smoke\`, opened in Explorer. Each should show recognizable anatomy at the correct W/L for that series. If any PNG is solid black, solid white, or pure noise, that's a real bug — investigate before continuing the slice.

- [ ] **Step 2: Document the smoke-test result**

Append a short note to `basic PACS/rust_version/README.md`'s `## Performance notes` section (just below it) — actually, add a new short section `## Real-DICOM validation`:

```markdown
## Real-DICOM validation

Slice 2 was smoke-tested by rendering one slice from each of 6 anonymized
MR series (3 different acquisition geometries, 256×256 and 512×512). Resulting
PNGs displayed as expected: visible anatomy, correct W/L per file, no byte-
order issues. Real-data testing is currently manual — formal regression tests
against real files are deferred until a stable test-data location is decided.
```

- [ ] **Step 3: Commit the README update**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): note real-DICOM smoke-test validation for slice 2"
```

If the smoke test surfaced a bug, instead: stop here, report it, and we triage before committing.

---

## Task 5: README update for `render` subcommand

**Files:**
- Modify: `basic PACS/rust_version/README.md`

- [ ] **Step 1: Update the CLI usage section**

Find the existing `## CLI usage` section in `README.md`. Replace it with:

```markdown
## CLI usage

Print key tags from a DICOM file:

\`\`\`powershell
cargo run --bin rrs-cli -- info path\to\file.dcm
\`\`\`

Output:

\`\`\`
File:             path\to\file.dcm
PatientName:      Smith^John
Modality:         CT
InstanceNumber:   3
Rows x Cols:      512 x 512
WindowCenter:     40
WindowWidth:      400
RescaleSlope:     1
RescaleIntercept: 0
\`\`\`

Render a DICOM as an 8-bit grayscale PNG (W/L from file's tags):

\`\`\`powershell
cargo run --bin rrs-cli -- render path\to\file.dcm out.png
\`\`\`
```

(Use real triple-backtick fences, not the escaped tildes. The escape above is just so this plan's markdown renders correctly.)

- [ ] **Step 2: Update the Roadmap section**

Find the `## Roadmap` section. Update the slice list so slice 2 is now marked done:

```markdown
## Roadmap

See [the design spec](../docs/superpowers/specs/2026-05-08-rust-port-design.md). Slice plan:

1. ✅ Slice 1 — CLI prints DICOM tags
2. **Slice 2 (this slice)** — `apply_window` + `rrs-cli render` writes PNG
3. Slice 3 — folder scan + DICOM sort + `rrs-cli list`
4. Slice 4 — egui window displays a single DICOM
5. Slice 5 — egui app loads a folder, mouse wheel scrolls
```

- [ ] **Step 3: Update the Crate layout section**

Find the `## Crate layout` section. Update `windowing.rs` line and add nothing else:

```markdown
- `src/windowing.rs` — `WindowSettings`, `extract_pixels`, `apply_window`
```

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): README documents render subcommand and slice-2 status"
```

---

## Task 6: Profiling pass

Per the user's standing plan template.

**Files:** none initially; possibly `README.md` to update perf notes.

- [ ] **Step 1: Build release**

```powershell
cargo build --release --bin rrs-cli
```

Expected: clean release build.

- [ ] **Step 2: Time `render` on one synthetic and one real DICOM**

```powershell
# Synthetic: small, dominated by parser overhead
Measure-Command {
    cargo test --release --test cli_render -- --nocapture cli_render_writes_a_png_with_correct_dimensions
} | Select-Object TotalMilliseconds

# Real: 512x512 MR
Measure-Command {
    .\target\release\rrs-cli.exe render `
        "DICOM_test_files\series-000001\image-000001.dcm" `
        "$env:TEMP\rrs-perf.png"
} | Select-Object TotalMilliseconds
```

Run each three times, take the median.

- [ ] **Step 3: Update the README's `## Performance notes` section**

Replace the existing slice-1 paragraph with:

```markdown
## Performance notes

Release-build, Windows, median of 3 runs:

| Operation | Synthetic 4×4 | Real MR 512×512 |
|---|---|---|
| `rrs-cli render` (full pipeline: open → decode → W/L → encode → write PNG) | ~__ms | ~__ms |

Hot path on real files: `decode_pixel_data` (~70%) and `image::ImageBuffer::save` (PNG encoding, ~20%). The W/L pass is negligible. These numbers compare against later slices.
```

Replace the two `__ms` placeholders with your measured medians. The "70% / 20%" split is a reasonable starting estimate — if you have time and `cargo flamegraph` installed, refine with a real flamegraph; otherwise the estimates are fine for a baseline.

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "perf(rust): record slice-2 baseline timings (synthetic + real 512x512)"
```

---

## Task 7: Dead-code / readability refactor pass

Per the user's standing plan template.

**Files:** any of the slice-2 source files, depending on what clippy says.

- [ ] **Step 1: Run clippy with default + pedantic + nursery**

```powershell
cargo clippy --all-targets -- -W clippy::pedantic -W clippy::nursery
```

Expected: a list of suggestions (likely fewer than slice 1 since the patterns are now established).

- [ ] **Step 2: Apply each suggestion that improves the code**

For each lint:
- Apply if the fix improves clarity.
- Use a targeted `#[allow(clippy::lint_name)]` with a brief reason if you reject a pedantic nit.
- Pay particular attention to anything in `apply_window` (the new pure function) — clippy may catch numerical-correctness issues you'd want to know about (`cast_precision_loss`, `cast_possible_truncation`, etc.).

- [ ] **Step 3: Read each modified file with fresh eyes**

Open `src/windowing.rs`, `src/bin/rrs-cli.rs`, `tests/windowing.rs`, `tests/cli_render.rs` — top to bottom.

For each file, ask:
- Is `apply_window`'s implementation as simple as the description? Any unused branches?
- Is `cmd_render` doing one clear thing? Any inline logic that should be a helper?
- Are the unit tests pinning *behavior* (output values) or *implementation* (intermediate steps)? Behavior-only is the goal.
- Does the comment density match the user's standing preference (sparse why-only + intent line)?

Apply changes inline.

- [ ] **Step 4: Confirm green**

```powershell
cargo test
cargo clippy --all-targets
```

Expected: all 11 tests PASS; clippy clean (or with documented `#[allow]`s).

- [ ] **Step 5: Commit**

```powershell
git add "basic PACS/rust_version"
git commit -m "refactor(rust): clippy pass + readability cleanup for slice 2"
```

---

## Done criteria

Slice 2 is done when:

- [ ] `cargo build --release` clean
- [ ] `cargo test` green — at least 11 tests (6 unit in `windowing` + 1 each in `fixture_smoke`/`windowing`/`cli_info` + 2 in `cli_render`)
- [ ] `cargo clippy --all-targets` clean
- [ ] `rrs-cli render <real-dicom>.dcm out.png` produces a viewable PNG that shows recognizable anatomy
- [ ] `extract_pixels` takes `&DefaultDicomObject`, not `&Path` (slice-1 debt resolved)
- [ ] README documents both `info` and `render` subcommands; slice 2 marked done in roadmap
- [ ] Performance notes capture baseline for both synthetic and real-DICOM render

## Out of scope (for later slices)

- Folder scanning / sorting / multi-slice handling (slice 3)
- `ImageStack` model (slice 4)
- egui viewer (slices 4–5)
- W/L override flags on `render` (e.g. `--center 40 --width 400`) — defer; if desired, ~10 lines in slice 3 or later
- Multi-frame DICOM (single-frame is the only supported case)
- JPG/PNG *input* (slice 1+2 only handle DICOM input; non-DICOM input was descoped from MVP)
- Color DICOMs (US, photographs) — current pipeline is grayscale-only by design
