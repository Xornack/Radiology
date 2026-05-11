# RustRadStack — Slice 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute. Steps use `- [ ]` checkbox syntax.

**Goal:** Add `loader::scan_directory`, `sorting::sort_files`, and a `rrs-cli list <FOLDER>` subcommand that prints DICOM files sorted by `InstanceNumber` (with `ImagePositionPatient[2]` fallback). First task splits `extract_pixels` so sorting can read InstanceNumber without decoding pixel data.

**Architecture:** Two new modules (`loader`, `sorting`) at `src/` level. Sorting uses `dicom_object::open_file` + reads InstanceNumber via the new `read_metadata` helper (or a sort-specific helper that grabs only InstanceNumber + IPP). `cmd_list` opens nothing extra — it just prints filenames in sorted order with their sort key.

**Tech Stack:** No new deps. `walkdir` is in std-adjacent territory but `std::fs::read_dir` + recursion is enough for our scope.

Working dir: `basic PACS/rust_version/` (worktree root: `basic PACS/.claude/worktrees/scrollable-mvp/`).

---

## Task 1: Split `extract_pixels` into metadata-only + pixel-decode paths

Pays off slice-2 carry-forward. After this task: `cmd_info` no longer decodes pixels; sorting in Task 3 will use the metadata-only path.

**Files:**
- Modify: `basic PACS/rust_version/src/windowing.rs`
- Modify: `basic PACS/rust_version/src/bin/rrs-cli.rs`
- Modify: `basic PACS/rust_version/tests/windowing.rs`

- [ ] **Step 1: Add a failing test for `read_metadata`**

Add to `tests/windowing.rs` (alongside the existing `extract_pixels_returns_dims_and_window_settings` test):

```rust
use rustradstack::windowing::{extract_pixels, read_metadata, WindowSettings};

#[test]
fn read_metadata_returns_dims_and_window_settings_without_decoding_pixels() {
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
    let (dims, ws) = read_metadata(&obj).expect("read metadata");
    assert_eq!(dims, (4, 4));
    assert_eq!(ws, WindowSettings { center: 40.0, width: 400.0, slope: 1.0, intercept: -1024.0 });
}
```

