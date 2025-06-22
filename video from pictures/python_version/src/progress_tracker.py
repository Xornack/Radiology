"""
Progress tracking and reporting functionality for video creation operations.

This module provides comprehensive progress tracking including:
- Real-time progress updates with callbacks
- Time estimation and performance metrics
- Error and warning collection
- Detailed operation reports
- Progress state persistence
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class StepTiming:
    """Information about individual step timing."""
    step_number: int
    message: str
    start_time: float
    end_time: float
    duration: float


@dataclass
class ErrorInfo:
    """Information about an error that occurred."""
    message: str
    type: str
    timestamp: float
    step_number: Optional[int] = None


@dataclass
class WarningInfo:
    """Information about a warning that occurred."""
    message: str
    timestamp: float
    step_number: Optional[int] = None


class ProgressTracker:
    """
    Comprehensive progress tracker for video creation operations.
    
    Provides real-time progress updates, time estimation, performance metrics,
    error tracking, and detailed reporting capabilities.
    """
    
    def __init__(self, operation_id: Optional[str] = None):
        """
        Initialize the progress tracker.
        
        Args:
            operation_id: Optional unique identifier for this operation
        """
        self.operation_id = operation_id or f"op_{int(time.time())}"
        self.reset()
        
    def reset(self):
        """Reset all tracking data."""
        self.total_steps = 0
        self.current_step = 0
        self.operation_name = ""
        self.start_time = None
        self.end_time = None
        self.last_update_time = None
        self.step_start_time = None  # Track when current step started
        self.status = "initialized"  # initialized, running, completed, failed
        
        self.step_timings: List[StepTiming] = []
        self.performance_metrics: Dict[str, Any] = {}
        self.errors: List[ErrorInfo] = []
        self.warnings: List[WarningInfo] = []
        self.callbacks: List[Callable] = []
        
        self.current_message = ""
        
    def initialize(self, total_steps: int, operation_name: str):
        """
        Initialize tracking for a new operation.
        
        Args:
            total_steps: Total number of steps in the operation
            operation_name: Human-readable name for the operation
        """
        self.total_steps = total_steps
        self.operation_name = operation_name
        self.current_step = 0
        self.status = "initialized"
        
    def start_timing(self):
        """Start timing the operation."""
        self.start_time = time.time()
        self.status = "running"
        self.step_start_time = self.start_time  # First step starts now
        
    def update_progress(self, step: int, message: str):
        """
        Update progress to a specific step.
        
        Args:
            step: Current step number (1-based)
            message: Description of current step
        """
        current_time = time.time()
        
        # Initialize step_start_time if not set (for cases where start_timing() wasn't called)
        if not hasattr(self, 'step_start_time') or self.step_start_time is None:
            self.step_start_time = current_time
        
        # If this is not the first step, record timing for the previous step
        if self.current_step > 0:
            # Record timing for the step we just completed
            timing = StepTiming(
                step_number=self.current_step,
                message=self.current_message,
                start_time=self.step_start_time,
                end_time=current_time,
                duration=current_time - self.step_start_time
            )
            self.step_timings.append(timing)
            
            # Next step starts now
            self.step_start_time = current_time
        
        # Update current step info   
        self.current_step = step
        self.current_message = message
        self.last_update_time = current_time
        
        # Calculate percentage and ETA
        percentage = (step / self.total_steps) * 100 if self.total_steps > 0 else 0
        eta = self.get_estimated_time_remaining()
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback(percentage, message, eta)
            except Exception as e:
                # Don't let callback errors break progress tracking
                self.add_error(f"Progress callback error: {e}", "CallbackError")
                
    def complete_operation(self):
        """Mark the operation as completed."""
        current_time = time.time()
        
        # Record final step timing if needed
        if self.current_step > 0 and hasattr(self, 'step_start_time') and self.step_start_time is not None:
            timing = StepTiming(
                step_number=self.current_step,
                message=self.current_message,
                start_time=self.step_start_time,
                end_time=current_time,
                duration=current_time - self.step_start_time
            )
            self.step_timings.append(timing)
            
        self.end_time = current_time
        self.status = "completed"
        
    def fail_operation(self, reason: str):
        """Mark the operation as failed."""
        self.end_time = time.time()
        self.status = "failed"
        self.add_error(f"Operation failed: {reason}", "OperationFailure")
        
    def get_current_progress(self) -> float:
        """Get current progress as percentage (0-100)."""
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100
        
    def get_total_steps(self) -> int:
        """Get total number of steps."""
        return self.total_steps
        
    def get_operation_name(self) -> str:
        """Get operation name."""
        return self.operation_name
        
    def get_estimated_time_remaining(self) -> Optional[float]:
        """
        Calculate estimated time remaining in seconds.
        
        Returns:
            Estimated seconds remaining, or None if cannot be calculated
        """
        if (self.start_time is None or self.current_step == 0 or 
            self.total_steps == 0 or self.current_step >= self.total_steps):
            return None
            
        current_time = self.last_update_time or time.time()
        elapsed_time = current_time - self.start_time
        progress_ratio = self.current_step / self.total_steps
        
        if progress_ratio <= 0:
            return None
            
        estimated_total_time = elapsed_time / progress_ratio
        remaining_time = estimated_total_time - elapsed_time
        
        return max(0, remaining_time)
        
    def add_performance_metric(self, name: str, value: Any):
        """
        Add a performance metric.
        
        Args:
            name: Metric name
            value: Metric value
        """
        self.performance_metrics[name] = value
        
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get all performance metrics."""
        return self.performance_metrics.copy()
        
    def add_error(self, message: str, error_type: str):
        """
        Add an error to the tracking.
        
        Args:
            message: Error message
            error_type: Type/category of error
        """
        error = ErrorInfo(
            message=message,
            type=error_type,
            timestamp=time.time(),
            step_number=self.current_step if self.current_step > 0 else None
        )
        self.errors.append(error)
        
    def add_warning(self, message: str):
        """
        Add a warning to the tracking.
        
        Args:
            message: Warning message
        """
        warning = WarningInfo(
            message=message,
            timestamp=time.time(),
            step_number=self.current_step if self.current_step > 0 else None
        )
        self.warnings.append(warning)
        
    def get_errors(self) -> List[Dict[str, Any]]:
        """Get all errors as dictionaries."""
        return [asdict(error) for error in self.errors]
        
    def get_warnings(self) -> List[Dict[str, Any]]:
        """Get all warnings as dictionaries."""
        return [asdict(warning) for warning in self.warnings]
        
    def register_callback(self, callback: Callable):
        """
        Register a progress callback function.
        
        Args:
            callback: Function that takes (percentage, message, eta) parameters
        """
        self.callbacks.append(callback)
        
    def unregister_callback(self, callback: Callable):
        """
        Unregister a progress callback function.
        
        Args:
            callback: Function to remove
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            
    def get_step_timings(self) -> List[Dict[str, Any]]:
        """Get timing information for all completed steps."""
        return [asdict(timing) for timing in self.step_timings]
        
    def generate_detailed_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive report of the operation.
        
        Returns:
            Dictionary containing detailed operation information
        """
        total_time = None
        if self.start_time is not None:
            end_time = self.end_time or time.time()
            total_time = end_time - self.start_time
            
        # Calculate average step time
        avg_step_time = None
        if self.step_timings:
            total_step_time = sum(timing.duration for timing in self.step_timings)
            avg_step_time = total_step_time / len(self.step_timings)
            
        report = {
            'operation_summary': {
                'id': self.operation_id,
                'name': self.operation_name,
                'status': self.status,
                'progress_percentage': self.get_current_progress(),
                'steps_completed': self.current_step,
                'total_steps': self.total_steps
            },
            'timing_info': {
                'start_time': self.start_time,
                'end_time': self.end_time,
                'total_duration_seconds': total_time,
                'average_step_duration_seconds': avg_step_time,
                'step_count': len(self.step_timings)
            },
            'performance_metrics': self.performance_metrics.copy(),
            'errors_and_warnings': {
                'error_count': len(self.errors),
                'warning_count': len(self.warnings),
                'errors': self.get_errors(),
                'warnings': self.get_warnings()
            },
            'step_details': self.get_step_timings(),
            'generated_at': time.time()
        }
        
        return report
        
    def save_state(self, file_path: Union[str, Path]):
        """
        Save current tracking state to a file.
        
        Args:
            file_path: Path where to save the state
        """
        file_path = Path(file_path)
        
        state = {
            'operation_id': self.operation_id,
            'total_steps': self.total_steps,
            'current_step': self.current_step,
            'operation_name': self.operation_name,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'last_update_time': self.last_update_time,
            'status': self.status,
            'current_message': self.current_message,
            'step_timings': [asdict(timing) for timing in self.step_timings],
            'performance_metrics': self.performance_metrics,
            'errors': [asdict(error) for error in self.errors],
            'warnings': [asdict(warning) for warning in self.warnings],
            'saved_at': time.time()
        }
        
        with open(file_path, 'w') as f:
            json.dump(state, f, indent=2)
            
    def load_state(self, file_path: Union[str, Path]):
        """
        Load tracking state from a file.
        
        Args:
            file_path: Path to load the state from
        """
        file_path = Path(file_path)
        
        with open(file_path, 'r') as f:
            state = json.load(f)
            
        self.operation_id = state['operation_id']
        self.total_steps = state['total_steps']
        self.current_step = state['current_step']
        self.operation_name = state['operation_name']
        self.start_time = state['start_time']
        self.end_time = state['end_time']
        self.last_update_time = state['last_update_time']
        self.status = state['status']
        self.current_message = state['current_message']
        
        # Reconstruct dataclass objects
        self.step_timings = [StepTiming(**timing) for timing in state['step_timings']]
        self.performance_metrics = state['performance_metrics']
        self.errors = [ErrorInfo(**error) for error in state['errors']]
        self.warnings = [WarningInfo(**warning) for warning in state['warnings']]
        
        # Note: callbacks are not persisted
        self.callbacks = []
