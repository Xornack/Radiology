# Video from Pictures - Medical Image to Video Converter

A PyQt6-based application for converting sequences of medical images (including DICOM files) into video format, designed specifically for radiology workflows.

## Features

- **Medical Image Support**: Handles DICOM (.dcm) files as well as standard image formats (JPEG, PNG, BMP, TIFF)
- **Intelligent Sorting**: Multiple sorting options including natural sorting (handles numeric sequences correctly), alphabetical, and modification date
- **Batch Processing**: Process entire folders of images efficiently
- **Progress Tracking**: Real-time progress updates with detailed logging
- **Error Handling**: Comprehensive error reporting with selectable text in error dialogs
- **Flexible Output**: Saves videos to the parent directory of the image folder for better organization
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Requirements

- Python 3.8 or higher
- Dependencies listed in `requirements.txt`:
  - PyQt6 >= 6.6.0
  - Pillow >= 10.0.0
  - pydicom >= 2.4.0
  - moviepy >= 1.0.3 (supports both 1.x and 2.x versions)
  - numpy >= 1.24.0

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd video-from-pictures/python_version
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:
```bash
python src/main.py
```

2. Click "Select Folder" to choose a directory containing your medical images
3. Configure settings:
   - **Frame Rate (FPS)**: Adjust the speed of the video (default: 15 fps)
   - **Video Quality**: Choose between Low, Medium, or High quality
   - **Output Format**: Select MP4, AVI, MOV, or MKV
   - **Sorting Method**: Choose how images should be ordered
   - **Add Timestamp**: Option to include timestamp in filename

4. Click "Start Processing" to create the video

## Output Location

Videos are saved to the **parent directory** of the selected image folder with the folder name as the filename. For example:
- Images in: `C:\Medical\Patient123\Series1\`
- Video saved to: `C:\Medical\Patient123\Series1_video_20250701_235241.mp4`

## Sorting Methods

- **Natural Sorting**: Intelligently sorts filenames with numbers (e.g., img1, img2, img10 instead of img1, img10, img2)
- **Alphabetical**: Standard alphabetical sorting
- **Modification Date**: Sorts by file modification timestamp

## Technical Details

### Architecture

The application uses a modular architecture with the following components:

- **MainWindow**: PyQt6 GUI interface
- **VideoProcessingWorker**: QThread-based worker for non-blocking video processing
- **ImageLoader**: Handles image loading and validation, including DICOM support
- **VideoEncoder**: Creates videos using MoviePy with multiple fallback methods
- **ProgressTracker**: Tracks processing progress and timing
- **ErrorLogger**: Comprehensive error logging and reporting
- **SettingsManager**: Persists user preferences

### MoviePy 2.x Compatibility

The application includes robust compatibility for both MoviePy 1.x and 2.x versions:
- Automatic detection of MoviePy version
- Multiple fallback methods for video creation
- Pre-processing of images as numpy arrays for better compatibility

### Error Handling

- All error messages are displayed in dialogs with **selectable text** for easy copying
- Detailed error logging for troubleshooting
- Graceful handling of various image format issues

## Development

### Running Tests

```bash
pytest tests/
```

### Code Structure

```
src/
├── main.py                 # Application entry point
├── main_window.py         # GUI interface
├── video_processing_worker.py  # Background processing thread
├── image_loader.py        # Image loading and DICOM support
├── video_encoder.py       # Video creation with MoviePy
├── progress_tracker.py    # Progress monitoring
├── error_logger.py        # Error handling
└── settings_manager.py    # User preferences
```

## Troubleshooting

### Common Issues

1. **"MoviePy not found" error**:
   - Ensure MoviePy is installed: `pip install moviepy`
   - The application supports both MoviePy 1.x and 2.x

2. **"tuple index out of range" error**:
   - This typically occurs with certain image formats
   - The application now pre-processes images to avoid this issue

3. **Video not playing**:
   - Ensure you have proper video codecs installed
   - Try different output formats (MP4 is most compatible)

### Debug Mode

For detailed logging, run with debug flag:
```bash
python src/main.py --debug
```

## License

[Your license information here]

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request with a clear description of changes

## Changelog

### Recent Updates
- Fixed MoviePy 2.x compatibility issues
- Added support for saving videos to parent directory
- Implemented selectable text in error dialogs
- Fixed progress tracking method calls
- Added alphabetical sorting option
- Improved error handling for medical image formats
- Pre-process images as numpy arrays for better compatibility