(Keep the existing `extract_pixels_returns_dims_and_window_settings` test — it still uses `extract_pixels` and that signature doesn't change.)

- [ ] **Step 2: Run — expect compile failure (RED)**

```powershell
cargo test --test windowing
```

Expected: `cannot find function 'read_metadata' in this scope`.

- [ ] **Step 3: Implement `read_metadata` and refactor `extract_pixels` to call it**

Modify `src/windowing.rs`. Add `read_metadata` between the helpers and `extract_pixels`, and make `extract_pixels` call it:

```rust
/// Read just the dims + W/L tags from an already-opened DICOM object.
/// Cheap — does not touch pixel data. Use this when you only need metadata
/// (sorting, listing) and want to avoid decode cost on hundreds of files.
///
/// # Errors
/// Returns `RrsError::MissingTag` if `Rows` or `Columns` tags are absent.
pub fn read_metadata(
    obj: &DefaultDicomObject,
) -> Result<((u32, u32), WindowSettings), RrsError> {
    let rows = read_u32(obj, tags::ROWS, "Rows")?;
    let cols = read_u32(obj, tags::COLUMNS, "Columns")?;
    let center = read_f64_or_default(obj, tags::WINDOW_CENTER, 128.0);
    let width = read_f64_or_default(obj, tags::WINDOW_WIDTH, 256.0);
    let slope = read_f64_or_default(obj, tags::RESCALE_SLOPE, 1.0);
    let intercept = read_f64_or_default(obj, tags::RESCALE_INTERCEPT, 0.0);
    Ok(((rows, cols), WindowSettings { center, width, slope, intercept }))
}

pub fn extract_pixels(obj: &DefaultDicomObject) -> Result<ExtractResult, RrsError> {
    let (dims, ws) = read_metadata(obj)?;
    let (rows, cols) = dims;

    // Decode without applying the Modality LUT so we get raw stored pixel values.
    let decoded = obj
        .decode_pixel_data()
        .map_err(|e| RrsError::Dicom(e.to_string()))?;
    let options = ConvertOptions::new().with_modality_lut(ModalityLutOption::None);
    let frame: Vec<i32> = decoded
        .to_vec_with_options(&options)
        .map_err(|e| RrsError::Dicom(e.to_string()))?;

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

    Ok((frame, dims, ws))
}
```

- [ ] **Step 4: Update `cmd_info` to use `read_metadata` only**

In `src/bin/rrs-cli.rs`, change the import and the `cmd_info` body. Replace `use rustradstack::windowing::{apply_window, extract_pixels};` with:

```rust
use rustradstack::windowing::{apply_window, extract_pixels, read_metadata};
```

Then in `cmd_info`, replace the `extract_pixels(&obj).with_context(...)?` line with:

```rust
let ((rows, cols), ws) = read_metadata(&obj)
    .with_context(|| format!("reading metadata from {}", path.display()))?;
```

The `_pixels` variable is gone. Remove the corresponding destructure pattern. Resulting cmd_info call site:

```rust
let ((rows, cols), ws) = read_metadata(&obj)
    .with_context(|| format!("reading metadata from {}", path.display()))?;
```

(`cmd_render` still uses `extract_pixels` — don't change it.)

- [ ] **Step 5: Run — expect GREEN**

```powershell
cargo test
```

Expected: 14 tests pass (7 unit + 7 integration: 1 fixture_smoke, 2 windowing now, 1 cli_info, 2 cli_render). The integration test count goes 6 → 7.

- [ ] **Step 6: Manually verify `cmd_info` still works**

```powershell
cargo run --bin rrs-cli -- info "DICOM_test_files\series-000001\image-000001.dcm"
```

Expected: same output as before, just no pixel decode underneath. (You can confirm by running with `--release` and seeing whether it's noticeably faster, but the timing is dominated by file I/O for one slice.)

- [ ] **Step 7: Commit**

```powershell
git add "basic PACS/rust_version/src/windowing.rs" "basic PACS/rust_version/src/bin/rrs-cli.rs" "basic PACS/rust_version/tests/windowing.rs"
git commit -m "refactor(rust): split read_metadata from extract_pixels for cheap tag reads"
```

---

## Task 2: `loader::scan_directory`

Recursive walk that returns `.dcm` files in alphabetical-by-path order. Path-sorted for stable output; sorting by InstanceNumber happens in Task 3.

**Files:**
- Create: `basic PACS/rust_version/src/loader.rs`
- Modify: `basic PACS/rust_version/src/lib.rs`
- Create: `basic PACS/rust_version/tests/loader.rs`

- [ ] **Step 1: Wire the new module**

Add to `src/lib.rs` after the existing `pub mod` lines:

```rust
pub mod loader;
```

(Order: `errors`, `loader`, `windowing` — alphabetical.)

- [ ] **Step 2: Write failing tests**

Create `tests/loader.rs`:

```rust
mod common;

use std::fs;

use common::{fresh_dir, write_synthetic, DicomFixture};
use rustradstack::loader::scan_directory;

#[test]
fn scan_directory_returns_dcm_files_in_alphabetical_order() {
    let dir = fresh_dir();
    let p2 = write_synthetic(dir.path(), "b.dcm", DicomFixture::default());
    let p1 = write_synthetic(dir.path(), "a.dcm", DicomFixture::default());
    let p3 = write_synthetic(dir.path(), "c.dcm", DicomFixture::default());

    let found = scan_directory(dir.path()).expect("scan");
    assert_eq!(found, vec![p1, p2, p3]);
}

#[test]
fn scan_directory_filters_non_dcm_files() {
    let dir = fresh_dir();
    let dcm = write_synthetic(dir.path(), "image.dcm", DicomFixture::default());
    fs::write(dir.path().join("notes.txt"), "ignore me").unwrap();
    fs::write(dir.path().join("README"), "no extension").unwrap();

    let found = scan_directory(dir.path()).expect("scan");
    assert_eq!(found, vec![dcm]);
}

#[test]
fn scan_directory_recurses_into_subdirectories() {
    let dir = fresh_dir();
    let sub = dir.path().join("sub");
    fs::create_dir(&sub).unwrap();
    let nested = write_synthetic(&sub, "nested.dcm", DicomFixture::default());
    let top = write_synthetic(dir.path(), "top.dcm", DicomFixture::default());

    let found = scan_directory(dir.path()).expect("scan");
    // Alphabetical by full path: "nested.dcm" sorts before "top.dcm" because
    // "sub/nested.dcm" < "top.dcm" lexicographically.
    assert!(found.contains(&nested));
    assert!(found.contains(&top));
    assert_eq!(found.len(), 2);
}

#[test]
fn scan_directory_returns_empty_for_empty_dir() {
    let dir = fresh_dir();
    let found = scan_directory(dir.path()).expect("scan");
    assert!(found.is_empty());
}
```

- [ ] **Step 3: Run — expect FAIL**

```powershell
cargo test --test loader
```

Expected: compile error (`unresolved import rustradstack::loader::scan_directory`).

- [ ] **Step 4: Implement `loader::scan_directory`**

Create `src/loader.rs`:

```rust
//! Recursive directory scanning for DICOM files.

use std::io;
use std::path::{Path, PathBuf};

/// Recursively walk `dir` and return all `.dcm` files (case-insensitive extension match)
/// in alphabetical-by-path order.
///
/// # Errors
/// Returns `io::Error` if the directory can't be read.
pub fn scan_directory(dir: &Path) -> io::Result<Vec<PathBuf>> {
    let mut out = Vec::new();
    walk(dir, &mut out)?;
    out.sort();
    Ok(out)
}

fn walk(dir: &Path, out: &mut Vec<PathBuf>) -> io::Result<()> {
    for entry in std::fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            walk(&path, out)?;
        } else if file_type.is_file() && is_dicom(&path) {
            out.push(path);
        }
    }
    Ok(())
}

fn is_dicom(path: &Path) -> bool {
    path.extension()
        .and_then(|ext| ext.to_str())
        .map(|ext| ext.eq_ignore_ascii_case("dcm"))
        .unwrap_or(false)
}
```

- [ ] **Step 5: Run — expect GREEN**

```powershell
cargo test --test loader
```

Expected: 4 tests pass.

- [ ] **Step 6: Run full suite**

```powershell
cargo test
```

Expected: 7 unit + 11 integration = 18 tests passing (the 4 new loader tests added on top of 14 from Task 1).

- [ ] **Step 7: Commit**

```powershell
git add "basic PACS/rust_version/src/lib.rs" "basic PACS/rust_version/src/loader.rs" "basic PACS/rust_version/tests/loader.rs"
git commit -m "feat(rust): loader::scan_directory recursively finds .dcm files"
```

---

## Task 3: `sorting::sort_files`

Sort DICOMs by `InstanceNumber`, fallback to `ImagePositionPatient[2]` Z-coord, fallback to `f64::INFINITY` (puts unparseable files at the end).

**Files:**
- Create: `basic PACS/rust_version/src/sorting.rs`
- Modify: `basic PACS/rust_version/src/lib.rs`
- Modify: `basic PACS/rust_version/tests/common/mod.rs` (extend `DicomFixture` to support omitting tags)
- Create: `basic PACS/rust_version/tests/sorting.rs`

- [ ] **Step 1: Extend `DicomFixture` to optionally omit tags**

Currently the synthetic-DICOM builder always writes `InstanceNumber` and other tags. Sort-fallback tests need DICOMs WITHOUT InstanceNumber, with only `ImagePositionPatient`.

In `tests/common/mod.rs`, find the `DicomFixture` struct. Add two new fields:

```rust
    /// If Some, write this ImagePositionPatient ([x, y, z]).
    pub image_position_patient: Option<[f64; 3]>,
    /// If true, omit the InstanceNumber tag entirely (for fallback-sort tests).
    pub skip_instance_number: bool,
```

In `write_synthetic`, replace the InstanceNumber block:

```rust
    if !fx.skip_instance_number {
        obj.put(DataElement::new(
            tags::INSTANCE_NUMBER,
            VR::IS,
            PrimitiveValue::from(fx.instance_number.unwrap_or(1).to_string()),
        ));
    }
```

And add an ImagePositionPatient block after the InstanceNumber one:

```rust
    if let Some(ipp) = fx.image_position_patient {
        // DS multi-valued: write as backslash-separated decimal strings
        let s = format!("{}\\{}\\{}", ipp[0], ipp[1], ipp[2]);
        obj.put(DataElement::new(
            tags::IMAGE_POSITION_PATIENT,
            VR::DS,
            PrimitiveValue::from(s),
        ));
    }
```

- [ ] **Step 2: Wire the sorting module**

Add to `src/lib.rs`:

```rust
pub mod sorting;
```

(Insert in alphabetical order between `loader` and `windowing`.)

- [ ] **Step 3: Write failing tests**

Create `tests/sorting.rs`:

```rust
mod common;

use common::{fresh_dir, write_synthetic, DicomFixture};
use rustradstack::sorting::sort_files;

#[test]
fn sort_files_orders_by_instance_number_ascending() {
    let dir = fresh_dir();
    let p3 = write_synthetic(dir.path(), "c.dcm", DicomFixture { instance_number: Some(3), ..Default::default() });
    let p1 = write_synthetic(dir.path(), "a.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    let p2 = write_synthetic(dir.path(), "b.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });

    let sorted = sort_files(vec![p3.clone(), p1.clone(), p2.clone()]);
    assert_eq!(sorted, vec![p1, p2, p3]);
}

#[test]
fn sort_files_falls_back_to_image_position_patient_z() {
    let dir = fresh_dir();
    let p_top = write_synthetic(
        dir.path(),
        "top.dcm",
        DicomFixture {
            skip_instance_number: true,
            image_position_patient: Some([0.0, 0.0, 100.0]),
            ..Default::default()
        },
    );
    let p_mid = write_synthetic(
        dir.path(),
        "mid.dcm",
        DicomFixture {
            skip_instance_number: true,
            image_position_patient: Some([0.0, 0.0, 50.0]),
            ..Default::default()
        },
    );
    let p_bot = write_synthetic(
        dir.path(),
        "bot.dcm",
        DicomFixture {
            skip_instance_number: true,
            image_position_patient: Some([0.0, 0.0, 0.0]),
            ..Default::default()
        },
    );

    let sorted = sort_files(vec![p_top.clone(), p_mid.clone(), p_bot.clone()]);
    assert_eq!(sorted, vec![p_bot, p_mid, p_top]);
}

#[test]
fn sort_files_puts_files_with_no_sort_key_at_the_end() {
    let dir = fresh_dir();
    let no_keys = write_synthetic(
        dir.path(),
        "noinfo.dcm",
        DicomFixture {
            skip_instance_number: true,
            image_position_patient: None,
            ..Default::default()
        },
    );
    let n1 = write_synthetic(dir.path(), "a.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    let n2 = write_synthetic(dir.path(), "b.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });

    let sorted = sort_files(vec![no_keys.clone(), n2.clone(), n1.clone()]);
    assert_eq!(sorted, vec![n1, n2, no_keys]);
}

#[test]
fn sort_files_handles_empty_input() {
    assert!(sort_files(vec![]).is_empty());
}
```

- [ ] **Step 4: Run — expect FAIL**

```powershell
cargo test --test sorting
```

Expected: compile error (`unresolved import rustradstack::sorting::sort_files`).

- [ ] **Step 5: Implement `sorting::sort_files`**

Create `src/sorting.rs`:

```rust
//! DICOM-aware sorting: InstanceNumber → ImagePositionPatient[2] → end.

use std::path::PathBuf;

use dicom_dictionary_std::tags;
use dicom_object::open_file;

/// Sort DICOM file paths by `InstanceNumber` ascending. Files missing
/// `InstanceNumber` fall back to `ImagePositionPatient[2]` (Z-coordinate).
/// Files missing both keys (or that fail to parse) sort to the end.
#[must_use]
pub fn sort_files(mut paths: Vec<PathBuf>) -> Vec<PathBuf> {
    paths.sort_by(|a, b| {
        let ka = sort_key(a);
        let kb = sort_key(b);
        ka.partial_cmp(&kb).unwrap_or(std::cmp::Ordering::Equal)
    });
    paths
}

fn sort_key(path: &std::path::Path) -> f64 {
    let Ok(obj) = open_file(path) else { return f64::INFINITY; };

    if let Ok(elt) = obj.element(tags::INSTANCE_NUMBER) {
        if let Ok(n) = elt.to_int::<i32>() {
            return f64::from(n);
        }
    }

    if let Ok(elt) = obj.element(tags::IMAGE_POSITION_PATIENT) {
        // ImagePositionPatient is DS with 3 values; we want index [2] (Z).
        if let Ok(values) = elt.to_multi_float64() {
            if let Some(z) = values.get(2) {
                return *z;
            }
        }
    }

    f64::INFINITY
}
```

> **API note:** `to_multi_float64()` is the dicom-rs accessor for multi-valued DS elements. If the exact name differs in 0.9.x (e.g. `to_multi_f64` or `to_floats`), check `cargo doc -p dicom-object` and adjust — the operation is "get all the f64 values from this element."

- [ ] **Step 6: Run — expect GREEN**

```powershell
cargo test --test sorting
```

Expected: 4 tests pass. If `to_multi_float64` is wrong, the compile error tells you what to use.

- [ ] **Step 7: Run full suite**

```powershell
cargo test
```

Expected: 7 unit + 15 integration = 22 tests (4 new sorting tests on top of 18).

- [ ] **Step 8: Commit**

```powershell
git add "basic PACS/rust_version/src/lib.rs" "basic PACS/rust_version/src/sorting.rs" "basic PACS/rust_version/tests/common/mod.rs" "basic PACS/rust_version/tests/sorting.rs"
git commit -m "feat(rust): sorting::sort_files orders DICOMs by InstanceNumber + IPP fallback"
```

---

## Task 4: CLI `list` subcommand

**Files:**
- Modify: `basic PACS/rust_version/src/bin/rrs-cli.rs`
- Create: `basic PACS/rust_version/tests/cli_list.rs`

- [ ] **Step 1: Update `run()` and `USAGE`, add `cmd_list`**

In `src/bin/rrs-cli.rs`:

Add to imports:

```rust
use rustradstack::loader::scan_directory;
use rustradstack::sorting::sort_files;
```

Update `USAGE`:

```rust
const USAGE: &str = "Usage:\n  rrs-cli info <FILE>\n  rrs-cli render <FILE> <OUT.png>\n  rrs-cli list <FOLDER>";
```

Add a `"list"` arm to the `run()` match:

```rust
        "list" => {
            let folder: PathBuf = args
                .next()
                .ok_or_else(|| anyhow!("list requires a <FOLDER> argument\n\n{USAGE}"))?
                .into();
            cmd_list(&folder)
        }
```

Update the module doc comment to mention the new subcommand:

```rust
//!   list <FOLDER>            List DICOM files in a folder, sorted by InstanceNumber.
```

Add `cmd_list` after `cmd_render`:

```rust
fn cmd_list(folder: &Path) -> Result<()> {
    let paths = scan_directory(folder)
        .with_context(|| format!("scanning {}", folder.display()))?;
    let sorted = sort_files(paths);
    println!("{} DICOM(s) in {}:", sorted.len(), folder.display());
    for (idx, path) in sorted.iter().enumerate() {
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("(?)");
        println!("  {:>4}  {}", idx + 1, name);
    }
    Ok(())
}
```

- [ ] **Step 2: Write integration test**

Create `tests/cli_list.rs`:

```rust
mod common;

use std::process::Command;

use common::{fresh_dir, write_synthetic, DicomFixture};

#[test]
fn cli_list_prints_files_in_instance_order() {
    let dir = fresh_dir();
    write_synthetic(dir.path(), "c.dcm", DicomFixture { instance_number: Some(3), ..Default::default() });
    write_synthetic(dir.path(), "a.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    write_synthetic(dir.path(), "b.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });

    let bin = env!("CARGO_BIN_EXE_rrs-cli");
    let out = Command::new(bin)
        .args(["list"])
        .arg(dir.path())
        .output()
        .expect("run rrs-cli");

    assert!(out.status.success(), "rrs-cli list failed: {}", String::from_utf8_lossy(&out.stderr));

    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(stdout.contains("3 DICOM(s)"), "header missing in: {stdout}");

    // Verify ordering: a.dcm appears before b.dcm appears before c.dcm in stdout.
    let idx_a = stdout.find("a.dcm").expect("a.dcm in output");
    let idx_b = stdout.find("b.dcm").expect("b.dcm in output");
    let idx_c = stdout.find("c.dcm").expect("c.dcm in output");
    assert!(idx_a < idx_b && idx_b < idx_c, "expected a < b < c, got positions {idx_a}, {idx_b}, {idx_c}");
}

#[test]
fn cli_list_handles_empty_folder() {
    let dir = fresh_dir();
    let bin = env!("CARGO_BIN_EXE_rrs-cli");
    let out = Command::new(bin).args(["list"]).arg(dir.path()).output().expect("run");
    assert!(out.status.success());
    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(stdout.contains("0 DICOM(s)"), "expected empty count: {stdout}");
}
```

- [ ] **Step 3: Run — expect PASS**

```powershell
cargo test --test cli_list
```

- [ ] **Step 4: Full suite**

```powershell
cargo test
```

Expected: 7 unit + 17 integration = 24 tests (2 new on top of 22).

- [ ] **Step 5: Smoke-test on a real series**

```powershell
cargo run --bin rrs-cli -- list "DICOM_test_files\series-000001"
```

Expected: 24 lines numbered 1–24, in InstanceNumber order. The actual filenames are `image-000001.dcm` through `image-000024.dcm` so the visual order should match the numeric order (lucky coincidence of how this dataset is named).

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/bin/rrs-cli.rs" "basic PACS/rust_version/tests/cli_list.rs"
git commit -m "feat(rust): rrs-cli list subcommand prints DICOMs in sort order"
```

---

## Task 5: README + roadmap update

- [ ] **Step 1: Update README**

In `basic PACS/rust_version/README.md`:

Update the `## CLI usage` section. After the existing `info` and `render` blocks, add a `list` block:

````markdown
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
````

Update the `## Roadmap` section. Mark slice 2 done and slice 3 as current:

```markdown
1. ✅ Slice 1 — CLI prints DICOM tags
2. ✅ Slice 2 — `apply_window` + `rrs-cli render` writes PNG
3. **Slice 3 (this slice)** — folder scan + DICOM sort + `rrs-cli list`
4. Slice 4 — egui window displays a single DICOM
5. Slice 5 — egui app loads a folder, mouse wheel scrolls
```

Update the `## Crate layout` section. Add the two new modules:

```markdown
- `src/loader.rs` — `scan_directory`
- `src/sorting.rs` — `sort_files`
- `src/windowing.rs` — `WindowSettings`, `read_metadata`, `extract_pixels`, `apply_window`
```

(Insert `loader` and `sorting` lines between `errors` and `windowing` to maintain alphabetical order.)

- [ ] **Step 2: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): README documents list subcommand and slice-3 status"
```

---

## Task 6: Profiling pass

- [ ] **Step 1: Build release**

```powershell
cargo build --release --bin rrs-cli
```

- [ ] **Step 2: Time `list` on a real series (24 files)**

```powershell
$series = "DICOM_test_files\series-000001"
1..3 | ForEach-Object {
    $ms = (Measure-Command { .\target\release\rrs-cli.exe list $series }).TotalMilliseconds
    Write-Host "list run $_: $ms ms"
}
```

Take the median.

- [ ] **Step 3: Update README perf table**

Add a row to the existing `## Performance notes` table:

```markdown
| `rrs-cli list` (24-file MR series, sort by InstanceNumber) | — | ~XXms |
```

Replace `~XXms` with the median.

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "perf(rust): record slice-3 list timing on 24-file series"
```

---

## Task 7: Clippy / refactor pass

- [ ] **Step 1: Run clippy**

```powershell
cargo clippy --all-targets -- -W clippy::pedantic -W clippy::nursery
```

- [ ] **Step 2: Apply suggestions that improve clarity**

Pay attention to:
- `loader::scan_directory` — recursion vs iterative, error handling on dir entries
- `sorting::sort_key` — the let-else + nested if-let pattern (clippy may suggest `?` + Option chain)

Reject pedantic nits with targeted `#[allow(...)]` + reason.

- [ ] **Step 3: Read each modified-this-slice file with fresh eyes**

`src/windowing.rs`, `src/loader.rs`, `src/sorting.rs`, `src/bin/rrs-cli.rs`, `tests/common/mod.rs`, `tests/loader.rs`, `tests/sorting.rs`, `tests/cli_list.rs`.

Apply readability fixes inline.

- [ ] **Step 4: Confirm green**

```powershell
cargo test
cargo clippy --all-targets
```

Expected: 24 tests pass; clippy clean.

- [ ] **Step 5: Commit**

```powershell
git add "basic PACS/rust_version"
git commit -m "refactor(rust): clippy pass + readability cleanup for slice 3"
```

---

## Done criteria

- [ ] `cargo build --release` clean
- [ ] `cargo test` green — 24 tests (7 unit + 17 integration)
- [ ] `cargo clippy --all-targets` clean
- [ ] `rrs-cli list <real-series>` returns the right number of files in correct order
- [ ] `extract_pixels` no longer called by `cmd_info` (slice-2 debt cleared)
- [ ] README documents `list`; slice 3 marked current in roadmap

## Out of scope (for slice 4+)

- egui GUI (slice 4)
- Multi-slice navigation / scrolling (slice 5)
- ImageStack data model (slice 4)
- JPG/PNG support in loader (descoped from MVP)
