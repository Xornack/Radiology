# RustRadStack — Slice 8 Implementation Plan (File menu + Open dialog)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute. Steps use `- [ ]` checkbox syntax.

**Goal:** Add a `File` menu to the GUI window with `Open Folder...` and `Open File...` items that pop a native file picker. Selecting a path swaps the `ImageStack` mid-session — no restart needed. Resets W/L override and texture cache so each new series starts clean.

**Architecture:** Add `rfd` (Rust File Dialog) crate for the native picker. egui's `egui::menu::bar` paints a top menubar inside a `TopBottomPanel`. Menu items dispatch to a `ViewerApp::load_path(&Path)` method that runs the same scan-sort-stack pipeline `main.rs` uses for argv input. Errors (empty folder, unreadable file) display as a transient label at the top of the central panel — no dialog spam, no crashes.

**Tech Stack:** Add `rfd = "0.15"` (or whatever cargo resolves). No other new deps.

Working dir: `basic PACS/rust_version/` (worktree root: `basic PACS/.claude/worktrees/file-menu/`).

---

## Task 1: Add `rfd` dependency

**Files:** `basic PACS/rust_version/Cargo.toml` + lockfile

- [ ] **Step 1: Add the dep**

```powershell
cargo add rfd
```

Cargo picks the latest stable. If there's a version conflict (e.g. with eframe's transitive deps), accept whatever the resolver settles on. `rfd` is a thin wrapper over the OS file picker (Windows uses `IFileDialog`, macOS uses `NSOpenPanel`, Linux uses `xdg-portal` or zenity).

- [ ] **Step 2: Verify the build still passes**

```powershell
cargo build
```

Expected: clean build. First build may take a while if rfd's deps are large (Win32 bindings). Source code doesn't use rfd yet.

- [ ] **Step 3: Verify tests still pass**

```powershell
cargo test
```

Expected: 29 tests pass.

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version/Cargo.toml" "basic PACS/rust_version/Cargo.lock"
git commit -m "build(rust): add rfd dep for native file picker (slice 8)"
```

---

## Task 2: Refactor stack-construction logic out of `main.rs`

The existing `main.rs::run()` function builds an `ImageStack` from a path arg. Slice 8's menu items need the same logic. Extract it into a library helper so both `main.rs` (startup arg) and `viewer.rs` (menu click) can call it.

**Files:**
- Modify: `basic PACS/rust_version/src/lib.rs`
- Create: `basic PACS/rust_version/src/loading.rs`
- Modify: `basic PACS/rust_version/src/main.rs`

- [ ] **Step 1: Wire the new module**

In `src/lib.rs`, add `pub mod loading;` in alphabetical order (between `loader` and `sorting`).

- [ ] **Step 2: Create `src/loading.rs`**

```rust
//! Convert a user-supplied path (file or folder) into a sorted Vec<PathBuf>
//! ready to feed into ImageStack::new.

use std::path::{Path, PathBuf};

use crate::loader::scan_directory;
use crate::sorting::sort_files;

/// Result of trying to build a stack from a path.
#[derive(Debug)]
pub enum LoadError {
    /// Path doesn't exist or is neither a file nor a directory.
    NotFile(PathBuf),
    /// Recursive scan failed (permission denied, etc.).
    ScanFailed(std::io::Error),
    /// Folder scanned successfully but contained no DICOM files.
    Empty(PathBuf),
}

impl std::fmt::Display for LoadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NotFile(p) => write!(f, "not a file or directory: {}", p.display()),
            Self::ScanFailed(e) => write!(f, "scan failed: {e}"),
            Self::Empty(p) => write!(f, "no DICOM files found in {}", p.display()),
        }
    }
}

impl std::error::Error for LoadError {}

/// Build a sorted Vec<PathBuf> from a file or folder path. Returns LoadError
/// on missing path, scan failure, or empty folder.
///
/// # Errors
/// See `LoadError` variants.
pub fn paths_for(arg: &Path) -> Result<Vec<PathBuf>, LoadError> {
    if arg.is_dir() {
        let scanned = scan_directory(arg).map_err(LoadError::ScanFailed)?;
        let sorted = sort_files(scanned);
        if sorted.is_empty() {
            return Err(LoadError::Empty(arg.to_path_buf()));
        }
        Ok(sorted)
    } else if arg.is_file() {
        Ok(vec![arg.to_path_buf()])
    } else {
        Err(LoadError::NotFile(arg.to_path_buf()))
    }
}
```

- [ ] **Step 3: Update `main.rs` to use the new helper**

In `src/main.rs`, find the existing path-handling block in `run()`:

```rust
let paths: Vec<PathBuf> = if arg.is_dir() {
    let scanned = scan_directory(&arg)
        .with_context(|| format!("scanning {}", arg.display()))?;
    sort_files(scanned)
} else if arg.is_file() {
    vec![arg.clone()]
} else {
    return Err(anyhow!("{} is neither a file nor a directory", arg.display()));
};

