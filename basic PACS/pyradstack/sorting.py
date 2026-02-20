from pathlib import Path

import pydicom


DICOM_EXTENSIONS = {".dcm"}


def _is_dicom(path: Path) -> bool:
    return path.suffix.lower() in DICOM_EXTENSIONS


def _dicom_sort_key(path: Path) -> float:
    """Extract a numeric sort key from a DICOM file.

    Priority: InstanceNumber > ImagePositionPatient[2] > filename fallback.
    """
    try:
        ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
    except Exception:
        return float("inf")

    if hasattr(ds, "InstanceNumber") and ds.InstanceNumber is not None:
        return float(ds.InstanceNumber)

    if hasattr(ds, "ImagePositionPatient") and ds.ImagePositionPatient is not None:
        return float(ds.ImagePositionPatient[2])

    return float("inf")


def sort_files(paths: list[Path]) -> list[Path]:
    """Sort a list of image paths: DICOMs by tag order, then standard images by name."""
    dicoms = [p for p in paths if _is_dicom(p)]
    standard = [p for p in paths if not _is_dicom(p)]

    dicoms.sort(key=_dicom_sort_key)
    standard.sort(key=lambda p: p.name.lower())

    return dicoms + standard
