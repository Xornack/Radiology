from pathlib import Path

import numpy as np
import pydicom


def apply_window(
    arr: np.ndarray,
    center: float,
    width: float,
    slope: float = 1.0,
    intercept: float = 0.0,
) -> np.ndarray:
    """Apply rescale transform and Window/Level to produce a uint8 image.

    1. Convert stored values to HU: hu = arr * slope + intercept
    2. Clamp to [center - width/2, center + width/2]
    3. Rescale to 0-255.
    """
    hu = arr * slope + intercept
    lower = center - width / 2
    upper = center + width / 2
    clamped = np.clip(hu, lower, upper)
    scaled = (clamped - lower) / (upper - lower) * 255.0
    return np.round(scaled).astype(np.uint8)


def extract_pixels(path: Path) -> np.ndarray:
    """Read a DICOM file and return its pixel data as a 2D numpy array."""
    ds = pydicom.dcmread(str(path), force=True)
    return ds.pixel_array
