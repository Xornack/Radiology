# RustRadStack — Slice 9 Implementation Plan (JPG/PNG support)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute. Steps use `- [ ]` checkbox syntax.

**Goal:** Treat folders containing `.jpg`, `.jpeg`, or `.png` files like DICOM folders — `loader::scan_directory` includes them, `ImageStack::get_current_image` decodes them via the `image` crate, and the GUI shows them. Matches PyRadStack's `SUPPORTED_EXTENSIONS = {".dcm", ".jpg", ".jpeg", ".png"}`. W/L drag has no effect on non-DICOM slices (they don't have HU values).

**Architecture:** Three module changes:
- `loader::scan_directory` — extend `is_dicom` (rename to `is_supported`) to also accept jpg/jpeg/png.
- `sorting::sort_files` — non-DICOM files use a path-based sort key (alphabetical by filename) instead of falling through to `f64::INFINITY`. Existing DICOMs keep InstanceNumber→IPP→INFINITY ordering. Mixed folders sort DICOMs first by tag, non-DICOMs after by name.
- `stack::ImageStack::get_current_image` — branch on extension. DICOM uses existing pipeline. JPG/PNG opens via `image::open(path).into_luma8()` (already 8-bit grayscale, ready for direct display). Override W/L is silently ignored for non-DICOM slices.

**Tech Stack:** No new deps — `image` is already in Cargo.toml.

Working dir: `basic PACS/rust_version/` (worktree root: `basic PACS/.claude/worktrees/jpg-png/`).

---

## Task 1: Extend `loader::scan_directory` to accept JPG/PNG

**Files:**
- Modify: `basic PACS/rust_version/src/loader.rs`
- Modify: `basic PACS/rust_version/tests/loader.rs`

- [ ] **Step 1: Write a failing test**

In `tests/loader.rs`, add:

```rust
use std::fs::File;
use std::io::Write;

#[test]
fn scan_directory_includes_jpg_jpeg_png_files() {
    let dir = fresh_dir();
    let dcm = write_synthetic(dir.path(), "ct.dcm", DicomFixture::default());
    // Write minimal placeholder files for jpg/jpeg/png — content doesn't matter
    // for scan_directory (which filters by extension only).
    let jpg = dir.path().join("photo.jpg");
    File::create(&jpg).unwrap().write_all(b"placeholder").unwrap();
    let jpeg = dir.path().join("photo.jpeg");
    File::create(&jpeg).unwrap().write_all(b"placeholder").unwrap();
    let png = dir.path().join("photo.png");
    File::create(&png).unwrap().write_all(b"placeholder").unwrap();
    // Confirm a non-image extension is still excluded.
    fs::write(dir.path().join("notes.txt"), "ignore").unwrap();

    let found = scan_directory(dir.path()).expect("scan");
    assert_eq!(found.len(), 4, "should find dcm + jpg + jpeg + png, not txt: {found:?}");
    assert!(found.contains(&dcm));
    assert!(found.contains(&jpg));
    assert!(found.contains(&jpeg));
    assert!(found.contains(&png));
}
```

(Note: this test imports `std::fs::File` and `std::io::Write`, and uses the existing `fs` import at the top of the file. The existing tests at the top of the file already do `use std::fs;` so that part is already wired.)

- [ ] **Step 2: Run — expect FAIL**

```powershell
cargo test --test loader
```

Expected: assertion fails — `found.len()` is 1 (just the .dcm), not 4.

- [ ] **Step 3: Update `is_dicom` in `src/loader.rs`**

Rename it to `is_supported` and broaden the predicate:

```rust
fn is_supported(path: &Path) -> bool {
    let Some(ext) = path.extension().and_then(|e| e.to_str()) else {
        return false;
    };
    matches!(
        ext.to_ascii_lowercase().as_str(),
        "dcm" | "jpg" | "jpeg" | "png"
    )
}
```

Update the only caller (`walk`) to use the new name:

```rust
} else if file_type.is_file() && is_supported(&path) {
    out.push(path);
}
```

Also update the doc comment on `scan_directory`:

