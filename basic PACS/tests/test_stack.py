from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest
from PIL import Image

from pyradstack.stack import ImageStack


@pytest.fixture
def dicom_stack(tmp_path):
    """Five DICOM files with pixel data and W/L tags, sorted by instance number."""
    from tests.conftest import _write_dcm_with_pixels

    paths = []
    for i in range(1, 6):
        pixels = np.full((4, 4), i * 10, dtype=np.int16)
        path = _write_dcm_with_pixels(
            tmp_path / f"slice_{i}.dcm",
            pixels,
            window_center=50,
            window_width=100,
            instance_number=i,
        )
        paths.append(path)
    return paths


class TestImageStackBasics:
    """Test basic container behavior."""

    def test_len_reports_number_of_slices(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        assert len(stack) == 5

    def test_index_access_returns_path(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        assert stack[0] == dicom_stack[0]
        assert stack[4] == dicom_stack[4]

    def test_index_out_of_range_raises(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        with pytest.raises(IndexError):
            stack[5]


class TestSliceNavigation:
    """Test current_slice tracking and navigation."""

    def test_current_slice_starts_at_zero(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        assert stack.current_slice == 0

    def test_next_slice_increments(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        stack.next_slice()
        assert stack.current_slice == 1

    def test_prev_slice_decrements(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        stack.next_slice()
        stack.next_slice()
        stack.prev_slice()
        assert stack.current_slice == 1

    def test_next_slice_clamps_at_upper_bound(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        for _ in range(20):
            stack.next_slice()
        assert stack.current_slice == 4

    def test_prev_slice_clamps_at_zero(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        stack.prev_slice()
        assert stack.current_slice == 0

    def test_set_slice_to_valid_index(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        stack.set_slice(3)
        assert stack.current_slice == 3

    def test_set_slice_clamps_out_of_range(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        stack.set_slice(999)
        assert stack.current_slice == 4
        stack.set_slice(-5)
        assert stack.current_slice == 0


class TestGetImage:
    """Test pixel retrieval with windowing."""

    def test_returns_uint8_array(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        img = stack.get_image(0)
        assert isinstance(img, np.ndarray)
        assert img.dtype == np.uint8

    def test_returns_2d_array(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        img = stack.get_image(0)
        assert img.ndim == 2

    def test_shape_matches_source(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        img = stack.get_image(0)
        assert img.shape == (4, 4)

    def test_different_slices_return_different_values(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        img0 = stack.get_image(0)
        img2 = stack.get_image(2)
        assert not np.array_equal(img0, img2)


@pytest.fixture
def png_stack(tmp_path):
    """Three PNG grayscale images with distinct pixel values."""
    paths = []
    for i, name in enumerate(["a.png", "b.png", "c.png"]):
        arr = np.full((32, 32), (i + 1) * 80, dtype=np.uint8)
        img = Image.fromarray(arr, mode="L")
        p = tmp_path / name
        img.save(p)
        paths.append(p)
    return paths


@pytest.fixture
def jpeg_stack(tmp_path):
    """Three JPEG grayscale images."""
    paths = []
    for i, name in enumerate(["x.jpg", "y.jpg", "z.jpg"]):
        arr = np.full((32, 32), (i + 1) * 60, dtype=np.uint8)
        img = Image.fromarray(arr, mode="L")
        p = tmp_path / name
        img.save(p)
        paths.append(p)
    return paths


class TestStandardImageStack:
    """Test get_image with PNG and JPEG files."""

    def test_png_returns_uint8_array(self, png_stack):
        stack = ImageStack(png_stack)
        img = stack.get_image(0)
        assert img.dtype == np.uint8
        assert img.ndim == 2

    def test_png_shape_matches(self, png_stack):
        stack = ImageStack(png_stack)
        img = stack.get_image(0)
        assert img.shape == (32, 32)

    def test_png_slices_are_distinct(self, png_stack):
        stack = ImageStack(png_stack)
        img0 = stack.get_image(0)
        img1 = stack.get_image(1)
        assert not np.array_equal(img0, img1)

    def test_jpeg_returns_uint8_array(self, jpeg_stack):
        stack = ImageStack(jpeg_stack)
        img = stack.get_image(0)
        assert img.dtype == np.uint8
        assert img.ndim == 2

    def test_jpeg_shape_matches(self, jpeg_stack):
        stack = ImageStack(jpeg_stack)
        img = stack.get_image(0)
        assert img.shape == (32, 32)

    def test_wl_override_changes_png_output(self, png_stack):
        stack = ImageStack(png_stack)
        img_default = stack.get_image(0).copy()
        # Narrow the window to a small range — should change the output
        stack.window_center = 40
        stack.window_width = 20
        img_windowed = stack.get_image(0)
        assert not np.array_equal(img_default, img_windowed)

    def test_rgb_png_converted_to_grayscale(self, tmp_path):
        arr = np.full((16, 16, 3), 128, dtype=np.uint8)
        img = Image.fromarray(arr, mode="RGB")
        p = tmp_path / "color.png"
        img.save(p)

        stack = ImageStack([p])
        result = stack.get_image(0)
        assert result.ndim == 2
        assert result.dtype == np.uint8


class TestWindowLevelOverride:
    """Test interactive W/L override on the stack."""

    def test_default_wl_is_none(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        assert stack.window_center is None
        assert stack.window_width is None

    def test_set_wl_override(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        stack.window_center = 200
        stack.window_width = 400
        assert stack.window_center == 200
        assert stack.window_width == 400

    def test_override_changes_output(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        img_default = stack.get_image(2).copy()
        stack.window_center = 10
        stack.window_width = 20
        img_override = stack.get_image(2)
        assert not np.array_equal(img_default, img_override)

    def test_clear_override_restores_tag_values(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        img_default = stack.get_image(0).copy()
        stack.window_center = 10
        stack.window_width = 20
        stack.window_center = None
        stack.window_width = None
        img_restored = stack.get_image(0)
        np.testing.assert_array_equal(img_default, img_restored)


class TestLazyLoading:
    """Verify pixels are only loaded on demand."""

    def test_construction_does_not_read_pixels(self, dicom_stack):
        with patch("pyradstack.stack.extract_pixels") as mock_extract:
            ImageStack(dicom_stack)
            mock_extract.assert_not_called()

    def test_get_image_reads_only_requested_slice(self, dicom_stack):
        stack = ImageStack(dicom_stack)
        with patch("pyradstack.stack.extract_pixels", return_value=np.zeros((4, 4), dtype=np.int16)) as mock_extract:
            with patch("pyradstack.stack.pydicom.dcmread") as mock_dcm:
                mock_ds = MagicMock()
                mock_ds.WindowCenter = 50
                mock_ds.WindowWidth = 100
                mock_ds.RescaleSlope = 1.0
                mock_ds.RescaleIntercept = 0.0
                mock_dcm.return_value = mock_ds
                stack.get_image(2)
                mock_extract.assert_called_once_with(dicom_stack[2])
