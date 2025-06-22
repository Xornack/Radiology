"""
Main GUI window for Video from Pictures application.
Provides the user interface for selecting image folders and converting them to videos.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QProgressBar, QLineEdit, 
    QComboBox, QGroupBox, QFileDialog, QApplication,
    QSpacerItem, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont


class MainWindow(QMainWindow):
    """Main application window for Video from Pictures converter."""
    
    def __init__(self):
        super().__init__()
        self.selected_folder = None
        self.processing_thread = None
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the user interface components."""
        self.setWindowTitle("Video from Pictures - Medical Image Converter")
        self.setMinimumSize(600, 400)
        self.resize(800, 500)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Medical Image Sequence to Video Converter")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Folder selection section
        folder_section = self._create_folder_selection_section()
        main_layout.addWidget(folder_section)
        
        # Progress section
        progress_section = self._create_progress_section()
        main_layout.addWidget(progress_section)
        
        # Control buttons section
        controls_section = self._create_controls_section()
        main_layout.addWidget(controls_section)
        
        # Settings section (collapsible)
        self.settings_section = self._create_settings_section()
        main_layout.addWidget(self.settings_section)
        
        # Add spacer to push everything to top
        spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        main_layout.addItem(spacer)
        
        # Initially hide settings
        self.settings_section.setVisible(False)
        
    def _create_folder_selection_section(self):
        """Create the folder selection section."""
        group_box = QGroupBox("Image Folder Selection")
        layout = QVBoxLayout(group_box)
        
        # Folder path display
        folder_layout = QHBoxLayout()
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("QLabel { border: 1px solid gray; padding: 5px; background-color: #f0f0f0; }")
        folder_layout.addWidget(QLabel("Selected Folder:"))
        folder_layout.addWidget(self.folder_label, 1)
        
        # Browse button
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.browse_button)
        
        layout.addLayout(folder_layout)
        
        # Folder info
        self.folder_info_label = QLabel("Please select a folder containing image files (JPEG, PNG, DICOM)")
        self.folder_info_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        layout.addWidget(self.folder_info_label)
        
        return group_box
        
    def _create_progress_section(self):
        """Create the progress display section."""
        group_box = QGroupBox("Processing Progress")
        layout = QVBoxLayout(group_box)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Ready to process images")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Current file label
        self.current_file_label = QLabel("")
        self.current_file_label.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        self.current_file_label.setVisible(False)
        layout.addWidget(self.current_file_label)
        
        return group_box
        
    def _create_controls_section(self):
        """Create the control buttons section."""
        group_box = QGroupBox("Processing Controls")
        layout = QHBoxLayout(group_box)
        
        # Start processing button
        self.start_button = QPushButton("Start Processing")
        self.start_button.clicked.connect(self.start_processing)
        self.start_button.setEnabled(False)
        layout.addWidget(self.start_button)
        
        # Stop processing button
        self.stop_button = QPushButton("Stop Processing")
        self.stop_button.clicked.connect(self.stop_processing)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        
        # Settings toggle button
        self.settings_button = QPushButton("Show Settings")
        self.settings_button.clicked.connect(self.toggle_settings)
        layout.addWidget(self.settings_button)
        
        # Add spacer
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addItem(spacer)
        
        return group_box
        
    def _create_settings_section(self):
        """Create the settings section (initially hidden)."""
        group_box = QGroupBox("Processing Settings")
        layout = QVBoxLayout(group_box)
        
        # Output filename section
        filename_layout = QHBoxLayout()
        filename_layout.addWidget(QLabel("Output Filename:"))
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Auto-generate from folder name")
        filename_layout.addWidget(self.filename_input)
        layout.addLayout(filename_layout)
        
        # Frame rate section
        framerate_layout = QHBoxLayout()
        framerate_layout.addWidget(QLabel("Frame Rate (FPS):"))
        self.framerate_combo = QComboBox()
        self.framerate_combo.addItems(['5', '10', '15', '20', '25', '30', '60'])
        self.framerate_combo.setCurrentText('15')  # Default value
        framerate_layout.addWidget(self.framerate_combo)
        framerate_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        layout.addLayout(framerate_layout)
        
        # Sorting method section
        sorting_layout = QHBoxLayout()
        sorting_layout.addWidget(QLabel("Sort Images By:"))
        self.sorting_combo = QComboBox()
        self.sorting_combo.addItems(['Filename (Natural)', 'Filename (Alphabetical)', 'Modification Date'])
        self.sorting_combo.setCurrentText('Filename (Natural)')  # Default value
        sorting_layout.addWidget(self.sorting_combo)
        sorting_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        layout.addLayout(sorting_layout)
        
        return group_box
        
    def select_folder(self):
        """Open folder selection dialog and update UI."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Image Folder",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder_path:
            self.selected_folder = Path(folder_path)
            self.folder_label.setText(str(self.selected_folder))
            
            # Update folder info
            self._update_folder_info()
            
            # Enable start button if folder is valid
            self.start_button.setEnabled(True)
            self.status_label.setText("Folder selected. Ready to process images.")
        else:
            self.selected_folder = None
            self.folder_label.setText("No folder selected")
            self.start_button.setEnabled(False)
            self.status_label.setText("Please select a folder containing image files.")
            
    def _update_folder_info(self):
        """Update the folder information display."""
        if not self.selected_folder or not self.selected_folder.exists():
            self.folder_info_label.setText("Selected folder does not exist")
            return
            
        # Count supported image files
        supported_extensions = {'.jpg', '.jpeg', '.png', '.dcm', '.dicom'}
        image_files = []
        
        for ext in supported_extensions:
            image_files.extend(list(self.selected_folder.glob(f'*{ext}')))
            image_files.extend(list(self.selected_folder.glob(f'*{ext.upper()}')))
            
        file_count = len(image_files)
        
        if file_count == 0:
            self.folder_info_label.setText("No supported image files found (JPEG, PNG, DICOM)")
            self.start_button.setEnabled(False)
        else:
            self.folder_info_label.setText(f"Found {file_count} image file(s) ready for processing")
            self.start_button.setEnabled(True)
            
    def toggle_settings(self):
        """Toggle the visibility of the settings section."""
        is_visible = self.settings_section.isVisible()
        self.settings_section.setVisible(not is_visible)
        
        # Update button text
        if is_visible:
            self.settings_button.setText("Show Settings")
        else:
            self.settings_button.setText("Hide Settings")
            
    def start_processing(self):
        """Start the image processing and video creation."""
        if not self.selected_folder:
            QMessageBox.warning(self, "Warning", "Please select a folder first.")
            return
            
        # Update UI for processing state
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.browse_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.current_file_label.setVisible(True)
        self.status_label.setText("Starting processing...")
        
        # TODO: Implement actual processing logic in Phase 2
        # For now, just show a placeholder message
        QMessageBox.information(
            self, 
            "Processing Started", 
            "Processing functionality will be implemented in Phase 2.\n"
            "This is the GUI design phase (Step 1.3)."
        )
        
        # Reset UI state (temporary for this phase)
        self._reset_processing_state()
        
    def stop_processing(self):
        """Stop the current processing operation."""
        # TODO: Implement actual stop logic in Phase 2
        self.status_label.setText("Processing stopped by user.")
        self._reset_processing_state()
        
    def _reset_processing_state(self):
        """Reset the UI to non-processing state."""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.browse_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.current_file_label.setVisible(False)
        self.status_label.setText("Ready to process images")


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Video from Pictures")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Medical Imaging Tools")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
