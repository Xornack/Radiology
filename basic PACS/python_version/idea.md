# Project: PyRadStack (Python Radiology Stack Viewer)

## 1. Core Concept
A lightweight, open-source image viewer designed to mimic the functionality of a radiology PACS workstation. The application loads folders of images (DICOM, PNG, JPG) and treats them as a volumetric stack, allowing the user to scroll through slices using the mouse wheel (cine mode).

**Primary Goal:** Prove that Python can handle the performance requirements of scrolling through high-resolution medical imaging stacks without the overhead of raw OpenGL implementation.

## 2. Target Users
* Radiologists and medical professionals needing a quick, portable viewer.
* Data Scientists/Developers verifying DICOM datasets for ML pipelines.
* Researchers needing to visualize folder-based image sequences.

## 3. Technology Stack
* **Language:** Python 3.10+
* **GUI Framework:** `PyQt6` (Preferred over PySide6 for this PoC due to licensing/community support, superior to Tkinter/PyGame for event handling).
* **DICOM Handling:** `pydicom` (Metadata parsing, pixel extraction).
* **Image Processing:** * `numpy` (High-performance array manipulation, Window/Leveling).
    * `Pillow (PIL)` (Fallback for non-DICOM formats).
* **Visualization (Future):** `pyqtgraph` (For hardware-accelerated rendering and histograms).

## 4. Key Features (MVP)
- **Universal Loader:** Recursively scans a selected directory for valid image files (`.dcm`, `.jpg`, `.png`).
- **Smart Sorting:** - *DICOM:* Sorts by `(0020,0013) Instance Number` to ensure correct Z-axis alignment.
    - *Standard:* Sorts alphanumeric by filename.
- **Radiology Scrolling:** Mouse wheel scrolling mimics standard PACS behavior (Up/Down traverses the Z-stack).
- **Basic Windowing:** Applies DICOM `WindowCenter` and `WindowWidth` tags to raw pixel data for correct Hounsfield Unit (HU) display.

## 5. Technical Challenges & Solutions
| Challenge | Solution |
| :--- | :--- |
| **Sorting Accuracy** | Filenames in DICOM folders are often randomized (e.g., `IM-0001-0002.dcm`). We must parse headers and sort by `InstanceNumber` or `ImagePositionPatient`. |
| **Performance** | Loading thousands of DICOMs can be slow. *Solution:* Lazy loading (load metadata first, pixels on demand) or async worker threads for loading. |
| **Window/Leveling** | Raw DICOM data is 12-16 bit. We use Numpy to clip and normalize ranges based on window width/center before converting to 8-bit QImages. |

## 6. Roadmap / Future Scope
- **MPR (Multi-Planar Reconstruction):** Implement VTK to generate Coronal/Sagittal views from Axial data.
- **Interactive Windowing:** Hold Right-Click + Drag to adjust contrast/brightness (W/L) dynamically.
- **Overlay Data:** Display Patient Name, MRN, Date, and current Slice Location on the viewport.
- **Anonymization:** "Export" feature to save the current stack as anonymous PNGs or raw arrays.
