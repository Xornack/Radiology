from pathlib import Path

import numpy as np
import pydicom
from PIL import Image

from pyradstack.windowing import apply_window, extract_pixels

DICOM_EXTENSIONS = {".dcm"}


class ImageStack:
    """Data model representing a scrollable stack of image slices.

    Provides lazy loading — pixel data is only read when get_image() is called.
    """

    def __init__(self, paths: list[Path]):
        self._paths = list(paths)
        self._current = 0
        self.window_center: float | None = None
        self.window_width: float | None = None

    def __len__(self) -> int:
        return len(self._paths)

    def __getitem__(self, index: int) -> Path:
        if index < 0 or index >= len(self._paths):
            raise IndexError(f"Slice index {index} out of range [0, {len(self._paths) - 1}]")
        return self._paths[index]

    @property
    def current_slice(self) -> int:
        return self._current

    def next_slice(self) -> int:
        self._current = min(self._current + 1, len(self._paths) - 1)
        return self._current

    def prev_slice(self) -> int:
        self._current = max(self._current - 1, 0)
        return self._current

    def set_slice(self, index: int) -> int:
        self._current = max(0, min(index, len(self._paths) - 1))
        return self._current

    def get_image(self, index: int) -> np.ndarray:
        """Load and window pixel data for a single slice. Returns uint8 2D array."""
        path = self[index]

        if path.suffix.lower() in DICOM_EXTENSIONS:
            return self._load_dicom(path)
        return self._load_standard(path)

    def _load_dicom(self, path: Path) -> np.ndarray:
        pixels = extract_pixels(path)

        ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
        center = self.window_center if self.window_center is not None else float(getattr(ds, "WindowCenter", 128))
        width = self.window_width if self.window_width is not None else float(getattr(ds, "WindowWidth", 256))
        slope = float(getattr(ds, "RescaleSlope", 1.0))
        intercept = float(getattr(ds, "RescaleIntercept", 0.0))

        return apply_window(pixels.astype(np.float64), center, width, slope, intercept)

    def _load_standard(self, path: Path) -> np.ndarray:
        img = Image.open(path).convert("L")
        pixels = np.array(img, dtype=np.uint8)

        if self.window_center is not None and self.window_width is not None:
            return apply_window(pixels.astype(np.float64), self.window_center, self.window_width)

        return pixels
