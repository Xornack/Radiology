"""
Test for video encoding functionality.
Tests video creation from image sequences with various settings.
"""

import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

class TestVideoEncoder(unittest.TestCase):
    """Test video encoding functionality."""
    
    def setUp(self):
        """Set up test environment with temporary directories and files."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create some test image files
        for i in range(5):
            test_file = self.test_path / f"image_{i:03d}.jpg"
            test_file.touch()
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.test_dir)
        
    def test_video_encoder_imports(self):
        """Test that video encoder module can be imported."""
        try:
            from video_encoder import VideoEncoder
            self.assertTrue(True, "VideoEncoder should be importable")
        except ImportError as e:
            self.fail(f"VideoEncoder import failed: {e}")
            
    def test_video_encoder_instantiation(self):
        """Test that VideoEncoder can be instantiated."""
        from video_encoder import VideoEncoder
        
        encoder = VideoEncoder()
        self.assertIsNotNone(encoder)
        
    def test_video_creation_basic(self):
        """Test basic video creation from image list."""
        from video_encoder import VideoEncoder
        
        encoder = VideoEncoder()
        
        # Create list of test image files
        image_files = [
            self.test_path / f"image_{i:03d}.jpg" 
            for i in range(5)
        ]
        
        output_path = self.test_path / "output.mp4"
        
        # Mock moviepy components and availability
        with patch('video_encoder.MOVIEPY_AVAILABLE', True), \
             patch('video_encoder.ImageSequenceClip') as mock_clip_class:
            
            mock_clip = MagicMock()
            mock_clip.duration = 0.33  # 5 frames at 15 fps
            mock_clip.w = 640
            mock_clip.h = 480
            mock_clip_class.return_value = mock_clip
            
            result = encoder.create_video(
                image_files=image_files,
                output_path=output_path,
                fps=15
            )
            
            # Should call ImageSequenceClip with string paths
            mock_clip_class.assert_called_once()
            args, kwargs = mock_clip_class.call_args
            
            # Check that image paths were converted to strings
            self.assertEqual(len(args[0]), 5)  # 5 image files
            
            # Should call write_videofile with at least the required parameters
            mock_clip.write_videofile.assert_called_once()
            call_args = mock_clip.write_videofile.call_args
            
            # Check the positional and keyword arguments
            self.assertEqual(call_args[0][0], str(output_path))
            self.assertEqual(call_args[1]['fps'], 15)
            self.assertEqual(call_args[1]['codec'], 'libx264')
            self.assertEqual(call_args[1]['audio'], False)
            self.assertEqual(call_args[1]['bitrate'], '5000k')
            
            self.assertTrue(result['success'])
            
    def test_video_settings_application(self):
        """Test that video settings are properly applied."""
        from video_encoder import VideoEncoder
        
        encoder = VideoEncoder()
        
        # Test that quality settings work
        quality_settings = encoder.get_quality_settings('high')
        self.assertEqual(quality_settings['bitrate'], '8000k')
        
        # Test that validation works
        validation = encoder.validate_settings(30, 'high', 'libx265')
        self.assertTrue(validation['valid'])
        
    def test_progress_callback(self):
        """Test progress callback functionality."""
        from video_encoder import VideoEncoder
        
        encoder = VideoEncoder()
        
        # Test that the method accepts a progress callback without error
        # (detailed testing would require actual moviepy functionality)
        progress_calls = []
        def progress_callback(percentage, message):
            progress_calls.append((percentage, message))
        
        image_files = [self.test_path / "test.jpg"]
        output_path = self.test_path / "test.mp4"
        
        # Without moviepy, this should return an error but not crash
        result = encoder.create_video(
            image_files=image_files,
            output_path=output_path,
            progress_callback=progress_callback
        )
        
        # Should handle the callback gracefully
        self.assertFalse(result['success'])  # Expected since moviepy not available
            
    def test_error_handling(self):
        """Test error handling during video creation."""
        from video_encoder import VideoEncoder
        
        encoder = VideoEncoder()
        
        # Test with non-existent files
        image_files = [self.test_path / "nonexistent.jpg"]
        output_path = self.test_path / "test.mp4"
        
        result = encoder.create_video(
            image_files=image_files,
            output_path=output_path
        )
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        
    def test_empty_image_list(self):
        """Test handling of empty image list."""
        from video_encoder import VideoEncoder
        
        encoder = VideoEncoder()
        
        # Test with moviepy available
        with patch('video_encoder.MOVIEPY_AVAILABLE', True):
            result = encoder.create_video(
                image_files=[],
                output_path=self.test_path / "test.mp4"
            )
            
            self.assertFalse(result['success'])
            self.assertIn('No images provided', str(result.get('error', '')))
        
    def test_output_directory_creation(self):
        """Test automatic creation of output directory."""
        from video_encoder import VideoEncoder
        
        encoder = VideoEncoder()
        
        # Create output path in non-existent directory
        output_dir = self.test_path / "new_dir"
        output_path = output_dir / "video.mp4"
        
        image_files = [self.test_path / f"image_{i:03d}.jpg" for i in range(2)]
        
        # Mock moviepy components and availability
        with patch('video_encoder.MOVIEPY_AVAILABLE', True), \
             patch('video_encoder.ImageSequenceClip') as mock_clip_class:
            
            mock_clip = MagicMock()
            mock_clip.duration = 0.133  # 2 frames at 15 fps
            mock_clip.w = 640
            mock_clip.h = 480
            mock_clip_class.return_value = mock_clip
            
            result = encoder.create_video(
                image_files=image_files,
                output_path=output_path
            )
            
            # Should create the directory
            self.assertTrue(output_dir.exists())
            self.assertTrue(result['success'])
            
    def test_video_quality_presets(self):
        """Test video quality preset functionality."""
        from video_encoder import VideoEncoder
        
        encoder = VideoEncoder()
        
        # Test quality presets
        quality_settings = encoder.get_quality_settings('high')
        self.assertIn('bitrate', quality_settings)
        
        quality_settings = encoder.get_quality_settings('medium')
        self.assertIn('bitrate', quality_settings)
        
        quality_settings = encoder.get_quality_settings('low')
        self.assertIn('bitrate', quality_settings)
        
    def test_supported_formats_validation(self):
        """Test validation of supported output formats."""
        from video_encoder import VideoEncoder
        
        encoder = VideoEncoder()
        
        # Test supported format
        self.assertTrue(encoder.is_supported_output_format('.mp4'))
        self.assertTrue(encoder.is_supported_output_format('.avi'))
        
        # Test unsupported format
        self.assertFalse(encoder.is_supported_output_format('.txt'))


if __name__ == '__main__':
    unittest.main()
