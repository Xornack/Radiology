# Video from Pictures - Python/PyQt6 Implementation - Technical Specification

## Overview
This specification outlines the requirements and design for a Python-based application, utilizing PyQt6 for the GUI, to convert medical imaging sequences (JPEG, PNG, and DICOM) into video files (MP4).  This implementation serves as a fallback option to the primary browser-based JavaScript application, addressing environments with stricter IT restrictions.  Unlike the Javascript environment, it can run with well-known libraries for image processing.

## Goals
1.  **Primary Goal**: Convert medical imaging sequences (JPEG, PNG, and DICOM formats) into MP4 videos for easier viewing and sharing.
2.  **Compliance Goal**: Less limited than the JS version, mostly run in unrestricted environments.
3.  **User Experience Goal**: Offer a user-friendly interface, similar in functionality to the JavaScript version, requiring minimal technical knowledge.
4.  **Maintainability Goal**: Design the application with clear structure and modularity for future updates and enhancements.

## Requirements

### Functional Requirements

*   **FR001**: Provide a GUI for user interaction.
*   **FR002**: Allow user to select a folder containing image files (JPEG, PNG, and DICOM).
*   **FR003**: Validate the presence of supported image files in the selected folder.
*   **FR004**: Process all supported image files in the selected folder using natural/numerical sorting of filenames.
*   **FR005**: Generate an MP4 video file from the image sequence.
*   **FR006**: Allow the user to specify the output file path and name, with a default option based on the source folder name.
*   **FR007**: Display progress information during video creation, including the current file being processed, percentage complete, and estimated time remaining.
*   **FR008**: Provide clear success/failure messages upon completion, including error details if applicable.
*   **FR009**: Implement error handling for invalid file formats, missing files, and processing failures.
*   **FR010**: Offer user-adjustable frame rate (5-60 FPS).
*   **FR011**: Support an alternative sorting option by file modification date.
*   **FR012**: Skip corrupted or unreadable image files during processing and continue with valid files.
*   **FR013**: Generate a detailed processing report including successful/failed files, processing times, and performance metrics.
*   **FR017**: Strip DICOM header information and extract only image data for processing.
*   **FR014**: Preserve original image data without preprocessing or modification.
*   **FR015**: Auto-generate output filename with a timestamp suffix for uniqueness.
*   **FR016**: Allow user customization of output filename and naming patterns.

### Non-Functional Requirements

*   **NFR001**: Run as a standalone application on Windows.
*   **NFR002**: Minimize external dependencies while maintaining functionality and security.
*   **NFR003**: Process image sequences of typical medical imaging studies (50-500 images) within a reasonable timeframe.
*   **NFR004**: Maintain image quality during video conversion.
*   **NFR005**: Be responsive and provide feedback to the user during potentially long-running operations.
*   **NFR006**: Ensure local security by using trusted dependencies and vulnerability scanning.
*   **NFR007**: Support packaging as standalone executable using Nuitka.

### Technical Requirements

*   **TR001**: Implementation Language: Python 3.12+
*   **TR002**: GUI Framework: PyQt6
*   **TR003**: Image Handling: Libraries capable of reading JPEG, PNG, and DICOM formats (e.g., `Pillow`, `pydicom`). DICOM processing should extract only image data, stripping header information.
*   **TR004**: Video Encoding: Library for creating MP4 videos from images (e.g., `moviepy`, `opencv-python`). Consider performance and licensing implications.
*   **TR005**: Default Video Settings: 15 FPS, original image resolution.
*   **TR006**: Implement natural/numerical sorting for filenames.
*   **TR007**: Provide a fallback sorting option using file modification date.
*   **TR008**: Robust error handling with logging and user-friendly messages.
*   **TR009**: Clear separation of concerns between GUI and core processing logic.
*   **TR010**: Comprehensive progress tracking and reporting mechanisms including processing times and performance metrics.
*   **TR011**: Use QThread for video processing to prevent GUI freezes during video creation.
*   **TR012**: Store user settings in JSON configuration file for persistence and portability.
*   **TR013**: Implement dependency security scanning and use pinned versions for reproducible builds.
*   **TR014**: Design for Nuitka compilation to standalone executable.

## Assumptions

*   **Input Format**: Source images are primarily JPEG, PNG, and DICOM.
*   **File Naming**: Images generally follow a sequential naming convention with numerical components for frame order.
*   **Folder Structure**: All images for a sequence are located within a single folder.
*   **User Environment**: Users possess basic computer literacy for file/folder navigation and application interaction.
*   **Error Handling**: Graceful handling of corrupted files and continuation of processing with valid files.
*   **Output Location**: Users can specify the output location or accept a default within the source folder.
*   **Frame Rate**: A default of 15 FPS is suitable for medical image review, with user adjustments available.
*   **Video Quality**: Reasonable quality for standard viewing, balancing file size and clarity.
*   **Processing Scope**: Single folder processing per operation.
*   **Sorting Logic**: Natural/numerical sorting will correctly order most medical imaging sequences.
*   **Data Integrity**: Extract only image data from DICOM files, stripping metadata to maintain diagnostic accuracy while removing potentially sensitive header information.
*   **Output Naming**: Default naming includes source folder name and a timestamp for uniqueness.
*   **Progress Feedback**: Detailed feedback on current processing stage, percentage complete, ETA, and performance metrics.
*   **Security**: Local processing with trusted dependencies and vulnerability scanning for safe operation.
*   **Distribution**: Application designed for compilation to standalone executable using Nuitka.

