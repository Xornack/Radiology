#!/usr/bin/env python3
"""
Main entry point for the Video from Pictures application.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

# Set environment for GUI applications (helps with some Linux distributions)
if os.name == 'posix':  # Unix-like systems
    os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

def main():
    """Main entry point."""
    try:
        from PyQt6.QtWidgets import QApplication
        from main_window import MainWindow
        
        # Create QApplication instance
        app = QApplication(sys.argv)
        
        # Create and show the main window
        window = MainWindow()
        window.show()
        
        # Start the application event loop
        sys.exit(app.exec())
        
    except ImportError as e:
        print(f"Error importing required modules: {e}")
        print("Please ensure all dependencies are installed:")
        print("pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
