"""
Tests for the settings manager functionality.
"""

import unittest
import tempfile
import shutil
import json
from pathlib import Path
from src.settings_manager import SettingsManager, AppSettings


class TestSettingsManager(unittest.TestCase):
    """Test cases for the SettingsManager class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test config files
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_file = self.test_dir / "test_settings.json"
        
    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directory
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_default_settings(self):
        """Test that default settings are properly initialized."""
        settings_manager = SettingsManager(self.config_file)
        settings = settings_manager.settings
        
        # Check default values
        self.assertEqual(settings.frame_rate, 15)
        self.assertEqual(settings.sorting_method, "natural")
        self.assertEqual(settings.output_filename_pattern, "")
        self.assertFalse(settings.settings_visible)
        self.assertEqual(settings.last_folder_path, "")
        self.assertEqual(settings.window_width, 800)
        self.assertEqual(settings.window_height, 600)
        
    def test_save_and_load_settings(self):
        """Test saving and loading settings from file."""
        # Create settings manager and modify some settings
        settings_manager = SettingsManager(self.config_file)
        settings_manager.update_setting('frame_rate', 30)
        settings_manager.update_setting('sorting_method', 'modification_date')
        settings_manager.update_setting('output_filename_pattern', 'custom_video')
        settings_manager.update_setting('settings_visible', True)
        settings_manager.update_setting('last_folder_path', '/test/path')
        settings_manager.update_setting('window_width', 1024)
        settings_manager.update_setting('window_height', 768)
        
        # Save settings
        result = settings_manager.save_settings()
        self.assertTrue(result)
        self.assertTrue(self.config_file.exists())
        
        # Create new settings manager and verify settings are loaded
        new_settings_manager = SettingsManager(self.config_file)
        new_settings = new_settings_manager.settings
        
        self.assertEqual(new_settings.frame_rate, 30)
        self.assertEqual(new_settings.sorting_method, 'modification_date')
        self.assertEqual(new_settings.output_filename_pattern, 'custom_video')
        self.assertTrue(new_settings.settings_visible)
        self.assertEqual(new_settings.last_folder_path, '/test/path')
        self.assertEqual(new_settings.window_width, 1024)
        self.assertEqual(new_settings.window_height, 768)
        
    def test_get_setting(self):
        """Test getting individual settings."""
        settings_manager = SettingsManager(self.config_file)
        
        # Test getting existing setting
        frame_rate = settings_manager.get_setting('frame_rate')
        self.assertEqual(frame_rate, 15)
        
        # Test getting non-existent setting with default
        unknown_setting = settings_manager.get_setting('unknown_key', 'default_value')
        self.assertEqual(unknown_setting, 'default_value')
        
    def test_update_setting(self):
        """Test updating individual settings."""
        settings_manager = SettingsManager(self.config_file)
        
        # Update valid setting
        settings_manager.update_setting('frame_rate', 25)
        self.assertEqual(settings_manager.settings.frame_rate, 25)
        
        # Try to update invalid setting (should not crash)
        settings_manager.update_setting('invalid_key', 'some_value')
        # Should not have any new attributes
        self.assertFalse(hasattr(settings_manager.settings, 'invalid_key'))
        
    def test_get_video_settings(self):
        """Test getting video-related settings."""
        settings_manager = SettingsManager(self.config_file)
        settings_manager.update_setting('frame_rate', 20)
        settings_manager.update_setting('sorting_method', 'alphabetical')
        settings_manager.update_setting('output_filename_pattern', 'test_video')
        
        video_settings = settings_manager.get_video_settings()
        
        self.assertEqual(video_settings['frame_rate'], 20)
        self.assertEqual(video_settings['sorting_method'], 'alphabetical')
        self.assertEqual(video_settings['output_filename'], 'test_video')
        
    def test_get_ui_settings(self):
        """Test getting UI-related settings."""
        settings_manager = SettingsManager(self.config_file)
        settings_manager.update_setting('settings_visible', True)
        settings_manager.update_setting('last_folder_path', '/some/path')
        settings_manager.update_setting('window_width', 1200)
        settings_manager.update_setting('window_height', 900)
        
        ui_settings = settings_manager.get_ui_settings()
        
        self.assertTrue(ui_settings['settings_visible'])
        self.assertEqual(ui_settings['last_folder_path'], '/some/path')
        self.assertEqual(ui_settings['window_width'], 1200)
        self.assertEqual(ui_settings['window_height'], 900)
        
    def test_update_from_ui(self):
        """Test updating settings from UI values."""
        settings_manager = SettingsManager(self.config_file)
        
        ui_values = {
            'frame_rate': 30,
            'sorting_method': 'modification_date',
            'output_filename': 'ui_test_video',
            'settings_visible': True,
            'last_folder_path': '/ui/test/path',
            'window_size': (1600, 1200)
        }
        
        settings_manager.update_from_ui(ui_values)
        
        # Check that settings were updated correctly
        settings = settings_manager.settings
        self.assertEqual(settings.frame_rate, 30)
        self.assertEqual(settings.sorting_method, 'modification_date')
        self.assertEqual(settings.output_filename_pattern, 'ui_test_video')
        self.assertTrue(settings.settings_visible)
        self.assertEqual(settings.last_folder_path, '/ui/test/path')
        self.assertEqual(settings.window_width, 1600)
        self.assertEqual(settings.window_height, 1200)
        
    def test_reset_to_defaults(self):
        """Test resetting settings to defaults."""
        settings_manager = SettingsManager(self.config_file)
        
        # Modify some settings
        settings_manager.update_setting('frame_rate', 60)
        settings_manager.update_setting('sorting_method', 'alphabetical')
        settings_manager.update_setting('settings_visible', True)
        
        # Reset to defaults
        settings_manager.reset_to_defaults()
        
        # Check that settings are back to defaults
        settings = settings_manager.settings
        self.assertEqual(settings.frame_rate, 15)
        self.assertEqual(settings.sorting_method, "natural")
        self.assertFalse(settings.settings_visible)
        
    def test_load_invalid_config_file(self):
        """Test handling of invalid or corrupted config files."""
        # Create an invalid JSON file
        with open(self.config_file, 'w') as f:
            f.write("invalid json content {")
            
        # Should load defaults without crashing
        settings_manager = SettingsManager(self.config_file)
        settings = settings_manager.settings
        
        # Should have default values
        self.assertEqual(settings.frame_rate, 15)
        self.assertEqual(settings.sorting_method, "natural")
        
    def test_load_partial_config_file(self):
        """Test handling of config files with missing keys."""
        # Create a partial config file
        partial_config = {
            'frame_rate': 25,
            'sorting_method': 'alphabetical'
            # Missing other keys
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(partial_config, f)
            
        # Should load partial settings and use defaults for missing ones
        settings_manager = SettingsManager(self.config_file)
        settings = settings_manager.settings
        
        # Should have loaded values
        self.assertEqual(settings.frame_rate, 25)
        self.assertEqual(settings.sorting_method, 'alphabetical')
        
        # Should have default values for missing keys
        self.assertEqual(settings.output_filename_pattern, "")
        self.assertFalse(settings.settings_visible)
        
    def test_save_failure_handling(self):
        """Test handling of save failures."""
        # Try to save to a non-existent directory with restricted permissions
        invalid_file = Path("/root/invalid/path/settings.json")
        settings_manager = SettingsManager(invalid_file)
        
        # Should handle save failure gracefully
        result = settings_manager.save_settings()
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
