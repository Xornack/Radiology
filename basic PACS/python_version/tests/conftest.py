import os
import tempfile

import numpy as np
import pytest
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


def _write_synthetic_dcm(path, instance_number=None, image_position=None):
    """Write a minimal valid DICOM file with optional sorting tags."""
    file_meta = pydicom.Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.Modality = "CT"

    if instance_number is not None:
        ds.InstanceNumber = instance_number
    if image_position is not None:
        ds.ImagePositionPatient = image_position

    ds.save_as(str(path))
    return path


def _write_dcm_with_pixels(
    path,
    pixel_array,
    window_center=None,
    window_width=None,
    rescale_slope=None,
    rescale_intercept=None,
    instance_number=None,
):
    """Write a DICOM file with actual pixel data and optional W/L and rescale tags."""
    file_meta = pydicom.Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.Modality = "CT"

    ds.Rows, ds.Columns = pixel_array.shape
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 1  # signed
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = pixel_array.astype(np.int16).tobytes()

    if window_center is not None:
        ds.WindowCenter = window_center
    if window_width is not None:
        ds.WindowWidth = window_width
    if rescale_slope is not None:
        ds.RescaleSlope = rescale_slope
    if rescale_intercept is not None:
        ds.RescaleIntercept = rescale_intercept
    if instance_number is not None:
        ds.InstanceNumber = instance_number

    ds.save_as(str(path))
    return path


@pytest.fixture
def empty_dir(tmp_path):
    """An empty temporary directory."""
    return tmp_path


@pytest.fixture
def flat_image_dir(tmp_path):
    """A flat directory with mixed image and non-image files."""
    for name in ["slice1.dcm", "slice2.dcm", "photo.jpg", "scan.png"]:
        (tmp_path / name).write_bytes(b"\x00")
    for name in ["notes.txt", "readme.md", "data.csv"]:
        (tmp_path / name).write_bytes(b"\x00")
    return tmp_path


@pytest.fixture
def nested_image_dir(tmp_path):
    """A directory with images nested in subdirectories."""
    sub1 = tmp_path / "series1"
    sub2 = tmp_path / "series1" / "subseries"
    sub1.mkdir()
    sub2.mkdir()

    (tmp_path / "top.dcm").write_bytes(b"\x00")
    (sub1 / "mid.jpg").write_bytes(b"\x00")
    (sub2 / "deep.png").write_bytes(b"\x00")
    (sub2 / "ignore.txt").write_bytes(b"\x00")
    return tmp_path


@pytest.fixture
def dicom_files_with_instance_numbers(tmp_path):
    """Three DICOM files with InstanceNumbers in non-alphabetical order."""
    paths = []
    for filename, inst_num in [("c.dcm", 3), ("a.dcm", 1), ("b.dcm", 2)]:
        paths.append(_write_synthetic_dcm(tmp_path / filename, instance_number=inst_num))
    return paths


@pytest.fixture
def dicom_files_with_position(tmp_path):
    """DICOM files with no InstanceNumber, only ImagePositionPatient."""
    paths = []
    for filename, z in [("z100.dcm", 100.0), ("z50.dcm", 50.0), ("z75.dcm", 75.0)]:
        paths.append(
            _write_synthetic_dcm(tmp_path / filename, image_position=[0.0, 0.0, z])
        )
    return paths


@pytest.fixture
def mixed_image_files(tmp_path):
    """DICOM files mixed with standard image files."""
    paths = []
    for filename, inst_num in [("slice_b.dcm", 2), ("slice_a.dcm", 1)]:
        paths.append(_write_synthetic_dcm(tmp_path / filename, instance_number=inst_num))
    for name in ["gamma.png", "alpha.jpg", "beta.png"]:
        p = tmp_path / name
        p.write_bytes(b"\x00")
        paths.append(p)
    return paths
