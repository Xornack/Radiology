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
    QSpacerItem, QSizePolicy, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# Import our video processing worker and settings manager
from video_processing_worker import VideoProcessingWorker
from settings_manager import SettingsManager


class MainWindow(QMainWindow):
    """Main application window for Video from Pictures converter."""
    
    def __init__(self):
        super().__init__()
        self.selected_folder = None
        self.processing_thread = None
        
        # Initialize settings manager
        self.settings_manager = SettingsManager()
        
        self.setup_ui()
        self.load_ui_settings()
        
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
            
            # Save the selected folder path
            self.settings_manager.update_setting('last_folder_path', str(self.selected_folder))
            
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
            
        # Save the updated visibility state
        self.settings_manager.update_setting('settings_visible', not is_visible)
            
    def start_processing(self):
        """Start the image processing and video creation."""
        if not self.selected_folder:
            self._show_selectable_message_box("warning", "Warning", "Please select a folder first.")
            return
            
        # Update UI for processing state
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.browse_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.current_file_label.setVisible(True)
        self.status_label.setText("Starting processing...")
        
        # Save current settings before processing
        self.save_ui_settings()
        
        # Gather settings from UI
        settings = {
            'output_filename': self.filename_input.text().strip(),
            'frame_rate': int(self.framerate_combo.currentText()),
            'sorting_method': self._get_sorting_method(),
            'output_directory': None  # Use source folder by default
        }
        
        # Create and start processing worker thread
        self.processing_thread = VideoProcessingWorker(self.selected_folder, settings)
        
        # Connect worker signals to UI update methods
        self.processing_thread.progress_updated.connect(self._on_progress_updated)
        self.processing_thread.current_file_updated.connect(self._on_current_file_updated)
        self.processing_thread.processing_finished.connect(self._on_processing_finished)
        self.processing_thread.error_occurred.connect(self._on_error_occurred)
        
        # Start the worker thread
        self.processing_thread.start()
        
    def stop_processing(self):
        """Stop the current processing operation."""
        if self.processing_thread and self.processing_thread.isRunning():
            self.status_label.setText("Stopping processing...")
            self.processing_thread.stop()
            self.processing_thread.wait(5000)  # Wait up to 5 seconds for thread to finish
            
            if self.processing_thread.isRunning():
                self.processing_thread.terminate()
                self.processing_thread.wait()
                
        self.status_label.setText("Processing stopped by user.")
        self._reset_processing_state()
        
    def _get_sorting_method(self) -> str:
        """Convert UI sorting selection to internal method name."""
        sorting_text = self.sorting_combo.currentText()
        if "Natural" in sorting_text:
            return "natural"
        elif "Alphabetical" in sorting_text:
            return "alphabetical"
        elif "Modification Date" in sorting_text:
            return "modification_date"
        else:
            return "natural"  # Default
    
    def _on_progress_updated(self, percentage: int, message: str):
        """Handle progress updates from worker thread."""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(message)
    
    def _on_current_file_updated(self, filename: str):
        """Handle current file updates from worker thread."""
        self.current_file_label.setText(filename)
    
    def _on_processing_finished(self, success: bool, message: str, report: dict):
        """Handle processing completion from worker thread."""
        self._reset_processing_state()
        
        if success:
            # Show success message with details
            details = self._format_processing_report(report)
            self._show_selectable_message_box(
                "information",
                "Processing Complete",
                f"{message}\n\n{details}"
            )
        else:
            # Show error message
            error_details = ""
            if self.processing_thread:
                error_report = self.processing_thread.get_error_report()
                if error_report.get('total_errors', 0) > 0:
                    error_details = f"\n\nErrors encountered: {error_report['total_errors']}"
                    if error_report.get('recommendations'):
                        error_details += f"\nRecommendations:\n" + "\n".join(f"• {r}" for r in error_report['recommendations'][:3])
            
            self._show_selectable_message_box(
                "critical",
                "Processing Failed",
                f"{message}{error_details}"
            )
    
    def _on_error_occurred(self, error_type: str, error_message: str):
        """Handle error notifications from worker thread."""
        # For now, just update status. Major errors will be handled in _on_processing_finished
        self.status_label.setText(f"Error: {error_message}")
    
    def _format_processing_report(self, report: dict) -> str:
        """Format the processing report for display."""
        if not report:
            return "Processing completed."
        
        summary = report.get('summary', {})
        timing = summary.get('total_time', 0)
        
        details = []
        if timing > 0:
            details.append(f"Processing time: {timing:.1f} seconds")
        
        if 'steps' in report:
            for step_name, step_data in report['steps'].items():
                if step_data.get('completed', False):
                    items_processed = step_data.get('items_processed', 0)
                    if items_processed > 0:
                        details.append(f"{step_name.replace('_', ' ').title()}: {items_processed} items")
        
        return "\n".join(details) if details else "Processing completed successfully."
        
    def _reset_processing_state(self):
        """Reset the UI to non-processing state."""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.browse_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.current_file_label.setVisible(False)
        self.status_label.setText("Ready to process images")
        
    def load_ui_settings(self):
        """Load and apply UI settings from the settings manager."""
        ui_settings = self.settings_manager.get_ui_settings()
        
        # Restore window size
        self.resize(ui_settings['window_width'], ui_settings['window_height'])
        
        # Restore settings visibility
        self.settings_section.setVisible(ui_settings['settings_visible'])
        if ui_settings['settings_visible']:
            self.settings_button.setText("Hide Settings")
        else:
            self.settings_button.setText("Show Settings")
            
        # Restore last folder path if it exists and is valid
        if ui_settings['last_folder_path'] and Path(ui_settings['last_folder_path']).exists():
            self.selected_folder = Path(ui_settings['last_folder_path'])
            self.folder_label.setText(str(self.selected_folder))
            self._update_folder_info()
            
        # Load video processing settings
        video_settings = self.settings_manager.get_video_settings()
        
        # Set frame rate
        frame_rate_str = str(video_settings['frame_rate'])
        index = self.framerate_combo.findText(frame_rate_str)
        if index >= 0:
            self.framerate_combo.setCurrentIndex(index)
            
        # Set sorting method
        sorting_mapping = {
            'natural': 'Filename (Natural)',
            'alphabetical': 'Filename (Alphabetical)', 
            'modification_date': 'Modification Date'
        }
        sorting_text = sorting_mapping.get(video_settings['sorting_method'], 'Filename (Natural)')
        index = self.sorting_combo.findText(sorting_text)
        if index >= 0:
            self.sorting_combo.setCurrentIndex(index)
            
        # Set output filename pattern
        if video_settings['output_filename']:
            self.filename_input.setText(video_settings['output_filename'])
            
    def save_ui_settings(self):
        """Save current UI settings to the settings manager."""
        # Get current window size
        size = self.size()
        
        # Get current UI values
        ui_values = {
            'window_size': (size.width(), size.height()),
            'settings_visible': self.settings_section.isVisible(),
            'last_folder_path': str(self.selected_folder) if self.selected_folder else "",
            'frame_rate': int(self.framerate_combo.currentText()),
            'output_filename': self.filename_input.text().strip(),
        }
        
        # Map sorting method
        sorting_mapping = {
            'Filename (Natural)': 'natural',
            'Filename (Alphabetical)': 'alphabetical',
            'Modification Date': 'modification_date'
        }
        ui_values['sorting_method'] = sorting_mapping.get(
            self.sorting_combo.currentText(), 'natural'
        )
        
        # Update settings and save
        self.settings_manager.update_from_ui(ui_values)
        self.settings_manager.save_settings()
        
    def closeEvent(self, event):
        """Handle window close event to save settings."""
        # Stop any running processing
        if self.processing_thread and self.processing_thread.isRunning():
            self.stop_processing()
            # Wait a bit for the thread to stop
            self.processing_thread.wait(1000)
            
        # Save settings before closing
        self.save_ui_settings()
        
        # Accept the close event
        event.accept()

    def _show_selectable_message_box(self, icon_type: str, title: str, message: str):
        """
        Show a message box with selectable text.
        
        Args:
            icon_type: Type of icon ('information', 'warning', 'critical')
            title: Window title
            message: Message text
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        # Set the appropriate icon
        if icon_type == 'information':
            msg_box.setIcon(QMessageBox.Icon.Information)
        elif icon_type == 'warning':
            msg_box.setIcon(QMessageBox.Icon.Warning)
        elif icon_type == 'critical':
            msg_box.setIcon(QMessageBox.Icon.Critical)
        
        # Make text selectable
        msg_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        
        # Show the dialog
        msg_box.exec()
