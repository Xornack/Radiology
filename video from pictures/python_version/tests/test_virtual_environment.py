"""
Test for virtual environment and dependency setup.
Tests that the virtual environment is properly configured.
"""

import unittest
import subprocess
import sys
from pathlib import Path

class TestVirtualEnvironment(unittest.TestCase):
    """Test that virtual environment is correctly set up."""
    
    def setUp(self):
        """Set up test environment."""
        self.project_root = Path(__file__).parent.parent
        self.venv_path = self.project_root / 'venv'
        
    def test_virtual_environment_exists(self):
        """Test that virtual environment directory exists."""
        self.assertTrue(
            self.venv_path.exists() and self.venv_path.is_dir(),
            "Virtual environment directory should exist"
        )
        
    def test_virtual_environment_structure(self):
        """Test that virtual environment has expected structure."""
        if sys.platform == "win32":
            expected_dirs = ['Scripts', 'Lib', 'Include']
            python_exe = self.venv_path / 'Scripts' / 'python.exe'
        else:
            expected_dirs = ['bin', 'lib', 'include']
            python_exe = self.venv_path / 'bin' / 'python'
            
        for dir_name in expected_dirs:
            dir_path = self.venv_path / dir_name
            self.assertTrue(
                dir_path.exists(),
                f"Virtual environment should have '{dir_name}' directory"
            )
            
        self.assertTrue(
            python_exe.exists(),
            "Virtual environment should have Python executable"
        )
        
    def test_setup_script_exists(self):
        """Test that setup script exists and is executable."""
        setup_script = self.project_root / 'setup.py'
        self.assertTrue(
            setup_script.exists(),
            "setup.py script should exist"
        )
        
        # Check if script is executable (Unix systems)
        if sys.platform != "win32":
            import stat
            file_stat = setup_script.stat()
            is_executable = bool(file_stat.st_mode & stat.S_IEXEC)
            self.assertTrue(
                is_executable,
                "setup.py should be executable"
            )

if __name__ == '__main__':
    unittest.main()