if paths.is_empty() {
    return Err(anyhow!("no DICOM files found in {}", arg.display()));
}
```

Replace with:

```rust
let paths = rustradstack::loading::paths_for(&arg)
    .map_err(|e| anyhow!("{e}"))?;
```

Remove the now-unused `scan_directory` and `sort_files` imports from `main.rs`.

- [ ] **Step 4: Verify build + tests**

```powershell
cargo build
cargo test
```

Expected: 29 tests still pass. `cargo run --bin rustradstack -- ...` should work identically to before.

- [ ] **Step 5: Commit**

```powershell
git add "basic PACS/rust_version/src/lib.rs" "basic PACS/rust_version/src/loading.rs" "basic PACS/rust_version/src/main.rs"
git commit -m "refactor(rust): extract path→paths logic into loading::paths_for"
```

---

## Task 3: Add `ViewerApp::load_path` method + tests

The viewer needs a way to swap its stack mid-session. Add a method that takes a path, runs `paths_for`, and either replaces the stack (success) or stashes an error message for display.

**Files:**
- Modify: `basic PACS/rust_version/src/viewer.rs`

- [ ] **Step 1: Add error-message state + load_path method**

Modify `ViewerApp` struct to add a transient error message field:

```rust
pub struct ViewerApp {
    stack: Option<ImageStack>,
    texture: Option<egui::TextureHandle>,
    texture_key: Option<TextureKey>,
    wheel_accum: f32,
    drag_accum: f32,
    /// Last file-load error (shown as a transient label until the next successful load).
    load_error: Option<String>,
}
```

Update both `ViewerApp::new` and `ViewerApp::empty` to initialize `load_error: None`.

Add the method below the constructors:

```rust
/// Load a new file or folder into the viewer, replacing the current stack.
/// Resets W/L override and texture cache so the new series starts clean.
/// On failure, the previous stack stays visible and an error label is shown.
pub fn load_path(&mut self, path: &std::path::Path) {
    match crate::loading::paths_for(path) {
        Ok(paths) => {
            self.stack = Some(ImageStack::new(paths));
            self.texture = None;
            self.texture_key = None;
            self.wheel_accum = 0.0;
            self.drag_accum = 0.0;
            self.load_error = None;
        }
        Err(e) => {
            self.load_error = Some(e.to_string());
        }
    }
}
```

Note that `load_path` doesn't touch `self.load_error` on success — clears it. On failure, the existing stack/texture remain intact (the user keeps seeing the previous series).

- [ ] **Step 2: Verify build**

```powershell
cargo build
```

- [ ] **Step 3: Commit**

```powershell
git add "basic PACS/rust_version/src/viewer.rs"
git commit -m "feat(rust): ViewerApp::load_path swaps stack mid-session"
```

---

## Task 4: Add the File menu UI

Top menubar with `File → Open Folder...` and `File → Open File...`. Use `rfd::FileDialog` for the native picker.

**Files:** Modify `basic PACS/rust_version/src/viewer.rs`

- [ ] **Step 1: Add the menubar paint code**

In `fn ui`, BEFORE the existing input-reading block, paint the menubar in a `TopBottomPanel`:

```rust
// Top menubar — file open dialogs.
egui::TopBottomPanel::top("menubar").show_inside(ui, |ui| {
    egui::menu::bar(ui, |ui| {
        ui.menu_button("File", |ui| {
            if ui.button("Open Folder…").clicked() {
                ui.close_menu();
                if let Some(folder) = rfd::FileDialog::new()
                    .set_title("Open DICOM folder")
                    .pick_folder()
                {
                    self.load_path(&folder);
                }
            }
            if ui.button("Open File…").clicked() {
                ui.close_menu();
                if let Some(file) = rfd::FileDialog::new()
                    .set_title("Open DICOM file")
                    .add_filter("DICOM", &["dcm"])
                    .pick_file()
                {
                    self.load_path(&file);
                }
            }
        });
    });
});
```

> **Note on the menubar approach:** egui's `fn ui` gives us a single `Ui` representing the central panel. To get a menubar above the content, we use `TopBottomPanel::top("menubar").show_inside(ui, ...)` — `show_inside` makes the panel paint inside our existing `Ui` rather than at the egui root (which would clash with the central layout). This is the eframe-0.34 idiomatic pattern.

> **`ui.close_menu()`:** without this, the menu stays open after clicking. The picker call blocks the GUI while open (rfd is sync), which feels right for a file dialog.

> **`rfd::FileDialog::pick_folder()` and `pick_file()`** are the synchronous APIs. They block the egui frame while the OS dialog is up — that's fine; egui just stops repainting. There's also an async API (`pick_folder_async`); we don't need it here.

- [ ] **Step 2: Show the load error (if any) at the top of the central area**

Just inside the existing `ui.vertical_centered(|ui| { ... })` block (BEFORE the `if let Some(tex) = ...` part), add:

```rust
if let Some(err) = &self.load_error {
    ui.colored_label(egui::Color32::LIGHT_RED, format!("Load error: {err}"));
}
```

This way the error sits above the image area and persists until the next successful load.

- [ ] **Step 3: Build + tests**

```powershell
cargo build
cargo test
```

Expected: 29 tests still pass.

- [ ] **Step 4: Manual smoke-test (if you have a display)**

```powershell
cargo run --release --bin rustradstack -- "C:\Users\harwo\OneDrive\Documents\Radiology\basic PACS\rust_version\DICOM_test_files\series-000001"
```

Expected:
- Window opens with "File" menu visible at the top
- Click File → Open Folder… → native folder picker opens
- Pick `series-000002` → image switches, "Slice 1 / 24" updates, scroll/W/L work on the new series
- Click File → Open File… → native file picker (filtered to .dcm) opens
- Pick a single .dcm → switches to single-slice mode
- Pick an invalid path or empty folder → red "Load error: …" label appears at top, previous stack remains usable

If headless, just confirm `cargo build` succeeds.

- [ ] **Step 5: Commit**

```powershell
git add "basic PACS/rust_version/src/viewer.rs"
git commit -m "feat(rust): File menu with Open Folder/File dialogs (rfd)"
```

---

## Task 5: README + clippy pass

**Files:** `basic PACS/rust_version/README.md`, possibly `src/viewer.rs` and `src/loading.rs` for clippy.

- [ ] **Step 1: Update README GUI usage**

Add a note about the File menu just below the Controls section:

````markdown
**Loading new series:** use **File → Open Folder…** or **File → Open File…**
to switch series mid-session. Native OS picker. Window/Level resets to per-file
defaults on each load.
````

Update Roadmap:

```markdown
1. ✅ Slice 1 — CLI prints DICOM tags
2. ✅ Slice 2 — `apply_window` + `rrs-cli render` writes PNG
3. ✅ Slice 3 — folder scan + DICOM sort + `rrs-cli list`
4. ✅ Slice 4 — egui window displays a single DICOM
5. ✅ Slice 5 — egui app loads a folder, mouse wheel scrolls
6. ✅ Slice 6 — scroll polish: throttled wheel + left-click drag scroll
7. ✅ Slice 7 — both-button drag adjusts W/L
8. ✅ Slice 8 (this slice) — File menu + Open Folder/File dialogs

