"""
Video encoding module for Video from Pictures application.
Handles creating MP4 videos from image sequences using moviepy.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional

try:
    from moviepy.editor import ImageSequenceClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    ImageSequenceClip = None


class VideoEncoder:
    """
    Handles video encoding from image sequences.
    Supports various output formats and quality settings.
    """
    
    # Supported output formats
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv'}
    
    # Quality presets
    QUALITY_PRESETS = {
        'low': {
            'bitrate': '2000k',
            'codec': 'libx264'
        },
        'medium': {
            'bitrate': '5000k', 
            'codec': 'libx264'
        },
        'high': {
            'bitrate': '8000k',
            'codec': 'libx264'
        }
    }
    
    def __init__(self):
        """Initialize the VideoEncoder."""
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        if not MOVIEPY_AVAILABLE:
            self.logger.warning("moviepy is not available. Video encoding will not work.")
    
    def _setup_logging(self):
        """Set up logging configuration."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def is_supported_output_format(self, file_path: str) -> bool:
        """
        Check if output format is supported.
        
        Args:
            file_path: Output file path or extension
            
        Returns:
            True if format is supported, False otherwise
        """
        if file_path.startswith('.'):
            extension = file_path.lower()
        else:
            extension = Path(file_path).suffix.lower()
            
        return extension in self.SUPPORTED_FORMATS
    
    def get_quality_settings(self, quality: str) -> Dict[str, str]:
        """
        Get quality settings for video encoding.
        
        Args:
            quality: Quality preset name ('low', 'medium', 'high')
            
        Returns:
            Dictionary of quality settings
        """
        return self.QUALITY_PRESETS.get(quality, self.QUALITY_PRESETS['medium'])
    
    def create_video(self,
                    image_files: List[Path],
                    output_path: Path,
                    fps: int = 15,
                    codec: str = 'libx264',
                    quality: str = 'medium',
                    progress_callback: Optional[Callable[[float, str], None]] = None) -> Dict[str, Any]:
        """
        Create a video from a sequence of images.
        
        Args:
            image_files: List of image file paths in sequence order
            output_path: Output video file path
            fps: Frames per second
            codec: Video codec to use
            quality: Quality preset ('low', 'medium', 'high')
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with success status and metadata
        """
        # Check moviepy availability dynamically for testing
        moviepy_available = MOVIEPY_AVAILABLE
        try:
            # Allow override for testing
            import video_encoder
            if hasattr(video_encoder, 'MOVIEPY_AVAILABLE'):
                moviepy_available = video_encoder.MOVIEPY_AVAILABLE
        except:
            pass
            
        if not moviepy_available:
            return {
                'success': False,
                'error': 'moviepy is not available. Please install it: pip install moviepy'
            }
        
        # Validate inputs
        if not image_files:
            return {
                'success': False,
                'error': 'No images provided for video creation'
            }
        
        if not isinstance(output_path, Path):
            output_path = Path(output_path)
            
        # Check output format
        if not self.is_supported_output_format(str(output_path)):
            return {
                'success': False,
                'error': f'Unsupported output format: {output_path.suffix}'
            }
        
        # Create output directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Convert Path objects to strings for moviepy
            image_paths = [str(img) for img in image_files]
            
            # Validate that image files exist
            missing_files = [img for img in image_files if not img.exists()]
            if missing_files:
                return {
                    'success': False,
                    'error': f'Missing image files: {[str(f) for f in missing_files[:5]]}'
                }
            
            # Progress callback wrapper
            def progress_wrapper(progress_callback, total_frames):
                def callback(get_frame, t):
                    if progress_callback:
                        percentage = (t * fps / total_frames) * 100
                        progress_callback(min(percentage, 100), f"Encoding frame at {t:.2f}s")
                return callback
            
            # Update progress
            if progress_callback:
                progress_callback(0, "Initializing video creation...")
            
            self.logger.info(f"Creating video from {len(image_files)} images")
            
            # Create video clip
            clip = ImageSequenceClip(image_paths, fps=fps)
            
            if progress_callback:
                progress_callback(25, "Video clip created, starting encoding...")
            
            # Get quality settings
            quality_settings = self.get_quality_settings(quality)
            
            # Prepare encoding parameters
            encode_params = {
                'fps': fps,
                'codec': codec,
                'audio': False
            }
            
            # Add quality-specific parameters
            if quality in self.QUALITY_PRESETS:
                encode_params['bitrate'] = quality_settings['bitrate']
                if codec == 'auto':
                    encode_params['codec'] = quality_settings['codec']
            
            if progress_callback:
                progress_callback(50, "Starting video encoding...")
            
            # Write video file
            clip.write_videofile(
                str(output_path),
                **encode_params,
                verbose=False,
                logger=None  # Suppress moviepy's verbose output
            )
            
            if progress_callback:
                progress_callback(100, "Video encoding completed successfully")
            
            # Get video metadata
            video_info = {
                'duration': clip.duration,
                'fps': fps,
                'size': (clip.w, clip.h) if hasattr(clip, 'w') else None,
                'total_frames': len(image_files),
                'codec': codec,
                'quality': quality
            }
            
            # Clean up
            clip.close()
            
            self.logger.info(f"Video created successfully: {output_path}")
            
            return {
                'success': True,
                'output_path': output_path,
                'video_info': video_info,
                'message': f'Video created with {len(image_files)} frames at {fps} FPS'
            }
            
        except Exception as e:
            error_msg = f"Error creating video: {str(e)}"
            self.logger.error(error_msg)
            
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            
            return {
                'success': False,
                'error': error_msg,
                'exception_type': type(e).__name__
            }
    
    def estimate_output_size(self, 
                           image_files: List[Path], 
                           fps: int = 15, 
                           quality: str = 'medium') -> Dict[str, Any]:
        """
        Estimate the output video file size.
        
        Args:
            image_files: List of image file paths
            fps: Frames per second
            quality: Quality preset
            
        Returns:
            Dictionary with size estimation information
        """
        if not image_files:
            return {'estimated_size_mb': 0, 'duration_seconds': 0}
        
        try:
            # Calculate duration
            duration_seconds = len(image_files) / fps
            
            # Get quality settings
            quality_settings = self.get_quality_settings(quality)
            bitrate_str = quality_settings.get('bitrate', '5000k')
            
            # Extract bitrate value (remove 'k' suffix)
            bitrate_kbps = int(bitrate_str.replace('k', ''))
            
            # Estimate size: (bitrate * duration) / 8 to convert bits to bytes
            estimated_size_bytes = (bitrate_kbps * 1000 * duration_seconds) / 8
            estimated_size_mb = estimated_size_bytes / (1024 * 1024)
            
            return {
                'estimated_size_mb': round(estimated_size_mb, 2),
                'estimated_size_bytes': int(estimated_size_bytes),
                'duration_seconds': round(duration_seconds, 2),
                'fps': fps,
                'total_frames': len(image_files),
                'quality': quality,
                'bitrate_kbps': bitrate_kbps
            }
            
        except Exception as e:
            self.logger.warning(f"Error estimating video size: {e}")
            return {
                'estimated_size_mb': 0,
                'duration_seconds': len(image_files) / fps if image_files else 0,
                'error': str(e)
            }
    
    def get_supported_codecs(self) -> List[str]:
        """
        Get list of supported video codecs.
        
        Returns:
            List of supported codec names
        """
        # Common codecs that are typically available
        return ['libx264', 'libx265', 'mpeg4', 'libvpx', 'libvpx-vp9']
    
    def validate_settings(self, 
                         fps: int, 
                         quality: str, 
                         codec: str) -> Dict[str, Any]:
        """
        Validate video encoding settings.
        
        Args:
            fps: Frames per second
            quality: Quality preset
            codec: Video codec
            
        Returns:
            Validation result dictionary
        """
        errors = []
        warnings = []
        
        # Validate FPS
        if fps < 1 or fps > 120:
            errors.append(f"FPS must be between 1 and 120, got {fps}")
        elif fps < 5:
            warnings.append(f"Very low FPS ({fps}) may result in choppy video")
        elif fps > 60:
            warnings.append(f"High FPS ({fps}) may result in large file sizes")
        
        # Validate quality
        if quality not in self.QUALITY_PRESETS:
            errors.append(f"Unknown quality preset '{quality}'. Available: {list(self.QUALITY_PRESETS.keys())}")
        
        # Validate codec
        supported_codecs = self.get_supported_codecs()
        if codec not in supported_codecs + ['auto']:
            warnings.append(f"Codec '{codec}' may not be supported. Recommended: {supported_codecs}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
