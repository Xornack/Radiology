"""
Test for main.py entry point.
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

class TestMainEntry(unittest.TestCase):
    """Test the main entry point."""
    
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
        
    def test_main_py_imports(self):
        """Test that main.py can be imported."""
        try:
            import main
            self.assertTrue(True, "main.py should be importable")
        except ImportError as e:
            self.fail(f"main.py import failed: {e}")
            
    def test_main_function_exists(self):
        """Test that main function exists."""
        import main
        
        self.assertTrue(hasattr(main, 'main'))
        self.assertTrue(callable(main.main))


if __name__ == '__main__':
    unittest.main()
