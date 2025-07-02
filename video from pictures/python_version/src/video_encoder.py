"""
Video encoding module for Video from Pictures application.
Handles creating MP4 videos from image sequences using moviepy.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional

try:
    # Try new MoviePy 2.0+ import structure first
    from moviepy import ImageSequenceClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    try:
        # Fallback to old import structure for older versions
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
                'error': 'MoviePy is not available. Please install it: pip install moviepy\n'
                        'Note: This application supports both MoviePy 1.x and 2.x versions.'
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
            
            # Validate that image files exist and are readable
            missing_files = []
            invalid_files = []
            
            for i, img_path in enumerate(image_files):
                if not img_path.exists():
                    missing_files.append(str(img_path))
                else:
                    # Try to verify it's a valid image file
                    try:
                        # Basic size check - image files should be larger than 0 bytes
                        if img_path.stat().st_size == 0:
                            invalid_files.append(str(img_path))
                    except Exception:
                        invalid_files.append(str(img_path))
            
            if missing_files:
                return {
                    'success': False,
                    'error': f'Missing image files: {missing_files[:5]}'
                }
                
            if invalid_files:
                return {
                    'success': False,
                    'error': f'Invalid or empty image files: {invalid_files[:5]}'
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
            self.logger.debug(f"Sample image paths: {[str(img) for img in image_files[:3]]}")
            
            # Create video clip with error handling
            try:
                # First, try to load just one image to check compatibility
                if progress_callback:
                    progress_callback(10, "Checking image compatibility...")
                
                # Pre-load images as numpy arrays for better compatibility
                from PIL import Image
                import numpy as np
                
                self.logger.info("Pre-loading images for better compatibility...")
                loaded_images = []
                
                for i, img_path in enumerate(image_files):
                    try:
                        img = Image.open(img_path)
                        
                        # Convert to RGB if necessary (handles grayscale, RGBA, etc.)
                        if img.mode != 'RGB':
                            self.logger.debug(f"Converting {img_path.name} from {img.mode} to RGB")
                            img = img.convert('RGB')
                        
                        # Convert to numpy array
                        img_array = np.array(img)
                        loaded_images.append(img_array)
                        img.close()
                        
                        if progress_callback and i % 10 == 0:
                            progress_callback(10 + (i / len(image_files)) * 10, f"Loading image {i+1}/{len(image_files)}")
                            
                    except Exception as e:
                        self.logger.error(f"Error loading image {img_path}: {e}")
                        return {
                            'success': False,
                            'error': f'Failed to load image {img_path.name}: {str(e)}'
                        }
                
                self.logger.info(f"Successfully loaded {len(loaded_images)} images as numpy arrays")
                
                # MoviePy 2.x approach with numpy arrays
                self.logger.info(f"Creating ImageSequenceClip with {len(loaded_images)} preprocessed images at {fps} fps")
                
                # Method 1: Try MoviePy 2.x style with durations parameter and numpy arrays
                try:
                    duration_per_frame = 1.0 / fps
                    durations = [duration_per_frame] * len(loaded_images)
                    self.logger.debug(f"Trying durations method with numpy arrays: {len(durations)} frames, {duration_per_frame:.4f}s each")
                    clip = ImageSequenceClip(loaded_images, durations=durations)
                    self.logger.info("Successfully created clip with durations parameter and numpy arrays")
                except Exception as e1:
                    self.logger.debug(f"Method 1 (durations with arrays) failed: {e1}")
                    
                    # Method 2: Try with fps parameter and numpy arrays
                    try:
                        self.logger.debug("Trying fps parameter method with numpy arrays")
                        clip = ImageSequenceClip(loaded_images, fps=fps)
                        self.logger.info("Successfully created clip with fps parameter and numpy arrays")
                    except Exception as e2:
                        self.logger.debug(f"Method 2 (fps with arrays) failed: {e2}")
                        
                        # Method 3: Try with file paths as fallback
                        try:
                            self.logger.debug("Falling back to file paths method")
                            duration_per_frame = 1.0 / fps
                            durations = [duration_per_frame] * len(image_paths)
                            clip = ImageSequenceClip(image_paths, durations=durations)
                            self.logger.info("Successfully created clip with file paths and durations")
                        except Exception as e3:
                            self.logger.debug(f"Method 3 (paths with durations) failed: {e3}")
                            
                            # Method 4: Create from sequence manually
                            try:
                                self.logger.debug("Trying manual sequence creation")
                                # Create clips from individual images and concatenate
                                from moviepy import CompositeVideoClip, ImageClip
                                
                                clips = []
                                for img_array in loaded_images:
                                    img_clip = ImageClip(img_array, duration=duration_per_frame)
                                    clips.append(img_clip)
                                
                                clip = CompositeVideoClip(clips).set_duration(len(loaded_images) / fps)
                                self.logger.info("Successfully created clip using CompositeVideoClip")
                            except Exception as e4:
                                # All methods failed
                                raise Exception(f"All ImageSequenceClip creation methods failed. "
                                              f"Arrays+durations: {e1}, Arrays+fps: {e2}, "
                                              f"Paths+durations: {e3}, Composite: {e4}")
                
            except Exception as e:
                self.logger.error(f"Failed to create ImageSequenceClip: {e}")
                return {
                    'success': False,
                    'error': f'Failed to create video clip: {str(e)}. This may be due to incompatible image formats or MoviePy version issues.',
                    'technical_details': str(e)
                }
            
            if progress_callback:
                progress_callback(25, "Video clip created, starting encoding...")
            
            # Get quality settings
            quality_settings = self.get_quality_settings(quality)
            
            if progress_callback:
                progress_callback(50, "Starting video encoding...")
            
            # Write video file
            try:
                # Try with full parameters including bitrate
                write_params = {
                    'fps': fps,
                    'codec': codec,
                    'audio': False,
                    'verbose': False,
                    'logger': None
                }
                
                # Add bitrate if quality preset is used
                if quality in self.QUALITY_PRESETS:
                    write_params['bitrate'] = quality_settings['bitrate']
                    if codec == 'auto':
                        write_params['codec'] = quality_settings['codec']
                
                clip.write_videofile(str(output_path), **write_params)
                
            except TypeError as te:
                # Handle MoviePy version differences in write_videofile parameters
                self.logger.warning(f"write_videofile parameter error: {te}, trying with basic parameters")
                try:
                    clip.write_videofile(
                        str(output_path),
                        fps=fps,
                        codec=codec,
                        audio=False,
                        verbose=False
                    )
                except Exception as e2:
                    # Final fallback with minimal parameters
                    self.logger.warning(f"Basic parameters failed: {e2}, trying minimal parameters")
                    clip.write_videofile(str(output_path), fps=fps)
            
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
