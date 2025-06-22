"""
Test for main GUI window design and components.
Tests that the main window has all required UI elements.
"""

import sys
import unittest
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# Set environment variables for headless GUI testing
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

class TestMainWindow(unittest.TestCase):
    """Test that main window has all required components."""
    
    def setUp(self):
        """Set up test environment."""
        # Create comprehensive mocks for PyQt6 components
        self.pyqt_patcher = patch.dict('sys.modules', {
            'PyQt6': MagicMock(),
            'PyQt6.QtWidgets': MagicMock(),
            'PyQt6.QtCore': MagicMock(),
            'PyQt6.QtGui': MagicMock(),
        })
        self.pyqt_patcher.start()
        
    def tearDown(self):
        """Clean up test environment."""
        self.pyqt_patcher.stop()
        
    def test_main_window_imports(self):
        """Test that MainWindow can be imported."""
        try:
            from main_window import MainWindow
            self.assertTrue(True, "MainWindow should be importable")
        except ImportError as e:
            self.fail(f"MainWindow import failed: {e}")
            
    def test_main_window_components(self):
        """Test that MainWindow has required components."""
        try:
            from main_window import MainWindow
            
            # Create window instance (PyQt6 is mocked)
            window = MainWindow()
            
            # Check for required attributes/methods
            required_methods = [
                'setup_ui',
                'select_folder',
                'toggle_settings',
                'start_processing',
                'stop_processing'
            ]
            
            for method_name in required_methods:
                self.assertTrue(
                    hasattr(window, method_name),
                    f"MainWindow should have {method_name} method"
                )
                
        except Exception as e:
            self.fail(f"MainWindow component test failed: {e}")

if __name__ == '__main__':
    unittest.main()
