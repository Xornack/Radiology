"""
Test for progress tracking and reporting functionality.
Tests progress updates, performance metrics, and detailed reporting.
"""

import sys
import unittest
import tempfile
import time
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

class TestProgressTracker(unittest.TestCase):
    """Test progress tracking and reporting functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.test_dir)
        
    def test_progress_tracker_imports(self):
        """Test that progress tracker module can be imported."""
        try:
            from progress_tracker import ProgressTracker
            self.assertTrue(True, "ProgressTracker should be importable")
        except ImportError as e:
            self.fail(f"ProgressTracker import failed: {e}")
            
    def test_progress_tracker_instantiation(self):
        """Test that ProgressTracker can be instantiated."""
        from progress_tracker import ProgressTracker
        
        tracker = ProgressTracker()
        self.assertIsNotNone(tracker)
        
    def test_progress_initialization(self):
        """Test progress tracking initialization."""
        from progress_tracker import ProgressTracker
        
        tracker = ProgressTracker()
        
        # Test initialization with total steps
        tracker.initialize(total_steps=100, operation_name="Test Operation")
        
        self.assertEqual(tracker.get_current_progress(), 0)
        self.assertEqual(tracker.get_total_steps(), 100)
        self.assertEqual(tracker.get_operation_name(), "Test Operation")
        
    def test_progress_updates(self):
        """Test progress update functionality."""
        from progress_tracker import ProgressTracker
        
        tracker = ProgressTracker()
        tracker.initialize(total_steps=10, operation_name="Test")
        
        # Test progress updates
        tracker.update_progress(1, "Processing step 1")
        self.assertEqual(tracker.get_current_progress(), 10.0)  # 1/10 * 100
        
        tracker.update_progress(5, "Processing step 5")
        self.assertEqual(tracker.get_current_progress(), 50.0)  # 5/10 * 100
        
        tracker.update_progress(10, "Completed")
        self.assertEqual(tracker.get_current_progress(), 100.0)  # 10/10 * 100
        
    def test_time_estimation(self):
        """Test estimated time remaining calculation."""
        from progress_tracker import ProgressTracker
        
        tracker = ProgressTracker()
        tracker.initialize(total_steps=10, operation_name="Test")
        
        # Simulate some progress with time delays
        with patch('time.time') as mock_time:
            # Mock time progression - provide enough values
            mock_time.side_effect = [0, 10, 10, 20, 20, 30, 30]
            
            tracker.start_timing()
            tracker.update_progress(1, "Step 1")
            tracker.update_progress(2, "Step 2")
            tracker.update_progress(3, "Step 3")
            
            eta = tracker.get_estimated_time_remaining()
            self.assertIsInstance(eta, (int, float))
            self.assertGreater(eta, 0)
            
    def test_performance_metrics(self):
        """Test performance metrics collection."""
        from progress_tracker import ProgressTracker
        
        tracker = ProgressTracker()
        tracker.initialize(total_steps=5, operation_name="Test")
        
        # Add some performance metrics
        tracker.add_performance_metric("files_processed", 100)
        tracker.add_performance_metric("processing_speed", 25.5)
        tracker.add_performance_metric("memory_usage", 512)
        
        metrics = tracker.get_performance_metrics()
        
        self.assertEqual(metrics["files_processed"], 100)
        self.assertEqual(metrics["processing_speed"], 25.5)
        self.assertEqual(metrics["memory_usage"], 512)
        
    def test_error_tracking(self):
        """Test error and warning tracking."""
        from progress_tracker import ProgressTracker
        
        tracker = ProgressTracker()
        tracker.initialize(total_steps=10, operation_name="Test")
        
        # Add some errors and warnings
        tracker.add_error("Failed to process file1.jpg", "FileNotFoundError")
        tracker.add_warning("Corrupted file skipped: file2.jpg")
        tracker.add_error("Invalid format: file3.txt", "FormatError")
        
        errors = tracker.get_errors()
        warnings = tracker.get_warnings()
        
        self.assertEqual(len(errors), 2)
        self.assertEqual(len(warnings), 1)
        
        # Check error details
        self.assertIn("file1.jpg", errors[0]["message"])
        self.assertEqual(errors[0]["type"], "FileNotFoundError")
        
    def test_progress_callback_system(self):
        """Test progress callback registration and notification."""
        from progress_tracker import ProgressTracker
        
        tracker = ProgressTracker()
        tracker.initialize(total_steps=5, operation_name="Test")
        
        # Register callbacks
        callback_calls = []
        
        def progress_callback(percentage, message, eta=None):
            callback_calls.append((percentage, message, eta))
            
        tracker.register_callback(progress_callback)
        
        # Make progress updates
        tracker.update_progress(1, "Step 1")
        tracker.update_progress(3, "Step 3")
        
        # Check that callbacks were called
        self.assertEqual(len(callback_calls), 2)
        self.assertEqual(callback_calls[0][0], 20.0)  # 1/5 * 100
        self.assertEqual(callback_calls[1][0], 60.0)  # 3/5 * 100
        
    def test_detailed_report_generation(self):
        """Test generation of detailed progress reports."""
        from progress_tracker import ProgressTracker
        
        tracker = ProgressTracker()
        tracker.initialize(total_steps=10, operation_name="Video Creation")
        
        # Simulate a complete operation
        tracker.start_timing()
        
        with patch('time.time') as mock_time:
            # Provide enough time values for all operations
            mock_time.side_effect = [0, 5, 5, 10, 10, 15, 15, 20, 20, 25]
            
            tracker.update_progress(2, "Loading images")
            tracker.add_performance_metric("images_loaded", 50)
            
            tracker.update_progress(6, "Processing images")
            tracker.add_warning("Skipped corrupted file")
            
            tracker.update_progress(10, "Creating video")
            tracker.add_performance_metric("video_size_mb", 25.6)
            
            tracker.complete_operation()
            
        # Generate detailed report
        report = tracker.generate_detailed_report()
        
        # Check report structure
        self.assertIn('operation_summary', report)
        self.assertIn('timing_info', report)
        self.assertIn('performance_metrics', report)
        self.assertIn('errors_and_warnings', report)
        
        # Check specific values
        self.assertEqual(report['operation_summary']['name'], "Video Creation")
        self.assertEqual(report['operation_summary']['status'], "completed")
        self.assertEqual(report['performance_metrics']['images_loaded'], 50)
        self.assertEqual(len(report['errors_and_warnings']['warnings']), 1)
        
    def test_progress_persistence(self):
        """Test saving and loading progress state."""
        from progress_tracker import ProgressTracker
        
        tracker = ProgressTracker()
        tracker.initialize(total_steps=20, operation_name="Batch Processing")
        
        # Make some progress
        tracker.update_progress(5, "Processing batch 1")
        tracker.add_performance_metric("batch_size", 100)
        tracker.add_error("Failed item", "ProcessingError")
        
        # Save state
        save_path = self.test_path / "progress_state.json"
        tracker.save_state(save_path)
        
        # Create new tracker and load state
        tracker2 = ProgressTracker()
        tracker2.load_state(save_path)
        
        # Verify loaded state
        self.assertEqual(tracker2.get_current_progress(), 25.0)  # 5/20 * 100
        self.assertEqual(tracker2.get_operation_name(), "Batch Processing")
        self.assertEqual(len(tracker2.get_errors()), 1)
        
    def test_concurrent_operation_tracking(self):
        """Test tracking multiple concurrent operations."""
        from progress_tracker import ProgressTracker
        
        # Test that we can track multiple operations
        tracker1 = ProgressTracker(operation_id="op1")
        tracker2 = ProgressTracker(operation_id="op2")
        
        tracker1.initialize(total_steps=10, operation_name="Operation 1")
        tracker2.initialize(total_steps=5, operation_name="Operation 2")
        
        tracker1.update_progress(3, "Op1 step 3")
        tracker2.update_progress(2, "Op2 step 2")
        
        self.assertEqual(tracker1.get_current_progress(), 30.0)
        self.assertEqual(tracker2.get_current_progress(), 40.0)
        
    def test_step_timing_analysis(self):
        """Test individual step timing analysis."""
        from progress_tracker import ProgressTracker
        
        tracker = ProgressTracker()
        tracker.initialize(total_steps=3, operation_name="Step Analysis")
        
        with patch('time.time') as mock_time:
            # Mock time progression accounting for actual time.time() calls:
            # 1: start_timing → 0
            # 2: update_progress(1) → 0  
            # 3: update_progress(1) something → 2
            # 4: update_progress(2) → 2 (ends step 1)
            # 5: update_progress(3) → 7 (ends step 2)
            # 6: complete_operation → 10 (ends step 3)
            mock_time.side_effect = [0, 0, 2, 2, 7, 10]
            
            tracker.start_timing()
            tracker.update_progress(1, "Step 1")  # Step 1 starts at time 0
            tracker.update_progress(2, "Step 2")  # Step 1 ends at time 2 (0->2 = 2s for step 1)  
            tracker.update_progress(3, "Step 3")  # Step 2 ends at time 7 (2->7 = 5s for step 2)
            tracker.complete_operation()  # Step 3 ends at time 10 (7->10 = 3s for step 3)
            
        step_timings = tracker.get_step_timings()
        
        self.assertEqual(len(step_timings), 3)
        self.assertEqual(step_timings[0]['step_number'], 1)
        self.assertEqual(step_timings[0]['duration'], 2.0)  # 0 to 2
        self.assertEqual(step_timings[1]['step_number'], 2)  
        self.assertEqual(step_timings[1]['duration'], 5.0)  # 2 to 7
        self.assertEqual(step_timings[2]['step_number'], 3)
        self.assertEqual(step_timings[2]['duration'], 3.0)  # 7 to 10


if __name__ == '__main__':
    unittest.main()
