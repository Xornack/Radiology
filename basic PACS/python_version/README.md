# PyRadStack

A lightweight radiology image viewer that mimics PACS workstation functionality. Load a folder of DICOM, PNG, or JPEG images and scroll through them as a volumetric stack.

## Features

- **Universal Loader** — recursively scans a directory for `.dcm`, `.jpg`, `.jpeg`, `.png` files
- **Smart DICOM Sorting** — sorts by `InstanceNumber` tag, falls back to `ImagePositionPatient` Z-coordinate
- **Window/Level** — applies DICOM `WindowCenter`/`WindowWidth` tags with `RescaleSlope`/`RescaleIntercept` for correct HU display
- **Mouse Controls:**
  - **Scroll wheel** — navigate slices
  - **Left-click drag up/down** — navigate slices
  - **Left + Right click drag left/right** — adjust window width (contrast)
  - **Left + Right click drag up/down** — adjust window level (brightness)

## Requirements

- Python 3.10+
- PyQt6
- pydicom
- numpy
- Pillow

## Setup

```bash
python -m venv venv
source venv/Scripts/activate   # Git Bash on Windows
pip install PyQt6 pydicom numpy Pillow
```

## Usage

```bash
python main.py
```

Then use **File > Open Folder** to select a directory containing images.

## Running Tests

```bash
pip install pytest pytest-qt
pytest
```

## Project Structure

```
pyradstack/
├── loader.py        # Directory scanning and file discovery
├── sorting.py       # DICOM-aware sort logic
├── windowing.py     # Window/Level and pixel extraction
├── stack.py         # ImageStack data model with lazy loading
├── viewer.py        # QWidget for slice display and mouse interaction
└── main_window.py   # QMainWindow with menus and status bar
```

## License

Open source. See LICENSE file for details.
