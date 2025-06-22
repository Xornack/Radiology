"""
Test for error handling and logging functionality.
Tests comprehensive error handling, logging to files, and error reporting.
"""

import sys
import unittest
import tempfile
import logging
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

class TestErrorHandlingAndLogging(unittest.TestCase):
    """Test comprehensive error handling and logging functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.test_dir)
        
    def test_error_logger_imports(self):
        """Test that error logger module can be imported."""
        try:
            from error_logger import ErrorLogger
            self.assertTrue(True, "ErrorLogger should be importable")
        except ImportError as e:
            self.fail(f"ErrorLogger import failed: {e}")
            
    def test_error_logger_instantiation(self):
        """Test that ErrorLogger can be instantiated."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        self.assertIsNotNone(logger)
        
    def test_error_logger_with_log_file(self):
        """Test ErrorLogger with custom log file."""
        from error_logger import ErrorLogger
        
        log_file = self.test_path / "test_errors.log"
        logger = ErrorLogger(log_file=log_file)
        
        self.assertEqual(logger.log_file, log_file)
        
    def test_file_operation_error_handling(self):
        """Test error handling for file operations."""
        from error_logger import ErrorLogger
        
        log_file = self.test_path / "file_errors.log"
        logger = ErrorLogger(log_file=log_file)
        
        # Test handling of non-existent file
        error_info = logger.handle_file_error("file_not_found.jpg", FileNotFoundError("File not found"))
        
        self.assertIsInstance(error_info, dict)
        self.assertIn('error_type', error_info)
        self.assertIn('message', error_info)
        self.assertIn('file_path', error_info)
        self.assertIn('timestamp', error_info)
        
        # Verify error was logged
        self.assertTrue(log_file.exists())
        
    def test_video_encoding_error_handling(self):
        """Test error handling for video encoding operations."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Test video encoding error
        encoding_error = RuntimeError("Failed to encode video: codec not found")
        error_info = logger.handle_video_error("output.mp4", encoding_error)
        
        self.assertEqual(error_info['error_type'], 'VideoEncodingError')
        self.assertIn('codec not found', error_info['message'])
        
    def test_image_processing_error_handling(self):
        """Test error handling for image processing operations."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Test corrupted image error
        image_error = OSError("cannot identify image file")
        error_info = logger.handle_image_error("corrupted.jpg", image_error)
        
        self.assertEqual(error_info['error_type'], 'ImageProcessingError')
        self.assertIn('corrupted.jpg', error_info['file_path'])
        
    def test_dicom_processing_error_handling(self):
        """Test error handling for DICOM processing operations."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Test DICOM parsing error
        dicom_error = Exception("Invalid DICOM file structure")
        error_info = logger.handle_dicom_error("invalid.dcm", dicom_error)
        
        self.assertEqual(error_info['error_type'], 'DicomProcessingError')
        self.assertIn('Invalid DICOM', error_info['message'])
        
    def test_permission_error_handling(self):
        """Test error handling for permission-related operations."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Test permission denied error
        perm_error = PermissionError("Access denied to output directory")
        error_info = logger.handle_permission_error("/protected/output.mp4", perm_error)
        
        self.assertEqual(error_info['error_type'], 'PermissionError')
        self.assertIn('Access denied', error_info['message'])
        
    def test_disk_space_error_handling(self):
        """Test error handling for disk space issues."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Test disk space error
        space_error = OSError("No space left on device")
        error_info = logger.handle_disk_error("/full/disk/output.mp4", space_error)
        
        self.assertEqual(error_info['error_type'], 'DiskSpaceError')
        self.assertIn('space left', error_info['message'])
        
    def test_error_aggregation(self):
        """Test aggregation of multiple errors."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Add multiple errors
        logger.handle_file_error("file1.jpg", FileNotFoundError("File 1 not found"))
        logger.handle_image_error("file2.jpg", OSError("Corrupted image"))
        logger.handle_video_error("output.mp4", RuntimeError("Encoding failed"))
        
        # Get error summary
        summary = logger.get_error_summary()
        
        self.assertEqual(summary['total_errors'], 3)
        self.assertIn('FileNotFoundError', summary['error_types'])
        self.assertIn('ImageProcessingError', summary['error_types'])
        self.assertIn('VideoEncodingError', summary['error_types'])
        
    def test_error_filtering_by_type(self):
        """Test filtering errors by type."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Add errors of different types
        logger.handle_file_error("file1.jpg", FileNotFoundError("File not found"))
        logger.handle_file_error("file2.jpg", FileNotFoundError("Another file not found"))
        logger.handle_image_error("file3.jpg", OSError("Corrupted"))
        
        # Filter by type
        file_errors = logger.get_errors_by_type('FileNotFoundError')
        
        self.assertEqual(len(file_errors), 2)
        for error in file_errors:
            self.assertEqual(error['error_type'], 'FileNotFoundError')
            
    def test_error_severity_levels(self):
        """Test error classification by severity."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Test different severity levels
        logger.log_warning("Skipping corrupted file", "file1.jpg")
        logger.log_error("Failed to create output directory", "critical operation")
        logger.log_critical("Out of memory during video encoding", "system")
        
        warnings = logger.get_warnings()
        errors = logger.get_errors()
        critical = logger.get_critical_errors()
        
        self.assertEqual(len(warnings), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(critical), 1)
        
    def test_log_file_rotation(self):
        """Test log file rotation when size limit is reached."""
        from error_logger import ErrorLogger
        
        log_file = self.test_path / "rotation_test.log"
        logger = ErrorLogger(log_file=log_file, max_log_size_mb=0.001)  # Very small limit
        
        # Generate enough log entries to trigger rotation
        for i in range(100):
            logger.handle_file_error(f"file{i}.jpg", FileNotFoundError(f"File {i} not found"))
            
        # Check if rotation occurred (backup file created)
        backup_files = list(self.test_path.glob("rotation_test.*.log"))
        self.assertGreater(len(backup_files), 0)
        
    def test_structured_error_reporting(self):
        """Test generation of structured error reports."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Add various errors
        logger.handle_file_error("missing.jpg", FileNotFoundError("File not found"))
        logger.handle_image_error("corrupt.jpg", OSError("Cannot decode"))
        logger.log_warning("Unusual file extension", "image.tiff")
        
        # Generate structured report
        report = logger.generate_error_report()
        
        self.assertIn('summary', report)
        self.assertIn('detailed_errors', report)
        self.assertIn('warnings', report)
        self.assertIn('recommendations', report)
        
        # Check summary statistics
        self.assertEqual(report['summary']['total_errors'], 2)
        self.assertEqual(report['summary']['total_warnings'], 1)
        
    def test_error_recovery_suggestions(self):
        """Test automatic generation of error recovery suggestions."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Test specific error types and their suggestions
        file_error = logger.handle_file_error("missing.jpg", FileNotFoundError("File not found"))
        permission_error = logger.handle_permission_error("output.mp4", PermissionError("Access denied"))
        
        self.assertIn('suggestion', file_error)
        self.assertIn('suggestion', permission_error)
        
        # Check that suggestions are relevant
        self.assertIn('check if file exists', file_error['suggestion'].lower())
        self.assertIn('permission', permission_error['suggestion'].lower())
        
    def test_error_context_preservation(self):
        """Test preservation of error context and stack traces."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        try:
            # Simulate nested function calls that raise an error
            def inner_function():
                raise ValueError("Inner error occurred")
            
            def outer_function():
                inner_function()
                
            outer_function()
            
        except Exception as e:
            error_info = logger.handle_generic_error("context_test", e, preserve_stack=True)
            
            self.assertIn('stack_trace', error_info)
            self.assertIn('inner_function', error_info['stack_trace'])
            self.assertIn('outer_function', error_info['stack_trace'])
            
    def test_error_notification_system(self):
        """Test error notification system for critical errors."""
        from error_logger import ErrorLogger
        
        logger = ErrorLogger()
        
        # Register error callback
        notifications = []
        def error_callback(error_info):
            notifications.append(error_info)
            
        logger.register_error_callback(error_callback)
        
        # Generate critical error
        logger.log_critical("System out of memory", "video_encoding")
        
        # Check notification was triggered
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]['severity'], 'critical')
        
    def test_performance_impact_logging(self):
        """Test that logging doesn't significantly impact performance."""
        from error_logger import ErrorLogger
        import time
        
        logger = ErrorLogger()
        
        # Time many logging operations
        start_time = time.time()
        for i in range(1000):
            logger.log_warning(f"Performance test {i}", f"operation_{i}")
        end_time = time.time()
        
        # Should complete quickly (under 1 second for 1000 operations)
        duration = end_time - start_time
        self.assertLess(duration, 1.0)
        
    def test_concurrent_logging_safety(self):
        """Test thread safety of logging operations."""
        from error_logger import ErrorLogger
        import threading
        import time
        
        logger = ErrorLogger()
        errors = []
        
        def log_errors(thread_id):
            try:
                for i in range(100):
                    logger.handle_file_error(f"thread_{thread_id}_file_{i}.jpg", 
                                           FileNotFoundError(f"File from thread {thread_id}"))
            except Exception as e:
                errors.append(e)
                
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=log_errors, args=(i,))
            threads.append(thread)
            thread.start()
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
        # Should have no threading errors
        self.assertEqual(len(errors), 0)
        
        # Should have logged all expected errors
        summary = logger.get_error_summary()
        self.assertEqual(summary['total_errors'], 500)  # 5 threads × 100 errors each


if __name__ == '__main__':
    unittest.main()