```rust
/// Recursively walk `dir` and return all supported image files (DICOM, JPG, JPEG, PNG —
/// case-insensitive extension match) in alphabetical-by-path order.
```

- [ ] **Step 4: Run — expect GREEN**

```powershell
cargo test --test loader
```

Expected: 5 loader tests pass (4 original + 1 new).

- [ ] **Step 5: Run full suite**

```powershell
cargo test
```

Expected: 30 tests pass (29 from before + 1 new loader test).

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/loader.rs" "basic PACS/rust_version/tests/loader.rs"
git commit -m "feat(rust): scan_directory includes .jpg/.jpeg/.png files"
```

---

## Task 2: Update `sorting::sort_files` for non-DICOM files

After Task 1, mixed folders can contain DICOMs and JPG/PNG. The existing sort key returns `f64::INFINITY` for any file that can't be parsed as DICOM — which would lump JPG/PNG together with broken DICOMs. PyRadStack sorts non-DICOMs alphabetically by filename. Match that.

**Files:**
- Modify: `basic PACS/rust_version/src/sorting.rs`
- Modify: `basic PACS/rust_version/tests/sorting.rs`

- [ ] **Step 1: Write a failing test**

In `tests/sorting.rs`, append:

```rust
use std::fs;

#[test]
fn sort_files_puts_non_dicom_files_after_dicoms_in_alphabetical_order() {
    let dir = fresh_dir();
    // Two DICOMs with InstanceNumber 1 and 2
    let d1 = write_synthetic(dir.path(), "ct1.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    let d2 = write_synthetic(dir.path(), "ct2.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });
    // Two non-DICOM placeholder files
    let png = dir.path().join("zebra.png");
    fs::write(&png, b"placeholder").unwrap();
    let jpg = dir.path().join("apple.jpg");
    fs::write(&jpg, b"placeholder").unwrap();

    // Mixed input, scrambled order
    let sorted = sort_files(vec![png.clone(), d2.clone(), jpg.clone(), d1.clone()]);

    // Expect: DICOMs first by InstanceNumber, then non-DICOMs alphabetical by filename.
    assert_eq!(sorted, vec![d1, d2, jpg, png]);
}
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
cargo test --test sorting
```

Expected: the test fails because non-DICOMs currently get `f64::INFINITY` and sort together but in path-tie-breaker order, not the explicit alphabetical-by-filename we want.

- [ ] **Step 3: Update `sorting::sort_files` to partition DICOMs vs non-DICOMs**

Modify `src/sorting.rs`. Replace the body of `sort_files` with:

```rust
#[must_use]
pub fn sort_files(paths: Vec<PathBuf>) -> Vec<PathBuf> {
    let (mut dicoms, mut others): (Vec<_>, Vec<_>) =
        paths.into_iter().partition(|p| is_dicom_extension(p));
    dicoms.sort_by(|a, b| {
        let ka = sort_key(a);
        let kb = sort_key(b);
        ka.partial_cmp(&kb).unwrap_or(std::cmp::Ordering::Equal)
    });
    others.sort_by(|a, b| {
        // Compare by filename (case-insensitive) so "Zoo.png" sorts after "apple.jpg".
        let na = a.file_name().and_then(|n| n.to_str()).unwrap_or("").to_ascii_lowercase();
        let nb = b.file_name().and_then(|n| n.to_str()).unwrap_or("").to_ascii_lowercase();
        na.cmp(&nb)
    });
    dicoms.into_iter().chain(others).collect()
}

fn is_dicom_extension(path: &std::path::Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("dcm"))
}
```

(`sort_key` from before stays — it's still used for the DICOM partition.)

- [ ] **Step 4: Run — expect GREEN**

```powershell
cargo test --test sorting
```

Expected: 5 sorting tests pass (4 original + 1 new).

- [ ] **Step 5: Full suite**

```powershell
cargo test
```

Expected: 31 tests pass.

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/sorting.rs" "basic PACS/rust_version/tests/sorting.rs"
git commit -m "feat(rust): sort_files puts non-DICOM images after DICOMs (alphabetical)"
```

---

## Task 3: Branch `ImageStack::get_current_image` on extension

