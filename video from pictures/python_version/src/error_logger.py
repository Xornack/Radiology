"""
Comprehensive error handling and logging functionality.

This module provides robust error handling, logging capabilities, and error reporting
for the video creation application. It handles various types of errors including
file operations, video encoding, image processing, and system-level errors.
"""

import logging
import json
import time
import traceback
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import os


@dataclass
class ErrorInfo:
    """Information about an error that occurred."""
    error_type: str
    message: str
    file_path: Optional[str] = None
    timestamp: float = None
    severity: str = "error"  # warning, error, critical
    suggestion: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class ErrorLogger:
    """
    Comprehensive error logger with categorization, reporting, and recovery suggestions.
    
    Provides structured error handling with automatic categorization, severity levels,
    logging to files, error aggregation, and recovery suggestions.
    """
    
    def __init__(self, log_file: Optional[Union[str, Path]] = None, max_log_size_mb: float = 10.0):
        """
        Initialize the error logger.
        
        Args:
            log_file: Path to log file. If None, uses default location.
            max_log_size_mb: Maximum log file size before rotation
        """
        self.log_file = Path(log_file) if log_file else Path("application_errors.log")
        self.max_log_size_bytes = int(max_log_size_mb * 1024 * 1024)
        
        self.errors: List[ErrorInfo] = []
        self.warnings: List[ErrorInfo] = []
        self.critical_errors: List[ErrorInfo] = []
        
        self.error_callbacks: List[Callable] = []
        self._lock = threading.Lock()
        
        # Set up file logging
        self._setup_file_logging()
        
    def _setup_file_logging(self):
        """Set up file-based logging configuration."""
        # Create log directory if it doesn't exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        self.logger = logging.getLogger('video_app_errors')
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create file handler
        handler = logging.FileHandler(self.log_file, encoding='utf-8')
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
    def _rotate_log_if_needed(self):
        """Rotate log file if it exceeds size limit."""
        if self.log_file.exists() and self.log_file.stat().st_size > self.max_log_size_bytes:
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{self.log_file.stem}.{timestamp}{self.log_file.suffix}"
            backup_path = self.log_file.parent / backup_name
            
            # Close current handler to release file handle
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)
            
            try:
                # Move current log to backup
                self.log_file.rename(backup_path)
            except Exception as e:
                # If rename fails, we should still recreate the handler
                pass
            
            # Recreate handler with new file
            handler = logging.FileHandler(self.log_file, encoding='utf-8')
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
    def _add_error(self, error_info: ErrorInfo):
        """Add error to appropriate collection based on severity."""
        with self._lock:
            if error_info.severity == "warning":
                self.warnings.append(error_info)
            elif error_info.severity == "critical":
                self.critical_errors.append(error_info)
                # Notify callbacks for critical errors
                for callback in self.error_callbacks:
                    try:
                        callback(asdict(error_info))
                    except Exception:
                        pass  # Don't let callback errors break logging
            else:
                self.errors.append(error_info)
                
            # Log to file
            self._log_to_file(error_info)
            
    def _log_to_file(self, error_info: ErrorInfo):
        """Log error information to file."""
        # Check for rotation before logging
        self._rotate_log_if_needed()
        
        message_parts = [error_info.message]
        
        if error_info.file_path:
            message_parts.append(f"File: {error_info.file_path}")
            
        if error_info.context:
            message_parts.append(f"Context: {json.dumps(error_info.context)}")
            
        if error_info.suggestion:
            message_parts.append(f"Suggestion: {error_info.suggestion}")
            
        message = " | ".join(message_parts)
        
        if error_info.severity == "warning":
            self.logger.warning(f"[{error_info.error_type}] {message}")
        elif error_info.severity == "critical":
            self.logger.critical(f"[{error_info.error_type}] {message}")
        else:
            self.logger.error(f"[{error_info.error_type}] {message}")
            
        if error_info.stack_trace:
            self.logger.error(f"Stack trace: {error_info.stack_trace}")
            
    def _get_error_suggestion(self, error_type: str, message: str, file_path: str = None) -> str:
        """Generate recovery suggestions based on error type and message."""
        suggestions = {
            'FileNotFoundError': "Check if file exists and verify the file path is correct.",
            'PermissionError': "Check file/directory permissions and ensure you have write access.",
            'DiskSpaceError': "Free up disk space or choose a different output location.",
            'ImageProcessingError': "Verify the image file is not corrupted and is in a supported format.",
            'VideoEncodingError': "Check video codec availability and output directory permissions.",
            'DicomProcessingError': "Ensure the file is a valid DICOM file and not corrupted.",
            'MemoryError': "Close other applications to free memory or process fewer images at once.",
            'NetworkError': "Check network connectivity and try again.",
        }
        
        # Default suggestion
        base_suggestion = suggestions.get(error_type, "Check the error details and try again.")
        
        # Add specific suggestions based on message content
        if "space" in message.lower():
            base_suggestion += " Consider using a different output location with more available space."
        elif "permission" in message.lower():
            base_suggestion += " Try running the application as administrator or change the output location."
        elif "codec" in message.lower():
            base_suggestion += " Ensure required video codecs are installed on your system."
        elif "memory" in message.lower():
            base_suggestion += " Try processing fewer images at once or restart the application."
            
        return base_suggestion
        
    def handle_file_error(self, file_path: str, exception: Exception) -> Dict[str, Any]:
        """Handle file operation errors."""
        error_type = "FileNotFoundError" if isinstance(exception, FileNotFoundError) else "FileOperationError"
        
        error_info = ErrorInfo(
            error_type=error_type,
            message=str(exception),
            file_path=file_path,
            suggestion=self._get_error_suggestion(error_type, str(exception), file_path)
        )
        
        self._add_error(error_info)
        return asdict(error_info)
        
    def handle_video_error(self, output_path: str, exception: Exception) -> Dict[str, Any]:
        """Handle video encoding errors."""
        error_info = ErrorInfo(
            error_type="VideoEncodingError",
            message=str(exception),
            file_path=output_path,
            suggestion=self._get_error_suggestion("VideoEncodingError", str(exception), output_path)
        )
        
        self._add_error(error_info)
        return asdict(error_info)
        
    def handle_image_error(self, file_path: str, exception: Exception) -> Dict[str, Any]:
        """Handle image processing errors."""
        error_info = ErrorInfo(
            error_type="ImageProcessingError",
            message=str(exception),
            file_path=file_path,
            suggestion=self._get_error_suggestion("ImageProcessingError", str(exception), file_path)
        )
        
        self._add_error(error_info)
        return asdict(error_info)
        
    def handle_dicom_error(self, file_path: str, exception: Exception) -> Dict[str, Any]:
        """Handle DICOM processing errors."""
        error_info = ErrorInfo(
            error_type="DicomProcessingError",
            message=str(exception),
            file_path=file_path,
            suggestion=self._get_error_suggestion("DicomProcessingError", str(exception), file_path)
        )
        
        self._add_error(error_info)
        return asdict(error_info)
        
    def handle_permission_error(self, file_path: str, exception: Exception) -> Dict[str, Any]:
        """Handle permission-related errors."""
        error_info = ErrorInfo(
            error_type="PermissionError",
            message=str(exception),
            file_path=file_path,
            suggestion=self._get_error_suggestion("PermissionError", str(exception), file_path)
        )
        
        self._add_error(error_info)
        return asdict(error_info)
        
    def handle_disk_error(self, file_path: str, exception: Exception) -> Dict[str, Any]:
        """Handle disk space and storage errors."""
        error_info = ErrorInfo(
            error_type="DiskSpaceError",
            message=str(exception),
            file_path=file_path,
            suggestion=self._get_error_suggestion("DiskSpaceError", str(exception), file_path)
        )
        
        self._add_error(error_info)
        return asdict(error_info)
        
    def handle_generic_error(self, context: str, exception: Exception, preserve_stack: bool = False) -> Dict[str, Any]:
        """Handle generic errors with optional stack trace preservation."""
        error_info = ErrorInfo(
            error_type=type(exception).__name__,
            message=str(exception),
            context={"operation": context},
            stack_trace=traceback.format_exc() if preserve_stack else None,
            suggestion=self._get_error_suggestion(type(exception).__name__, str(exception))
        )
        
        self._add_error(error_info)
        return asdict(error_info)
        
    def log_warning(self, message: str, context: str = None):
        """Log a warning message."""
        error_info = ErrorInfo(
            error_type="Warning",
            message=message,
            severity="warning",
            context={"context": context} if context else None
        )
        
        self._add_error(error_info)
        
    def log_error(self, message: str, context: str = None):
        """Log an error message."""
        error_info = ErrorInfo(
            error_type="ApplicationError",
            message=message,
            severity="error",
            context={"context": context} if context else None
        )
        
        self._add_error(error_info)
        
    def log_critical(self, message: str, context: str = None):
        """Log a critical error message."""
        error_info = ErrorInfo(
            error_type="CriticalError",
            message=message,
            severity="critical",
            context={"context": context} if context else None
        )
        
        self._add_error(error_info)
        
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all recorded errors."""
        with self._lock:
            all_errors = self.errors + self.warnings + self.critical_errors
            
            error_types = {}
            for error in all_errors:
                error_type = error.error_type
                error_types[error_type] = error_types.get(error_type, 0) + 1
                
            return {
                'total_errors': len(self.errors) + len(self.critical_errors),
                'total_warnings': len(self.warnings),
                'total_critical': len(self.critical_errors),
                'error_types': error_types,
                'last_error_time': max([e.timestamp for e in all_errors]) if all_errors else None
            }
            
    def get_errors_by_type(self, error_type: str) -> List[Dict[str, Any]]:
        """Get all errors of a specific type."""
        with self._lock:
            all_errors = self.errors + self.warnings + self.critical_errors
            filtered_errors = [asdict(error) for error in all_errors if error.error_type == error_type]
            return filtered_errors
            
    def get_warnings(self) -> List[Dict[str, Any]]:
        """Get all warnings."""
        with self._lock:
            return [asdict(warning) for warning in self.warnings]
            
    def get_errors(self) -> List[Dict[str, Any]]:
        """Get all non-critical errors."""
        with self._lock:
            return [asdict(error) for error in self.errors]
            
    def get_critical_errors(self) -> List[Dict[str, Any]]:
        """Get all critical errors."""
        with self._lock:
            return [asdict(error) for error in self.critical_errors]
            
    def generate_error_report(self) -> Dict[str, Any]:
        """Generate a comprehensive error report."""
        summary = self.get_error_summary()
        
        # Group errors by type for detailed analysis
        error_details = {}
        all_errors = self.errors + self.warnings + self.critical_errors
        
        for error in all_errors:
            error_type = error.error_type
            if error_type not in error_details:
                error_details[error_type] = []
            error_details[error_type].append(asdict(error))
            
        # Generate recommendations based on error patterns
        recommendations = self._generate_recommendations(all_errors)
        
        return {
            'generated_at': time.time(),
            'summary': summary,
            'detailed_errors': error_details,
            'warnings': self.get_warnings(),
            'critical_errors': self.get_critical_errors(),
            'recommendations': recommendations
        }
        
    def _generate_recommendations(self, errors: List[ErrorInfo]) -> List[str]:
        """Generate recommendations based on error patterns."""
        recommendations = []
        
        if not errors:
            return recommendations
            
        # Analyze error patterns
        error_counts = {}
        file_errors = 0
        permission_errors = 0
        space_errors = 0
        
        for error in errors:
            error_counts[error.error_type] = error_counts.get(error.error_type, 0) + 1
            
            if "file" in error.message.lower() or "not found" in error.message.lower():
                file_errors += 1
            if "permission" in error.message.lower():
                permission_errors += 1
            if "space" in error.message.lower():
                space_errors += 1
                
        # Generate specific recommendations
        if file_errors > 5:
            recommendations.append("Multiple file access issues detected. Verify input folder path and file permissions.")
            
        if permission_errors > 0:
            recommendations.append("Permission errors detected. Try running as administrator or change output location.")
            
        if space_errors > 0:
            recommendations.append("Disk space issues detected. Free up space or use a different output location.")
            
        if error_counts.get('ImageProcessingError', 0) > 3:
            recommendations.append("Multiple image processing errors. Check image file integrity and formats.")
            
        if error_counts.get('VideoEncodingError', 0) > 0:
            recommendations.append("Video encoding issues detected. Verify codec availability and system resources.")
            
        if len(error_counts) > 5:
            recommendations.append("Multiple error types detected. Consider restarting the application.")
            
        return recommendations
        
    def register_error_callback(self, callback: Callable):
        """Register a callback function for critical errors."""
        self.error_callbacks.append(callback)
        
    def clear_errors(self):
        """Clear all recorded errors and warnings."""
        with self._lock:
            self.errors.clear()
            self.warnings.clear()
            self.critical_errors.clear()