**MVP+ in progress.** Future slices: JPG/PNG support, Nuitka build, W/L presets.
```

Update Crate layout to add `loading.rs`:

```markdown
- `src/loading.rs` — `paths_for` (path → sorted Vec<PathBuf>)
```

(In alphabetical order between `loader.rs` and `sorting.rs`.)

- [ ] **Step 2: Commit README**

```powershell
git add "basic PACS/rust_version/README.md"
git commit -m "docs(rust): README documents File menu (slice 8)"
```

- [ ] **Step 3: Clippy pass**

```powershell
cargo clippy --all-targets -- -W clippy::pedantic -W clippy::nursery
```

Apply suggestions that improve clarity. Pay attention to:
- `LoadError` variants — clippy may suggest `#[non_exhaustive]` for future-proofing. Apply if you intend to add more variants later (likely yes — invalid file content errors will eventually surface). Otherwise leave.
- `paths_for` — straightforward; few warnings expected.
- `ViewerApp::load_path` — the stack + texture + accum reset block could be extracted into a `ViewerApp::reset_state` private helper. Judgment call.

Confirm:

```powershell
cargo test
cargo clippy --all-targets
```

Expected: 29 tests pass, clippy clean.

- [ ] **Step 4: Commit**

```powershell
git add "basic PACS/rust_version"
git commit -m "refactor(rust): clippy pass + readability cleanup for slice 8"
```

---

## Done criteria

- [ ] `cargo build --release` clean
- [ ] `cargo test` green — 29 tests
- [ ] `cargo clippy --all-targets` clean
- [ ] Manual smoke test (user): File → Open Folder picks a series and switches the viewer; File → Open File picks a single .dcm
- [ ] Invalid path → red error label, previous stack stays visible
- [ ] README documents the File menu

## Out of scope (for slice 9+)

- JPG/PNG support (slice 9)
- Recent-files list (defer)
- File → Save As (image export to PNG via GUI; CLI render already covers this)
- Drag-and-drop a folder onto the window (defer)
- Keyboard shortcut (Ctrl+O) for Open Folder (defer)