## Implementation Plan

### Phase 1: Project Setup and GUI

1.  **Step 1.1**: ✅ **COMPLETED** - Create a new Python project directory (`video_from_pictures/python_version`).
2.  **Step 1.2**: ✅ **COMPLETED** - Set up a virtual environment and install required dependencies: `PyQt6`, `Pillow` (or equivalent for image handling), `pydicom`, and a video encoding library (e.g., `moviepy`).
3.  **Step 1.3**: ✅ **COMPLETED** - Design the main GUI window using PyQt6, including:
    *   Folder selection button/input.
    *   Progress bar.
    *   Status label for displaying messages and progress updates.
    *   Start/Stop processing button.
    *   Settings section (initially hidden, with a button to expand/collapse) for:
        *   Output filename customization.
        *   Frame rate selection.
        *   Sorting method selection.
4.  **Step 1.4**: ✅ **COMPLETED** - Implement basic GUI functionality:
    *   Folder selection dialog.
    *   Button click event handling.
    *   Basic layout management.

### Phase 2: Core Processing Logic

1.  **Step 2.1**: ✅ **COMPLETED** - Implement image file loading and validation:
    *   Function to read JPEG, PNG, and DICOM files from a directory.
    *   DICOM processing to extract image data while stripping header information.
    *   File format validation.
    *   Handling of corrupted or unreadable files (skipping and logging).
2.  **Step 2.2**: ✅ **COMPLETED** - Implement sorting algorithms:
    *   Natural/numerical sorting for filenames.
    *   Sorting by file modification date.
3.  **Step 2.3**: ✅ **COMPLETED** - Integrate video encoding library:
    *   Function to create an MP4 video from a list of image filenames.
    *   Handle video settings (frame rate).
4.  **Step 2.4**: ✅ **COMPLETED** - Implement progress tracking and reporting:
    *   Mechanism to update the progress bar and status label during video creation.
    *   Generate a detailed summary report including processing times and performance metrics.
5.  **Step 2.5**: ✅ **COMPLETED** - Implement error handling and logging:
    *   Comprehensive error handling for file operations, video encoding, etc.
    *   Logging of errors and warnings to a file or console.

### Phase 3: GUI Integration and Testing

1.  **Step 3.1**: Connect GUI elements to core processing functions:
    *   Folder selection triggers image loading and validation.
    *   Start button initiates video creation in a separate QThread (to avoid GUI blocking).
    *   Progress updates from the processing thread are communicated to the GUI via signals.
    *   Completion or error signals are handled to display appropriate messages.
2.  **Step 3.2**: Implement settings functionality:
    *   Load and save user settings (output filename pattern, frame rate, sorting method) using JSON configuration files.
    *   Apply settings to the video creation process.
3.  **Step 3.3**: Thoroughly test the application:
    *   Test with various image sequences (different sizes, formats, and naming conventions).
    *   Verify correct sorting, video creation, progress reporting, and error handling.
    *   Test different video settings and output filename patterns.
    *   Test DICOM header stripping functionality.
4.  **Step 3.4**: Refine the user interface and overall application flow based on testing feedback.

## Dependencies

*   Python 3.12+
*   PyQt6
*   Pillow (for JPEG/PNG)
*   pydicom (for DICOM image extraction)
*   moviepy or opencv-python (for MP4 video creation)
*   pip-audit (for dependency security scanning)

## Security Considerations

*   Use `pip-audit` to scan dependencies for known vulnerabilities
*   Pin specific versions in requirements.txt for reproducible builds
*   Use virtual environments to isolate dependencies
*   Regular updates of dependencies with security patches
*   Local-only processing ensures no data transmission

## Distribution

*   Design application for compilation with Nuitka to create standalone executable
*   Include all necessary dependencies in the compiled package
*   Test standalone executable on clean Windows systems
*   Provide installation instructions for end users

## Success Criteria

1.  The application successfully converts JPEG, PNG, and DICOM image sequences to MP4 videos.
2.  It provides a user-friendly GUI for folder selection, progress tracking, and settings customization.
3.  Error handling is robust, providing informative messages and preventing application crashes.
4.  The application performs adequately in terms of processing speed and resource usage for typical medical image sequences.
5.  The code is well-structured and maintainable, adhering to Python best practices.