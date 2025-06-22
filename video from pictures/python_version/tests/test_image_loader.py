"""
Test for image file loading and validation functionality.
Tests image file discovery, format validation, and DICOM processing.
"""

import sys
import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

class TestImageLoader(unittest.TestCase):
    """Test image loading and validation functionality."""
    
    def setUp(self):
        """Set up test environment with temporary directories and files."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create test files
        (self.test_path / "image1.jpg").touch()
        (self.test_path / "image2.png").touch()
        (self.test_path / "image3.dcm").touch()
        (self.test_path / "image4.JPEG").touch()  # Test case sensitivity
        (self.test_path / "image5.dicom").touch()
        (self.test_path / "not_image.txt").touch()  # Should be ignored
        (self.test_path / "another.doc").touch()    # Should be ignored
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.test_dir)
        
    def test_image_loader_imports(self):
        """Test that image loader module can be imported."""
        try:
            from image_loader import ImageLoader
            self.assertTrue(True, "ImageLoader should be importable")
        except ImportError as e:
            self.fail(f"ImageLoader import failed: {e}")
            
    def test_image_loader_instantiation(self):
        """Test that ImageLoader can be instantiated."""
        from image_loader import ImageLoader
        
        loader = ImageLoader()
        self.assertIsNotNone(loader)
        
    def test_supported_formats_detection(self):
        """Test detection of supported image formats."""
        from image_loader import ImageLoader
        
        loader = ImageLoader()
        supported_files = loader.find_supported_images(self.test_path)
        
        # Should find 5 supported files (jpg, png, dcm, JPEG, dicom)
        self.assertEqual(len(supported_files), 5)
        
        # Check that unsupported files are excluded
        file_names = [f.name for f in supported_files]
        self.assertNotIn("not_image.txt", file_names)
        self.assertNotIn("another.doc", file_names)
        
    def test_file_validation(self):
        """Test individual file validation."""
        from image_loader import ImageLoader
        
        loader = ImageLoader()
        
        # Test valid extensions
        self.assertTrue(loader.is_supported_format(self.test_path / "test.jpg"))
        self.assertTrue(loader.is_supported_format(self.test_path / "test.jpeg"))
        self.assertTrue(loader.is_supported_format(self.test_path / "test.png"))
        self.assertTrue(loader.is_supported_format(self.test_path / "test.dcm"))
        self.assertTrue(loader.is_supported_format(self.test_path / "test.dicom"))
        
        # Test case insensitive
        self.assertTrue(loader.is_supported_format(self.test_path / "test.JPG"))
        self.assertTrue(loader.is_supported_format(self.test_path / "test.PNG"))
        
        # Test invalid extensions
        self.assertFalse(loader.is_supported_format(self.test_path / "test.txt"))
        self.assertFalse(loader.is_supported_format(self.test_path / "test.doc"))
        
    def test_corrupted_file_handling(self):
        """Test handling of corrupted or unreadable files."""
        from image_loader import ImageLoader
        
        loader = ImageLoader()
        
        # Create a corrupted file (empty file with image extension)
        corrupted_file = self.test_path / "corrupted.jpg"
        corrupted_file.write_text("not an image")
        
        valid_files, errors = loader.validate_files([corrupted_file])
        
        # Should return empty valid files and one error
        self.assertEqual(len(valid_files), 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("corrupted.jpg", str(errors[0]))
        
    def test_dicom_processing(self):
        """Test DICOM file processing and header stripping."""
        from image_loader import ImageLoader
        
        loader = ImageLoader()
        
        # Mock DICOM file processing
        with patch('image_loader.pydicom') as mock_pydicom:
            mock_dataset = MagicMock()
            mock_dataset.pixel_array = "mock_image_data"
            mock_pydicom.dcmread.return_value = mock_dataset
            
            dicom_file = self.test_path / "test.dcm"
            image_data = loader.extract_dicom_image(dicom_file)
            
            # Should call pydicom.dcmread
            mock_pydicom.dcmread.assert_called_once_with(dicom_file)
            
            # Should return pixel array
            self.assertEqual(image_data, "mock_image_data")
            
    def test_natural_sorting(self):
        """Test natural/numerical sorting of filenames."""
        from image_loader import ImageLoader
        
        loader = ImageLoader()
        
        # Create files with numerical names
        files = [
            self.test_path / "image1.jpg",
            self.test_path / "image10.jpg", 
            self.test_path / "image2.jpg",
            self.test_path / "image20.jpg"
        ]
        
        sorted_files = loader.sort_files_natural(files)
        expected_order = ["image1.jpg", "image2.jpg", "image10.jpg", "image20.jpg"]
        
        sorted_names = [f.name for f in sorted_files]
        self.assertEqual(sorted_names, expected_order)
        
    def test_modification_date_sorting(self):
        """Test sorting by file modification date."""
        from image_loader import ImageLoader
        
        loader = ImageLoader()
        
        files = [
            self.test_path / "file1.jpg",
            self.test_path / "file2.jpg",
            self.test_path / "file3.jpg"
        ]
        
        # Create files and modify timestamps
        for i, file in enumerate(files):
            file.touch()
            # Modify access time to simulate different modification times
            stat = file.stat()
            os.utime(file, (stat.st_atime, stat.st_mtime + i))
            
        sorted_files = loader.sort_files_by_date(files)
        
        # Should be sorted by modification time (oldest first)
        self.assertEqual(len(sorted_files), 3)
        self.assertEqual(sorted_files[0].name, "file1.jpg")
        self.assertEqual(sorted_files[-1].name, "file3.jpg")
        
    def test_empty_directory_handling(self):
        """Test handling of directories with no supported images."""
        from image_loader import ImageLoader
        
        loader = ImageLoader()
        
        # Create empty directory
        empty_dir = self.test_path / "empty"
        empty_dir.mkdir()
        
        supported_files = loader.find_supported_images(empty_dir)
        self.assertEqual(len(supported_files), 0)
        
    def test_load_and_validate_workflow(self):
        """Test complete load and validate workflow."""
        from image_loader import ImageLoader
        
        loader = ImageLoader()
        
        # Test complete workflow
        result = loader.load_and_validate_images(
            self.test_path,
            sort_method="natural"
        )
        
        self.assertIn('valid_files', result)
        self.assertIn('errors', result)
        self.assertIn('total_found', result)
        self.assertIn('total_valid', result)
        
        # Should find our test files
        self.assertEqual(result['total_found'], 5)  # 5 supported image files
        

if __name__ == '__main__':
    unittest.main()
