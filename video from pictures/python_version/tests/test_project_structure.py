"""
Test for project structure validation.
Tests that the required project directories and files exist.
"""

import os
import unittest
from pathlib import Path

class TestProjectStructure(unittest.TestCase):
    """Test that the project structure is correctly set up."""
    
    def setUp(self):
        """Set up test environment."""
        self.project_root = Path(__file__).parent.parent
        
    def test_project_directories_exist(self):
        """Test that required directories exist."""
        required_dirs = ['src', 'tests']
        
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            self.assertTrue(
                dir_path.exists() and dir_path.is_dir(),
                f"Directory '{dir_name}' should exist"
            )
            
    def test_project_files_exist(self):
        """Test that required files exist."""
        required_files = ['README.md', 'specification_py.md']
        
        for file_name in required_files:
            file_path = self.project_root / file_name
            self.assertTrue(
                file_path.exists() and file_path.is_file(),
                f"File '{file_name}' should exist"
            )
            
    def test_readme_content(self):
        """Test that README.md contains expected content."""
        readme_path = self.project_root / 'README.md'
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        self.assertIn('Video from Pictures - Python Version', content)
        self.assertIn('Project Structure', content)
        self.assertIn('Step 1.1: Project directory structure created', content)

if __name__ == '__main__':
    unittest.main()
