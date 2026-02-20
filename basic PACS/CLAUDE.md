# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PyRadStack** — a lightweight Python radiology image viewer that mimics PACS workstation functionality. Loads folders of images (DICOM, PNG, JPG) as volumetric stacks with mouse-wheel scrolling through slices.

## Technology Stack

- Python 3.13 (venv in `venv/`)
- PyQt6 for GUI
- pydicom for DICOM metadata/pixel extraction
- numpy for array manipulation and Window/Level transforms
- Pillow for non-DICOM image formats

## Architecture

The application is a desktop PyQt6 viewer with these core responsibilities:

- **Image Loading:** Recursively scan directories for `.dcm`, `.jpg`, `.png` files. Use lazy loading or async worker threads for performance with large DICOM sets.
- **Sorting:** DICOM files sort by `InstanceNumber` (tag `0020,0013`) or `ImagePositionPatient`, not filename. Standard images sort alphanumerically.
- **Windowing:** Raw DICOM pixel data (12-16 bit) is clipped/normalized using `WindowCenter`/`WindowWidth` tags via numpy, then converted to 8-bit QImages for display.
- **Scrolling:** Mouse wheel drives Z-stack traversal (cine mode), mimicking standard PACS behavior.

## Development Commands

```bash
# Activate virtual environment
source venv/Scripts/activate        # Git Bash on Windows
venv\Scripts\activate               # CMD on Windows

# Install all dependencies (production + test)
pip install PyQt6 pydicom numpy Pillow pytest pytest-qt pytest-cov

# Run the application
python main.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_image_loader.py

# Run a single test by name
pytest tests/test_image_loader.py::test_scan_finds_dcm_files -v

# Run tests with coverage report
pytest --cov=pyradstack --cov-report=term-missing

# Run only tests matching a keyword
pytest -k "windowing" -v
```

## Key Domain Concepts

- **HU (Hounsfield Units):** CT density scale. Window/Level controls map HU ranges to displayable grayscale.
- **Instance Number:** DICOM tag determining slice order in the Z-axis. Critical for correct stack ordering.
- **W/L (Window/Level):** Window Width controls contrast range; Window Center controls brightness midpoint.

## TDD Implementation Plan

Build the project in the order below. Each phase follows Red-Green-Refactor: write a failing test first, implement the minimum code to pass it, then refactor.

### Phase 1: Project Skeleton & Image Discovery

**Module:** `pyradstack/loader.py`
**Test file:** `tests/test_loader.py`

1. **Test:** `scan_directory` given a temp dir with `.dcm`, `.jpg`, `.png`, and `.txt` files returns only the image paths.
   - **Implement:** A function that walks a directory recursively and filters by extension.

2. **Test:** `scan_directory` on an empty directory returns an empty list.

3. **Test:** `scan_directory` follows subdirectories (nested structure).

**Outcome:** A pure-logic module with no GUI dependency. All tests run headlessly.

### Phase 2: DICOM Sorting

**Module:** `pyradstack/sorting.py`
**Test file:** `tests/test_sorting.py`

1. **Test:** Given a list of file paths to DICOM files with known `InstanceNumber` tags, `sort_dicom_files` returns them in ascending instance order.
   - **Implement:** Read `InstanceNumber` (0020,0013) from each file via pydicom and sort.

2. **Test:** Fallback — if `InstanceNumber` is missing, sort by `ImagePositionPatient[2]` (Z-coordinate).

3. **Test:** Non-DICOM files are sorted alphanumerically by filename.

4. **Test:** Mixed list (DICOM + standard images) — DICOMs sorted by instance, standard images appended sorted by name.

**Fixtures needed:** Create minimal synthetic DICOM files in a `conftest.py` using `pydicom.Dataset` with only the required tags (no pixel data yet).

### Phase 3: Pixel Data & Windowing

**Module:** `pyradstack/windowing.py`
**Test file:** `tests/test_windowing.py`

