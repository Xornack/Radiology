"""
Image loading and validation module for Video from Pictures application.
Handles loading, validation, and processing of JPEG, PNG, and DICOM images.
"""

import re
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any, Union

try:
    import pydicom
    DICOM_AVAILABLE = True
except ImportError:
    DICOM_AVAILABLE = False
    pydicom = None

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None


class ImageLoader:
    """
    Handles loading and validation of medical image files.
    Supports JPEG, PNG, and DICOM formats with robust error handling.
    """
    
    # Supported file extensions (case-insensitive)
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.dcm', '.dicom'
    }
    
    def __init__(self):
        """Initialize the ImageLoader."""
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
    def _setup_logging(self):
        """Set up logging configuration."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def is_supported_format(self, file_path: Path) -> bool:
        """
        Check if a file has a supported image format extension.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if the file extension is supported, False otherwise
        """
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
            
        extension = file_path.suffix.lower()
        return extension in self.SUPPORTED_EXTENSIONS
    
    def find_supported_images(self, directory: Path) -> List[Path]:
        """
        Find all supported image files in a directory.
        
        Args:
            directory: Directory path to search
            
        Returns:
            List of Path objects for supported image files
        """
        if not isinstance(directory, Path):
            directory = Path(directory)
            
        if not directory.exists() or not directory.is_dir():
            self.logger.warning(f"Directory does not exist or is not a directory: {directory}")
            return []
            
        supported_files = []
        
        try:
            for file_path in directory.iterdir():
                if file_path.is_file() and self.is_supported_format(file_path):
                    supported_files.append(file_path)
                    
        except (PermissionError, OSError) as e:
            self.logger.error(f"Error accessing directory {directory}: {e}")
            return []
            
        self.logger.info(f"Found {len(supported_files)} supported image files in {directory}")
        return supported_files
    
    def validate_files(self, file_paths: List[Path]) -> Tuple[List[Path], List[str]]:
        """
        Validate a list of image files for readability and basic integrity.
        
        Args:
            file_paths: List of file paths to validate
            
        Returns:
            Tuple of (valid_files, error_messages)
        """
        valid_files = []
        errors = []
        
        for file_path in file_paths:
            try:
                if not file_path.exists():
                    errors.append(f"File does not exist: {file_path}")
                    continue
                    
                if file_path.stat().st_size == 0:
                    errors.append(f"File is empty: {file_path}")
                    continue
                
                # Basic validation based on file type
                if self._validate_file_content(file_path):
                    valid_files.append(file_path)
                else:
                    errors.append(f"File appears to be corrupted or invalid: {file_path}")
                    
            except (PermissionError, OSError) as e:
                errors.append(f"Cannot access file {file_path}: {e}")
                
        self.logger.info(f"Validated {len(valid_files)} files, {len(errors)} errors")
        return valid_files, errors
    
    def _validate_file_content(self, file_path: Path) -> bool:
        """
        Perform basic content validation for different file types.
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            True if file appears valid, False otherwise
        """
        extension = file_path.suffix.lower()
        
        try:
            if extension in {'.dcm', '.dicom'}:
                return self._validate_dicom_file(file_path)
            elif extension in {'.jpg', '.jpeg', '.png'}:
                return self._validate_image_file(file_path)
            else:
                return False
                
        except Exception as e:
            self.logger.debug(f"Validation error for {file_path}: {e}")
            return False
    
    def _validate_dicom_file(self, file_path: Path) -> bool:
        """Validate DICOM file by attempting to read it."""
        if not DICOM_AVAILABLE:
            self.logger.warning("pydicom not available, cannot validate DICOM files")
            return True  # Assume valid if we can't check
            
        try:
            dataset = pydicom.dcmread(file_path, stop_before_pixels=True)
            return hasattr(dataset, 'pixel_array') or hasattr(dataset, 'PixelData')
        except Exception:
            return False
    
    def _validate_image_file(self, file_path: Path) -> bool:
        """Validate regular image file by attempting to open it."""
        if not PIL_AVAILABLE:
            # If PIL is not available, do basic file signature check
            return self._check_file_signature(file_path)
            
        try:
            with Image.open(file_path) as img:
                img.verify()  # Verify it's a valid image
            return True
        except Exception:
            return False
    
    def _check_file_signature(self, file_path: Path) -> bool:
        """Check file signature/magic bytes for basic validation."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
                
            extension = file_path.suffix.lower()
            
            if extension in {'.jpg', '.jpeg'}:
                return header.startswith(b'\xff\xd8\xff')
            elif extension == '.png':
                return header.startswith(b'\x89PNG\r\n\x1a\n')
            else:
                return True  # Default to valid for unknown types
                
        except Exception:
            return False
    
    def extract_dicom_image(self, file_path: Path) -> Any:
        """
        Extract image data from DICOM file, stripping header information.
        
        Args:
            file_path: Path to DICOM file
            
        Returns:
            Image pixel array or None if extraction fails
        """
        if not DICOM_AVAILABLE:
            raise ImportError("pydicom is required for DICOM processing")
            
        try:
            dataset = pydicom.dcmread(file_path)
            return dataset.pixel_array
        except Exception as e:
            self.logger.error(f"Failed to extract DICOM image from {file_path}: {e}")
            return None
    
    def sort_files_natural(self, file_paths: List[Path]) -> List[Path]:
        """
        Sort files using natural/numerical ordering.
        
        Args:
            file_paths: List of file paths to sort
            
        Returns:
            Sorted list of file paths
        """
        def natural_key(path: Path) -> List[Union[int, str]]:
            """Convert filename to list of strings and numbers for natural sorting."""
            parts = re.split(r'(\d+)', path.name.lower())
            return [int(part) if part.isdigit() else part for part in parts]
        
        return sorted(file_paths, key=natural_key)
    
    def sort_files_by_date(self, file_paths: List[Path]) -> List[Path]:
        """
        Sort files by modification date (oldest first).
        
        Args:
            file_paths: List of file paths to sort
            
        Returns:
            Sorted list of file paths
        """
        try:
            return sorted(file_paths, key=lambda p: p.stat().st_mtime)
        except (OSError, AttributeError) as e:
            self.logger.warning(f"Error sorting by date, falling back to name sorting: {e}")
            return sorted(file_paths, key=lambda p: p.name)
    
    def load_and_validate_images(self, 
                                directory: Path, 
                                sort_method: str = "natural") -> Dict[str, Any]:
        """
        Complete workflow to load and validate images from a directory.
        
        Args:
            directory: Directory containing images
            sort_method: Sorting method ("natural", "alphabetical", or "date")
            
        Returns:
            Dictionary containing results and statistics
        """
        if not isinstance(directory, Path):
            directory = Path(directory)
            
        # Find supported image files
        found_files = self.find_supported_images(directory)
        
        # Validate files
        valid_files, errors = self.validate_files(found_files)
        
        # Sort files according to specified method
        if sort_method == "natural":
            sorted_files = self.sort_files_natural(valid_files)
        elif sort_method == "alphabetical":
            sorted_files = sorted(valid_files, key=lambda p: p.name.lower())
        elif sort_method == "date":
            sorted_files = self.sort_files_by_date(valid_files)
        else:
            self.logger.warning(f"Unknown sort method '{sort_method}', using natural")
            sorted_files = self.sort_files_natural(valid_files)
        
        result = {
            'valid_files': sorted_files,
            'errors': errors,
            'total_found': len(found_files),
            'total_valid': len(valid_files),
            'sort_method': sort_method,
            'directory': directory
        }
        
        self.logger.info(
            f"Loaded {result['total_valid']}/{result['total_found']} "
            f"images from {directory} (sorted by {sort_method})"
        )
        
        return result
