"""
Settings Manager for Video from Pictures application.

This module handles loading, saving, and managing user preferences
using JSON configuration files.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class AppSettings:
    """Data class to hold application settings."""
    # Video encoding settings
    frame_rate: int = 15
    
    # Image processing settings
    sorting_method: str = "natural"  # natural, alphabetical, modification_date
    
    # Output settings
    output_filename_pattern: str = ""  # Empty means auto-generate
    
    # UI settings
    settings_visible: bool = False
    last_folder_path: str = ""
    
    # Window settings
    window_width: int = 800
    window_height: int = 600


class SettingsManager:
    """Manages application settings persistence."""
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize the settings manager.
        
        Args:
            config_file: Path to the configuration file. If None, uses default location.
        """
        self.logger = logging.getLogger(__name__)
        
        # Default config file location
        if config_file is None:
            config_dir = Path.home() / ".video_from_pictures"
            config_dir.mkdir(exist_ok=True)
            config_file = config_dir / "settings.json"
            
        self.config_file = config_file
        self._settings = AppSettings()
        
        # Load settings on initialization
        self.load_settings()
        
    @property
    def settings(self) -> AppSettings:
        """Get the current settings."""
        return self._settings
        
    def load_settings(self) -> None:
        """Load settings from the configuration file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Update settings with loaded data
                for key, value in data.items():
                    if hasattr(self._settings, key):
                        setattr(self._settings, key, value)
                        
                self.logger.info(f"Settings loaded from {self.config_file}")
            else:
                self.logger.info("No settings file found, using defaults")
                
        except Exception as e:
            self.logger.warning(f"Failed to load settings: {e}. Using defaults.")
            self._settings = AppSettings()  # Reset to defaults
            
    def save_settings(self) -> bool:
        """
        Save current settings to the configuration file.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Ensure the directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert settings to dictionary
            settings_dict = asdict(self._settings)
            
            # Write to file with proper formatting
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"Settings saved to {self.config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
            return False
            
    def update_setting(self, key: str, value: Any) -> None:
        """
        Update a specific setting.
        
        Args:
            key: The setting key to update
            value: The new value
        """
        if hasattr(self._settings, key):
            setattr(self._settings, key, value)
            self.logger.debug(f"Setting updated: {key} = {value}")
        else:
            self.logger.warning(f"Unknown setting key: {key}")
            
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a specific setting value.
        
        Args:
            key: The setting key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            The setting value or default
        """
        return getattr(self._settings, key, default)
        
    def reset_to_defaults(self) -> None:
        """Reset all settings to their default values."""
        self._settings = AppSettings()
        self.logger.info("Settings reset to defaults")
        
    def get_video_settings(self) -> Dict[str, Any]:
        """
        Get settings relevant for video encoding.
        
        Returns:
            Dictionary with video encoding settings
        """
        return {
            'frame_rate': self._settings.frame_rate,
            'sorting_method': self._settings.sorting_method,
            'output_filename': self._settings.output_filename_pattern
        }
        
    def get_ui_settings(self) -> Dict[str, Any]:
        """
        Get settings relevant for UI state.
        
        Returns:
            Dictionary with UI settings
        """
        return {
            'settings_visible': self._settings.settings_visible,
            'last_folder_path': self._settings.last_folder_path,
            'window_width': self._settings.window_width,
            'window_height': self._settings.window_height
        }
        
    def update_from_ui(self, ui_values: Dict[str, Any]) -> None:
        """
        Update settings from UI values.
        
        Args:
            ui_values: Dictionary with UI values to update
        """
        # Map UI values to setting keys
        mapping = {
            'frame_rate': 'frame_rate',
            'sorting_method': 'sorting_method',
            'output_filename': 'output_filename_pattern',
            'settings_visible': 'settings_visible',
            'last_folder_path': 'last_folder_path',
            'window_size': ('window_width', 'window_height')
        }
        
        for ui_key, value in ui_values.items():
            if ui_key in mapping:
                setting_key = mapping[ui_key]
                if isinstance(setting_key, tuple):
                    # Handle special cases like window size
                    if ui_key == 'window_size' and len(value) == 2:
                        self._settings.window_width = value[0]
                        self._settings.window_height = value[1]
                else:
                    self.update_setting(setting_key, value)
