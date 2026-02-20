import numpy as np
import pytest

from pyradstack.windowing import apply_window, extract_pixels


class TestApplyWindow:
    """Tests for the Window/Level transform."""

    def test_basic_window_center_and_width(self):
        # center=100, width=200 → range [0, 200]
        # Values: 0 → 0, 100 → 127, 200 → 255
        arr = np.array([[0, 100], [200, 50]], dtype=np.float64)
        result = apply_window(arr, center=100, width=200)

        assert result.dtype == np.uint8
        assert result[0, 0] == 0        # at lower bound
        assert result[0, 1] == 128      # at center (127.5 rounds to 128)
        assert result[1, 0] == 255      # at upper bound

    def test_values_below_window_clamp_to_zero(self):
        arr = np.array([[-500, -1000]], dtype=np.float64)
        result = apply_window(arr, center=40, width=400)
        assert np.all(result == 0)

    def test_values_above_window_clamp_to_255(self):
        arr = np.array([[5000, 9999]], dtype=np.float64)
        result = apply_window(arr, center=40, width=400)
        assert np.all(result == 255)

    def test_output_shape_matches_input(self):
        arr = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float64)
        result = apply_window(arr, center=3, width=6)
        assert result.shape == (2, 3)

    def test_with_rescale_slope_and_intercept(self):
        # Stored value 1000, slope=1, intercept=-1024
        # HU = 1000 * 1 + (-1024) = -24
        # center=40, width=400 → range [-160, 240]
        # -24 maps to (-24 - -160) / (240 - -160) * 255 = 136/400 * 255 ≈ 86
        arr = np.array([[1000]], dtype=np.float64)
        result = apply_window(arr, center=40, width=400, slope=1.0, intercept=-1024.0)
        assert result.dtype == np.uint8
        expected = int(round((-24 - (-160)) / (240 - (-160)) * 255))
        assert abs(int(result[0, 0]) - expected) <= 1

    def test_rescale_defaults_to_identity(self):
        # With no slope/intercept, raw values should be used directly
        arr = np.array([[100]], dtype=np.float64)
        result_no_rescale = apply_window(arr, center=100, width=200)
        result_identity = apply_window(arr, center=100, width=200, slope=1.0, intercept=0.0)
        assert result_no_rescale[0, 0] == result_identity[0, 0]


class TestExtractPixels:
    """Tests for reading pixel data from a DICOM file."""

    def test_returns_2d_numpy_array(self, tmp_path):
        from tests.conftest import _write_dcm_with_pixels

        pixels = np.array([[10, 20], [30, 40]], dtype=np.int16)
        path = _write_dcm_with_pixels(tmp_path / "test.dcm", pixels)

        result = extract_pixels(path)
        assert isinstance(result, np.ndarray)
        assert result.ndim == 2

    def test_pixel_values_match_source(self, tmp_path):
        from tests.conftest import _write_dcm_with_pixels

        pixels = np.array([[10, 20], [30, 40]], dtype=np.int16)
        path = _write_dcm_with_pixels(tmp_path / "test.dcm", pixels)

        result = extract_pixels(path)
        np.testing.assert_array_equal(result, pixels)

    def test_shape_matches_rows_columns(self, tmp_path):
        from tests.conftest import _write_dcm_with_pixels

        pixels = np.array([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]], dtype=np.int16)
        path = _write_dcm_with_pixels(tmp_path / "test.dcm", pixels)

        result = extract_pixels(path)
        assert result.shape == (3, 4)
