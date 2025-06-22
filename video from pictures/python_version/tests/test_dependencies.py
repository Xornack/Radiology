"""
Test for dependency management and virtual environment setup.
Tests that the requirements.txt file exists and contains expected dependencies.
"""

import unittest
from pathlib import Path

class TestDependencies(unittest.TestCase):
    """Test that dependencies are correctly specified."""
    
    def setUp(self):
        """Set up test environment."""
        self.project_root = Path(__file__).parent.parent
        self.requirements_file = self.project_root / 'requirements.txt'
        
    def test_requirements_file_exists(self):
        """Test that requirements.txt exists."""
        self.assertTrue(
            self.requirements_file.exists(),
            "requirements.txt file should exist"
        )
        
    def test_core_dependencies_specified(self):
        """Test that core dependencies are listed in requirements.txt."""
        with open(self.requirements_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        required_packages = [
            'PyQt6',
            'Pillow', 
            'pydicom',
            'moviepy',
            'pytest',
            'pip-audit'
        ]
        
        for package in required_packages:
            self.assertIn(
                package, content,
                f"Package '{package}' should be in requirements.txt"
            )
            
    def test_requirements_format(self):
        """Test that requirements.txt is properly formatted."""
        with open(self.requirements_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Filter out comment lines and empty lines
        package_lines = [
            line.strip() for line in lines 
            if line.strip() and not line.strip().startswith('#')
        ]
        
        # Each package line should contain a version specification
        for line in package_lines:
            if line:  # Skip empty lines
                self.assertIn(
                    '>=', line,
                    f"Package line '{line}' should specify minimum version with '>='"
                )

if __name__ == '__main__':
    unittest.main()