Decode JPG/PNG via `image::open(path).into_luma8()`. DICOM uses the existing pipeline. Override W/L is silently ignored for non-DICOM (no HU values to clamp).

**Files:**
- Modify: `basic PACS/rust_version/src/stack.rs`
- Modify: `basic PACS/rust_version/tests/stack.rs`

- [ ] **Step 1: Write a failing test**

In `tests/stack.rs`, append:

```rust
use std::fs;

#[test]
fn image_stack_renders_png_via_image_crate() {
    use image::{ImageBuffer, Luma};
    let dir = fresh_dir();
    // Build a 4x4 grayscale ramp PNG and write it
    let buf: ImageBuffer<Luma<u8>, Vec<u8>> =
        ImageBuffer::from_fn(4, 4, |x, y| Luma([(y * 4 + x) as u8 * 16]));
    let png_path = dir.path().join("ramp.png");
    buf.save(&png_path).expect("save png");

    let stack = ImageStack::new(vec![png_path]);
    let img = stack.get_current_image().expect("decode png");
    assert_eq!(img.dimensions(), (4, 4));
    // Ramp pixel (2, 1) should be (1*4+2)*16 = 96
    assert_eq!(img.get_pixel(2, 1).0[0], 96);
}

#[test]
fn image_stack_ignores_override_window_for_png() {
    use image::{ImageBuffer, Luma};
    let dir = fresh_dir();
    let buf: ImageBuffer<Luma<u8>, Vec<u8>> = ImageBuffer::from_fn(2, 2, |_, _| Luma([100]));
    let png_path = dir.path().join("flat.png");
    buf.save(&png_path).expect("save png");

    let mut stack = ImageStack::new(vec![png_path]);
    let img_no_override = stack.get_current_image().expect("decode");
    stack.set_override_window(Some((10.0, 5.0))); // would clamp to black if applied
    let img_with_override = stack.get_current_image().expect("decode");
    // Both renders should be identical — override has no effect on PNG.
    assert_eq!(img_no_override.as_raw(), img_with_override.as_raw());
}
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
cargo test --test stack
```

Expected: both new tests fail. The PNG decode test fails because the current `get_current_image` calls `extract_pixels` which calls `dicom_object::open_file` — which will return an error on a PNG file. The override test fails for the same reason.

- [ ] **Step 3: Update `get_current_image`**

In `src/stack.rs`, find the body of `get_current_image`. The current cache-miss path looks like:

```rust
let path = &self.paths[self.current];
let obj = open_file(path).map_err(|e| RrsError::Dicom(e.to_string()))?;
let (pixels, dims, mut ws) = extract_pixels(&obj)?;
if let Some((center, width)) = self.override_window {
    ws.center = center;
    ws.width = width;
}
let img = apply_window(&pixels, dims, ws);
```

Branch on extension. Add `is_dicom_path` as a private free function below the impl block and use it in `get_current_image`:

```rust
let path = &self.paths[self.current];
let img = if is_dicom_path(path) {
    let obj = open_file(path).map_err(|e| RrsError::Dicom(e.to_string()))?;
    let (pixels, dims, mut ws) = extract_pixels(&obj)?;
    if let Some((center, width)) = self.override_window {
        ws.center = center;
        ws.width = width;
    }
    apply_window(&pixels, dims, ws)
} else {
    // JPG/PNG: open with the image crate, force-convert to 8-bit grayscale.
    // Override W/L is intentionally ignored — no HU values to map.
    image::open(path)
        .map_err(|e| RrsError::Dicom(format!("decode {}: {}", path.display(), e)))?
        .into_luma8()
};
```

Add the helper at the bottom of the file (outside the impl):

```rust
fn is_dicom_path(path: &std::path::Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("dcm"))
}
```

> **Note:** `RrsError::Dicom` is repurposed slightly here for image-decode errors. That's a small naming abuse — a future slice could rename to `RrsError::Decode` or add a `RrsError::Image` variant. For slice 9, the user-visible error message ("decode <path>: <err>") is what matters; the variant name is internal.

- [ ] **Step 4: Run — expect GREEN**

