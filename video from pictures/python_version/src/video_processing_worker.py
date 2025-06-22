"""
Video processing worker thread for GUI integration.

This module provides QThread-based video processing to prevent GUI blocking
during long-running video creation operations. It integrates all core
processing components with proper signal-based communication.
"""

import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import QThread, pyqtSignal, QObject

# Import our core processing components
from image_loader import ImageLoader
from video_encoder import VideoEncoder
from progress_tracker import ProgressTracker
from error_logger import ErrorLogger


class VideoProcessingWorker(QThread):
    """
    QThread worker for video processing operations.
    
    This class handles all video processing in a separate thread to prevent
    GUI freezing. It communicates with the main thread through Qt signals.
    """
    
    # Qt signals for communication with main thread
    progress_updated = pyqtSignal(int, str)  # progress_percent, status_message
    current_file_updated = pyqtSignal(str)  # current_file_name
    processing_finished = pyqtSignal(bool, str, dict)  # success, message, report
    error_occurred = pyqtSignal(str, str)  # error_type, error_message
    
    def __init__(self, folder_path: Path, settings: Dict[str, Any]):
        """
        Initialize the video processing worker.
        
        Args:
            folder_path: Path to folder containing images
            settings: Processing settings dictionary containing:
                - output_filename: Optional custom output filename
                - frame_rate: Video frame rate (FPS)
                - sorting_method: Image sorting method
                - output_directory: Optional custom output directory
        """
        super().__init__()
        self.folder_path = folder_path
        self.settings = settings
        self.should_stop = False
        
        # Initialize core components
        self.image_loader = ImageLoader()
        self.video_encoder = VideoEncoder()
        self.progress_tracker = ProgressTracker()
        self.error_logger = ErrorLogger()
        
        # Connect progress tracker to our signals
        self.progress_tracker.register_callback(self._on_progress_update)
        
    def run(self):
        """Main processing method that runs in the separate thread."""
        try:
            self._process_video()
        except Exception as e:
            self.error_logger.handle_generic_error("video_processing", e, preserve_stack=True)
            self.error_occurred.emit("ProcessingError", f"Unexpected error during processing: {str(e)}")
            self.processing_finished.emit(False, f"Processing failed: {str(e)}", {})
    
    def stop(self):
        """Request the worker to stop processing."""
        self.should_stop = True
        self.progress_tracker.add_note("Processing stopped by user request")
        
    def _process_video(self):
        """Execute the complete video processing workflow."""
        self.progress_tracker.start_operation("video_creation")
        
        try:
            # Step 1: Load and validate images
            self._emit_progress(5, "Loading and validating images...")
            if self.should_stop:
                return
                
            self.progress_tracker.start_step("image_loading")
            image_files = self._load_and_validate_images()
            
            if not image_files:
                error_msg = "No valid image files found in the selected folder"
                self.error_logger.log_error(error_msg, "image_loading")
                self.processing_finished.emit(False, error_msg, {})
                return
                
            self.progress_tracker.complete_step("image_loading", len(image_files))
            
            # Step 2: Generate output filename
            self._emit_progress(20, "Preparing output settings...")
            if self.should_stop:
                return
                
            output_path = self._generate_output_path()
            
            # Step 3: Create video
            self._emit_progress(25, "Creating video...")
            if self.should_stop:
                return
                
            success = self._create_video(sorted_files, output_path)
            
            if success:
                # Generate final report
                report = self.progress_tracker.generate_report()
                self._emit_progress(100, "Video creation completed successfully!")
                self.processing_finished.emit(True, f"Video saved to: {output_path}", report)
            else:
                error_msg = "Video creation failed"
                self.processing_finished.emit(False, error_msg, {})
                
        except Exception as e:
            self.error_logger.handle_generic_error("video_processing_workflow", e, preserve_stack=True)
            self.processing_finished.emit(False, f"Processing failed: {str(e)}", {})
        finally:
            self.progress_tracker.complete_operation("video_creation")
    
    def _load_and_validate_images(self) -> List[Path]:
        """Load and validate image files from the folder."""
        try:
            # Get sorting method from settings
            sorting_method = self.settings.get('sorting_method', 'natural')
            
            # Load and validate images using the comprehensive method
            result = self.image_loader.load_and_validate_images(
                self.folder_path,
                sort_method=sorting_method
            )
            
            # Log any errors
            if result['errors']:
                for error in result['errors']:
                    self.error_logger.log_error(f"Image validation error: {error}", "image_validation")
            
            valid_files = result['valid_files']
            
            # Update progress and emit current file info
            total_files = result['total_found']
            if total_files > 0:
                self._emit_progress(15, f"Found {len(valid_files)}/{total_files} valid images")
            
            return valid_files
            
        except Exception as e:
            self.error_logger.handle_file_error(str(self.folder_path), e)
            raise
    
    def _sort_images(self, image_files: List[Path]) -> List[Path]:
        """Sort image files according to settings."""
        sorting_method = self.settings.get('sorting_method', 'natural')
        
        if sorting_method == 'modification_date':
            return self.image_loader.sort_by_modification_date(image_files)
        else:
            # Default to natural sorting
            return self.image_loader.sort_naturally(image_files)
    
    def _generate_output_path(self) -> Path:
        """Generate the output file path based on settings."""
        output_filename = self.settings.get('output_filename', '')
        
        if not output_filename:
            # Auto-generate filename from folder name with timestamp
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            folder_name = self.folder_path.name
            output_filename = f"{folder_name}_video_{timestamp}.mp4"
        elif not output_filename.endswith('.mp4'):
            output_filename += '.mp4'
        
        # Determine output directory
        output_directory = self.settings.get('output_directory')
        if output_directory:
            output_dir = Path(output_directory)
        else:
            output_dir = self.folder_path
        
        return output_dir / output_filename
    
    def _create_video(self, image_files: List[Path], output_path: Path) -> bool:
        """Create the video from image files."""
        try:
            self.progress_tracker.start_step("video_encoding")
            
            # Get video settings
            frame_rate = int(self.settings.get('frame_rate', 15))
            
            # Create video with progress callback
            result = self.video_encoder.create_video(
                image_files=image_files,
                output_path=output_path,
                fps=frame_rate,
                progress_callback=self._on_video_progress
            )
            
            if result.get('success', False):
                self.progress_tracker.complete_step("video_encoding", len(image_files))
                return True
            else:
                error_msg = result.get('error', 'Unknown video creation error')
                self.progress_tracker.record_error("video_encoding", error_msg)
                self.error_logger.handle_video_error(str(output_path), Exception(error_msg))
                return False
            
        except Exception as e:
            self.error_logger.handle_video_error(str(output_path), e)
            self.progress_tracker.record_error("video_encoding", str(e))
            return False
    
    def _on_progress_update(self, data: Dict[str, Any]):
        """Handle progress updates from the progress tracker."""
        if 'percentage' in data:
            # Map to our GUI progress range (25-95% for video creation)
            base_progress = 25
            video_progress_range = 70
            video_progress = data['percentage'] * video_progress_range / 100
            total_progress = base_progress + video_progress
            
            status = data.get('status', 'Processing...')
            self._emit_progress(int(total_progress), status)
    
    def _on_video_progress(self, percentage: float, message: str):
        """Handle progress updates from video encoder."""
        if self.should_stop:
            return False  # Signal to video encoder to stop
        
        # Update progress tracker
        self.progress_tracker.update_progress(percentage, message)
        
        # Map to our GUI progress range (25-95% for video creation)
        base_progress = 25
        video_progress_range = 70
        video_progress = percentage * video_progress_range / 100
        total_progress = base_progress + video_progress
        
        self._emit_progress(int(total_progress), message)
        
        return True  # Continue processing
    
    def _emit_progress(self, percentage: int, message: str):
        """Emit progress update signal."""
        self.progress_updated.emit(percentage, message)
    
    def get_error_report(self) -> Dict[str, Any]:
        """Get comprehensive error report."""
        return self.error_logger.generate_error_report()
