from pathlib import Path

from pyradstack.loader import scan_directory


class TestScanDirectory:
    """Tests for the scan_directory function."""

    def test_filters_image_files_only(self, flat_image_dir):
        results = scan_directory(flat_image_dir)
        extensions = {p.suffix.lower() for p in results}
        assert extensions <= {".dcm", ".jpg", ".png"}
        assert len(results) == 4

    def test_excludes_non_image_files(self, flat_image_dir):
        results = scan_directory(flat_image_dir)
        names = {p.name for p in results}
        assert "notes.txt" not in names
        assert "readme.md" not in names
        assert "data.csv" not in names

    def test_empty_directory_returns_empty_list(self, empty_dir):
        results = scan_directory(empty_dir)
        assert results == []

    def test_follows_subdirectories(self, nested_image_dir):
        results = scan_directory(nested_image_dir)
        names = {p.name for p in results}
        assert names == {"top.dcm", "mid.jpg", "deep.png"}

    def test_returns_list_of_paths(self, flat_image_dir):
        results = scan_directory(flat_image_dir)
        assert isinstance(results, list)
        for item in results:
            assert isinstance(item, Path)

    def test_returned_paths_are_absolute(self, flat_image_dir):
        results = scan_directory(flat_image_dir)
        for item in results:
            assert item.is_absolute()