1. **Test:** `apply_window` given a numpy array and (center=40, width=400) returns a uint8 array clamped/scaled correctly.
   - **Implement:** `lower = center - width/2`, `upper = center + width/2`, clip, rescale to 0-255.

2. **Test:** Values below the window floor map to 0; values above map to 255.

3. **Test:** `apply_window` with `RescaleSlope` and `RescaleIntercept` applies the linear transform before windowing.

4. **Test:** `extract_pixels` reads a DICOM file and returns a 2D numpy array of raw stored values.

**Fixtures needed:** Synthetic DICOM datasets with small pixel arrays (e.g., 4x4) and known WindowCenter/WindowWidth tags.

### Phase 4: Image Stack Model

**Module:** `pyradstack/stack.py`
**Test file:** `tests/test_stack.py`

1. **Test:** `ImageStack` initialised with a sorted list of paths reports correct `len()` and allows index access.

2. **Test:** `current_slice` starts at 0; `next_slice()` increments; `prev_slice()` decrements; both clamp at bounds.

3. **Test:** `get_image(index)` returns a uint8 numpy array (calls loader + windowing internally).

4. **Test:** Lazy loading — accessing slice N does not load slice N+1's pixel data. Verify with a mock/spy on the pixel reader.

**Outcome:** The `ImageStack` is the central data model the GUI will consume. All logic testable without a display.

### Phase 5: GUI — Viewer Widget

**Module:** `pyradstack/viewer.py`
**Test file:** `tests/test_viewer.py` (uses `pytest-qt`)

1. **Test:** `ViewerWidget` can be instantiated with a `QApplication` (qtbot fixture) without crashing.

2. **Test:** `set_stack(stack)` followed by rendering shows the first slice (assert the QLabel/QPixmap is not null).

3. **Test:** Simulated wheel-up event advances the slice index; wheel-down decrements. Verify via the stack's `current_slice`.

4. **Test:** Viewer displays correct image dimensions matching the source data.

### Phase 6: Main Window & File Dialog

**Module:** `pyradstack/main_window.py` + `main.py`
**Test file:** `tests/test_main_window.py`

1. **Test:** `MainWindow` opens without errors. Menu bar contains "File > Open Folder".

2. **Test:** Triggering Open Folder action (mocked `QFileDialog`) wires through to `scan_directory` → `sort` → `ImageStack` → `ViewerWidget.set_stack`.

3. **Test:** Status bar shows current slice number as "Slice X / N".

### Phase 7: Integration Test

**Test file:** `tests/test_integration.py`

1. **Test:** End-to-end — create a temp folder with 5 synthetic DICOM files, open it via the main window (mocked dialog), and verify the viewer displays all 5 slices by scrolling through them.

### Project File Structure

```
basic PACS/
├── main.py                  # Entry point: creates QApplication + MainWindow
├── pyradstack/
│   ├── __init__.py
│   ├── loader.py            # Directory scanning and file discovery
│   ├── sorting.py           # DICOM-aware sort logic
│   ├── windowing.py         # Window/Level + pixel extraction
│   ├── stack.py             # ImageStack data model
│   ├── viewer.py            # QWidget for displaying slices
│   └── main_window.py       # QMainWindow with menus, status bar
├── tests/
│   ├── conftest.py          # Shared fixtures (synthetic DICOMs, temp dirs)
│   ├── test_loader.py
│   ├── test_sorting.py
│   ├── test_windowing.py
│   ├── test_stack.py
│   ├── test_viewer.py
│   ├── test_main_window.py
│   └── test_integration.py
├── venv/
├── idea.md
├── CLAUDE.md
└── .gitignore
```

### TDD Workflow Summary

1. Pick the next untested behaviour from the current phase.
2. Write a failing test (`pytest tests/test_<module>.py -v` — expect RED).
3. Write the minimum implementation to make it pass (GREEN).
4. Refactor if needed while keeping tests green.
5. Run the full suite (`pytest`) to catch regressions before moving on.
6. Only advance to the next phase when all tests in the current phase pass.