```powershell
cargo test --test stack
```

Expected: 8 stack tests pass (6 original + 2 new).

- [ ] **Step 5: Full suite**

```powershell
cargo test
```

Expected: 33 tests pass.

- [ ] **Step 6: Commit**

```powershell
git add "basic PACS/rust_version/src/stack.rs" "basic PACS/rust_version/tests/stack.rs"
git commit -m "feat(rust): ImageStack decodes .jpg/.jpeg/.png via image crate"
```

---

## Task 4: Verify CLI subcommands work on non-DICOM (or fail gracefully)

The slice-2 `rrs-cli render` and `rrs-cli info` subcommands assume DICOM input. With slice 9's broader scan, a `rrs-cli list <folder>` containing JPG/PNG should still work (list doesn't open files). But `rrs-cli info path/to/photo.jpg` would currently fail with a confusing dicom-rs error — we should at least confirm the failure mode, possibly improve it.

**Files:** none changed — this is a verification-only task. If any change is needed, it goes in the next slice or a fix-up commit.

- [ ] **Step 1: Run `rrs-cli list` on a synthetic mixed folder**

Inline test (in your shell, not a `cargo test` test):

```bash
mkdir -p /tmp/mixed-test
cp "C:/Users/harwo/OneDrive/Documents/Radiology/basic PACS/rust_version/DICOM_test_files/series-000001/image-000001.dcm" /tmp/mixed-test/
echo "fake png content" > /tmp/mixed-test/zebra.png
echo "fake jpg content" > /tmp/mixed-test/apple.jpg
cargo run --bin rrs-cli -- list /tmp/mixed-test
```

Expected output:

```
3 DICOM(s) in /tmp/mixed-test:
   1  image-000001.dcm
   2  apple.jpg
   3  zebra.png
```

