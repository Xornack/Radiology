from pyradstack.sorting import sort_files


class TestSortDicomByInstanceNumber:
    """DICOM files should sort by InstanceNumber tag."""

    def test_sorts_by_instance_number(self, dicom_files_with_instance_numbers):
        result = sort_files(dicom_files_with_instance_numbers)
        names = [p.name for p in result]
        assert names == ["a.dcm", "b.dcm", "c.dcm"]

    def test_preserves_all_files(self, dicom_files_with_instance_numbers):
        result = sort_files(dicom_files_with_instance_numbers)
        assert len(result) == 3


class TestSortDicomByPosition:
    """Fallback: sort by ImagePositionPatient Z when InstanceNumber is missing."""

    def test_sorts_by_z_coordinate(self, dicom_files_with_position):
        result = sort_files(dicom_files_with_position)
        names = [p.name for p in result]
        assert names == ["z50.dcm", "z75.dcm", "z100.dcm"]


class TestSortStandardImages:
    """Non-DICOM images should sort alphanumerically by filename."""

    def test_sorts_by_filename(self, tmp_path):
        paths = []
        for name in ["charlie.png", "alpha.jpg", "bravo.png"]:
            p = tmp_path / name
            p.write_bytes(b"\x00")
            paths.append(p)

        result = sort_files(paths)
        names = [p.name for p in result]
        assert names == ["alpha.jpg", "bravo.png", "charlie.png"]


class TestSortMixedFiles:
    """Mixed DICOM + standard: DICOMs first sorted by instance, then standard by name."""

    def test_dicoms_first_then_standard(self, mixed_image_files):
        result = sort_files(mixed_image_files)
        names = [p.name for p in result]
        assert names == ["slice_a.dcm", "slice_b.dcm", "alpha.jpg", "beta.png", "gamma.png"]

    def test_preserves_all_files(self, mixed_image_files):
        result = sort_files(mixed_image_files)
        assert len(result) == 5