(The "3 DICOM(s)" header is now a misnomer — it really means "3 supported files." That's a minor wording bug for a future slice; not addressed in slice 9.)

- [ ] **Step 2: Run `rrs-cli info` on a JPG**

```bash
echo "fake jpg content" > /tmp/test.jpg
cargo run --bin rrs-cli -- info /tmp/test.jpg
```

Expected: an error message about not being a valid DICOM file (some flavor of dicom-rs error wrapped through anyhow). The exit code should be non-zero. The error doesn't have to be pretty for slice 9 — `info` is DICOM-specific by design.

- [ ] **Step 3: Run `rrs-cli render` on a JPG**

```bash
cargo run --bin rrs-cli -- render /tmp/test.jpg /tmp/out.png
```

Expected: same — DICOM-specific parser error. `rrs-cli render` is also DICOM-specific.

These error paths aren't great UX but they're acceptable for slice 9. The GUI binary (`rustradstack`) is the path that handles JPG/PNG correctly because it goes through `ImageStack::get_current_image` which has the extension branch.

If you find any of these fail in a way that crashes/panics rather than printing an error and exiting non-zero, that's a real bug — escalate.

**No commit for this task** — it's verification only. Move directly to Task 5.

---

## Task 5: Manual smoke-test the GUI on a mixed folder

Build a small folder containing a few real DICOMs from your test set + a few JPG/PNG screenshots. Open it in the GUI. Scroll through. DICOMs should render with W/L; JPG/PNG should render as 8-bit grayscale with no W/L (override drag does nothing on those slices).

**Files:** none changed. This is a manual sanity check.

- [ ] **Step 1: Build a mixed-content folder**

In PowerShell (the user can do this; the implementer may not have a display):

```powershell
$mixed = New-Item -ItemType Directory -Path "$env:TEMP\rrs-mixed" -Force
# Copy 3 DICOMs from a real series
1..3 | ForEach-Object {
    Copy-Item "C:\Users\harwo\OneDrive\Documents\Radiology\basic PACS\rust_version\DICOM_test_files\series-000001\image-00000$_.dcm" $mixed.FullName
}
# Copy any handy JPG/PNG (Windows ships with samples)
# E.g.: Copy-Item "$env:USERPROFILE\Pictures\*.jpg" $mixed.FullName -ErrorAction SilentlyContinue
# Or generate a quick PNG via Python if available
```

If the implementer can't do this manually because no display: skip this step and document "deferred to user manual test."

- [ ] **Step 2: Open the mixed folder via the GUI**

```powershell
.\target\release\rustradstack.exe $mixed.FullName
```

Expected: scrolling through shows DICOMs first (rendered with W/L from their tags), then JPG/PNG (rendered as-is). W/L drag affects DICOMs; on JPG/PNG slices the W/L drag is silently ignored.

If headless, defer this to the user's manual test pass.

**No commit for this task** — verification only. Move to Task 6.

---

## Task 6: README + clippy pass

**Files:** `basic PACS/rust_version/README.md`, possibly source files for clippy.

- [ ] **Step 1: Update README**

Find the existing description in any section that mentions "DICOM files" — slice 9 broadens scope to also include common image formats. Most concrete change: add a bullet near the GUI usage section:

```markdown
**Supported file types:** DICOM (`.dcm`), plus JPG/JPEG/PNG (rendered as 8-bit grayscale,
no Window/Level applied). Mixed folders are supported; DICOMs sort first by InstanceNumber,
non-DICOMs alphabetically by filename.
```

Place this just below the existing **Loading new series** note.

Update Roadmap:

```markdown
1. ✅ Slice 1 — CLI prints DICOM tags
2. ✅ Slice 2 — `apply_window` + `rrs-cli render` writes PNG
3. ✅ Slice 3 — folder scan + DICOM sort + `rrs-cli list`
4. ✅ Slice 4 — egui window displays a single DICOM
5. ✅ Slice 5 — egui app loads a folder, mouse wheel scrolls
6. ✅ Slice 6 — scroll polish: throttled wheel + left-click drag scroll
7. ✅ Slice 7 — both-button drag adjusts W/L
8. ✅ Slice 8 — File menu + Open Folder/File dialogs
9. ✅ Slice 9 (this slice) — JPG/JPEG/PNG support in viewer + scan + sort

**MVP+ in progress.** Future slices: Nuitka-equivalent build (cargo packaging), W/L presets, recent-files list.
```

- [ ] **Step 2: Commit README**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): README documents JPG/PNG support (slice 9)"
```

- [ ] **Step 3: Clippy pass**

```powershell
cargo clippy --all-targets -- -W clippy::pedantic -W clippy::nursery
```

Apply suggestions that improve clarity. Specific items to consider:
- The `is_dicom_extension` in sorting.rs and `is_dicom_path` in stack.rs do the same thing. If clippy doesn't flag the duplication, fine — they're tiny private helpers. If it bothers a fresh-eyes read, consider extracting to a public `loader::is_dicom` (or similar) and using that in both places.
- The `RrsError::Dicom` variant is now used for image-crate decode errors too. Clippy won't catch this; it's a documentation/design note, not a fix for slice 9.

Confirm:

```powershell
cargo test
cargo clippy --all-targets
```

Expected: 33 tests pass; clippy clean.

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version"
git commit -m "refactor(rust): clippy pass + readability cleanup for slice 9"
```

---

## Done criteria

- [ ] `cargo build --release` clean
- [ ] `cargo test` green — 33 tests (7 unit + 26 integration: 1 fixture_smoke, 2 windowing, 1 cli_info, 2 cli_render, 5 loader, 5 sorting, 2 cli_list, 8 stack)
- [ ] `cargo clippy --all-targets` clean
- [ ] Manual smoke (user): mixed folder loads + scrolls through DICOMs and JPG/PNGs in expected order
- [ ] README documents JPG/PNG support

## Out of scope (for future slices)

- Color (RGB) image support — current path force-converts to luma; color JPGs lose chroma. Defer.
- W/L on non-DICOM (treating 8-bit luma as if it were HU) — defer; not in PyRadStack either.
- "X DICOM(s)" header in `rrs-cli list` is now a misnomer when JPG/PNG are present. Cosmetic. Defer.
- Better error messages when `rrs-cli info`/`render` are pointed at JPG/PNG — defer.
- Loading directly via drag-and-drop. Defer.
