# Video from Pictures - Technical Specification

## Overview
A locally-running application that converts a### Phase 3: Output and Validation
1. **Step 3.1**: Add MP4 file save functionality ✅ **COMPLETED**
   - Enhanced file saving with multiple save methods (File System Access API, directory selection, download)
   - User-configurable save options and preferences
   - Automatic unique filename generation with timestamps
   - Comprehensive error handling and fallback mechanisms
   - Save method selection UI for user choice
   - Integration with existing progress tracking and error handling systems
2. **Step 3.2**: Implement automatic video playback/testing
3. **Step 3.3**: Add success/failure reporting  
4. **Step 3.4**: Implement proper error codes and messaging

### Phase 4: User Experience Enhancementce of JPEG medical images (CT, MRI, SPECT, PET, or time-resolved nuclear medicine planar images) into a single MP4 video file. The application prioritizes browser-based implementation to work within restrictive IT environments common in medical facilities.

## Goals
1. **Primary Goal**: Convert medical imaging sequences (JPEG format) into MP4 videos for easier viewing and sharing
2. **Compliance Goal**: Work within IT-restricted environments that limit executable installations but allow browser-based applications
3. **Validation Goal**: Ensure output quality by automatically playing/testing the generated MP4
4. **User Experience Goal**: Provide simple, intuitive interface requiring minimal technical knowledge

## Requirements

### Functional Requirements
1. **FR001**: Accept user input for source folder path containing JPEG images
2. **FR002**: Validate presence of JPEG files in specified folder
3. **FR003**: Process ALL JPEG images found in the selected folder using natural/numerical sorting
4. **FR004**: Generate MP4 video file from image sequence
5. **FR005**: Save MP4 file to user-specified or default location
6. **FR006**: Automatically test/play generated MP4 to verify successful creation
7. **FR007**: Display error messages for missing files, invalid formats, or processing failures
8. **FR008**: Exit with appropriate error codes for programmatic integration
9. **FR009**: Display count of detected JPEG files before processing
10. **FR010**: Provide alternative sorting option by file modification date in settings
11. **FR011**: Support multiple file access methods (File System Access API, File Input, Drag & Drop)
12. **FR012**: Automatically detect and use best available browser API for file access
13. **FR013**: Skip corrupted or unreadable JPEG files during processing
14. **FR014**: Generate detailed processing report showing successful and failed files
15. **FR015**: Continue video creation with available valid images
16. **FR016**: Preserve original image data without any preprocessing or modification
17. **FR017**: Auto-generate output filename based on source folder name with timestamp suffix for uniqueness
18. **FR018**: Allow user to customize output filename and naming pattern in settings
19. **FR019**: Display detailed progress information during processing (current step, percentage, current file)
20. **FR020**: Show estimated time remaining and processing statistics

### Non-Functional Requirements
1. **NFR001**: Run entirely locally without internet dependencies after initial load
2. **NFR002**: Compatible with IT-restricted Windows environments
3. **NFR003**: Minimal external dependencies
4. **NFR004**: Process typical medical image sequences (50-500 images) within reasonable time
5. **NFR005**: Support common JPEG variations used in medical imaging
6. **NFR006**: Maintain image quality during MP4 conversion

### Technical Requirements
1. **TR001**: Primary implementation: Browser-based JavaScript/HTML application
2. **TR002**: Fallback options: Python with PyQt6 GUI, or C++ with simple GUI
3. **TR003**: Handle typical medical image dimensions and file sizes
4. **TR004**: Generate MP4 with standard codecs for broad compatibility
5. **TR005**: Default video settings: 15 FPS frame rate, original image resolution, medium compression
6. **TR006**: Provide user interface for adjusting frame rate (5-60 FPS), resolution scaling, and quality settings
7. **TR007**: Implement natural/numerical sorting algorithm for filename ordering (e.g., img1.jpg, img2.jpg, img10.jpg)
8. **TR008**: Provide fallback sorting option using file modification date
9. **TR009**: Implement hybrid file access approach: File System Access API (primary), File Input API with webkitdirectory (fallback), Drag & Drop (alternative)
10. **TR010**: Graceful degradation across different browser capabilities and security restrictions
11. **TR011**: Implement robust error handling with file skipping and detailed logging
12. **TR012**: Generate processing summary report with file-by-file status
13. **TR013**: No image preprocessing - preserve original medical image data integrity
14. **TR014**: Handle dimension variations by using largest common resolution or original dimensions
15. **TR015**: Implement smart output naming: "{folder_name}.mp4" with timestamp suffix if file exists
16. **TR016**: Provide user-customizable naming patterns and filename override options
17. **TR017**: Implement comprehensive progress tracking with step-by-step status updates
18. **TR018**: Display real-time processing information: current operation, file being processed, completion percentage, ETA

## Assumptions
1. **Input Format**: Source images are in JPEG format only
2. **File Naming**: Images follow sequential naming convention with numerical components (natural sorting handles frame order)
3. **Folder Structure**: All relevant images are in a single source folder (single folder processing per operation)
4. **User Environment**: Target users have basic computer literacy for folder navigation
5. **Browser Support**: Modern browser with hybrid API support (File System Access preferred, File Input fallback)
6. **Image Consistency**: Images may have varying dimensions - application handles this without modification
7. **Output Location**: User can specify output location or default to source folder
8. **Frame Rate**: Default 15 FPS with user-adjustable range (5-60 FPS) suitable for medical image review
9. **Video Quality**: Medium compression default with user-selectable quality levels (high/medium/low)
10. **Resolution Handling**: Maintain original image resolution by default with optional scaling options
11. **File Processing**: Process all JPEG files in selected folder (user manages unwanted files via file system)
12. **Sorting Logic**: Natural/numerical sorting works for most medical imaging filename conventions
13. **Error Recovery**: Skip corrupted files and continue processing with detailed error logging
14. **Data Integrity**: No image preprocessing applied to preserve diagnostic accuracy
15. **Output Naming**: Default naming pattern uses source folder name with automatic timestamp suffix for uniqueness
16. **Progress Feedback**: Detailed progress indication with current step, completion percentage, current file, and ETA
17. **Processing Scope**: Single folder processing for initial version (batch processing consideration for future enhancement)

## Open Questions
~~All Open Questions Have Been Resolved~~

## Current Implementation Status

### ✅ **COMPLETED PHASES**
- **Phase 1**: Core App Setup (Steps 1.1-1.4) - File system access, JPEG detection, sorting
- **Phase 2**: Video Generation Engine (Steps 2.1-2.4) - FFmpeg.js integration, conversion pipeline, progress tracking, error handling
- **Phase 3**: Output and Validation 
  - **Step 3.1**: Enhanced MP4 file save functionality ✅ **COMPLETED**

### 🚧 **IN PROGRESS**
- **Phase 3**: Output and Validation (Steps 3.2-3.4)

### 📋 **PENDING**
- **Phase 4**: User Experience Enhancement
- **Phase 5**: Testing and Deployment

## Future Enhancement Considerations
1. **Batch Processing**: Support for processing multiple folders in sequence
2. **Advanced Video Controls**: Additional codec options and video effects
3. **DICOM Integration**: Direct DICOM file support without JPEG conversion
4. **Cloud Storage Integration**: Support for cloud-based medical image repositories
5. **Export Formats**: Additional output formats (AVI, MOV, GIF animations)

## Step-by-Step Implementation Plan

### Phase 1: Core Browser Application Setup
1. **Step 1.1**: ✅ **COMPLETED** - Create HTML interface with folder selection capability
2. **Step 1.2**: ✅ **COMPLETED** - Implement JavaScript file system access using available browser APIs
3. **Step 1.3**: ✅ **COMPLETED** - Add JPEG file detection and validation logic
4. **Step 1.4**: ✅ **COMPLETED** - Implement file sorting algorithm

### Phase 2: Video Generation Engine
1. **Step 2.1**: ✅ **COMPLETED** - Research and integrate browser-based video encoding library (e.g., FFmpeg.js)
2. **Step 2.2**: ✅ **COMPLETED** - Implement image-to-video conversion logic
3. **Step 2.3**: ✅ **COMPLETED** - Add enhanced progress tracking with ETA, step-by-step status, and statistics
4. **Step 2.4**: ✅ **COMPLETED** - Implement comprehensive error handling, validation, and recovery mechanisms

### Phase 3: Output and Validation
1. **Step 3.1**: Add MP4 file save functionality
2. **Step 3.2**: Implement automatic video playback/testing
3. **Step 3.3**: Add success/failure reporting
4. **Step 3.4**: Implement proper error codes and messaging

### Phase 4: User Experience Enhancement
1. **Step 4.1**: Add intuitive UI elements and styling
2. **Step 4.2**: Implement drag-and-drop folder selection
3. **Step 4.3**: Add settings panel for video parameters
4. **Step 4.4**: Include help documentation and tooltips

### Phase 5: Testing and Deployment
1. **Step 5.1**: Test with various medical image sequences
2. **Step 5.2**: Validate compatibility across different browsers
3. **Step 5.3**: Performance testing with large image sets
4. **Step 5.4**: Create deployment package for restricted environments

### Fallback Implementation Plan
If browser-based approach proves unfeasible:
1. **Alternative 1**: Python + PyQt6 desktop application
2. **Alternative 2**: Simple C++ GUI application
3. **Alternative 3**: Command-line tool with batch file wrapper

## Dependencies and Technical Stack

### Primary Stack (Browser-based)
- File System Access API (primary file access method)
- File Input API with webkitdirectory (fallback method)
- Drag & Drop API (alternative user interface)
- JavaScript (ES6+)
- Canvas API for image processing
- Web-based video encoding library (FFmpeg.js or similar)
- CSS for styling

### Fallback Stacks
- **Python**: PyQt6, OpenCV, FFmpeg-python
- **C++**: Qt or simple Windows API, OpenCV, FFmpeg

## Success Criteria
1. Successfully converts medical image sequences to MP4 format
2. Runs in restricted IT environments without administrative privileges
3. Processes typical image sequences (100-200 files) in under 2 minutes
4. Generated videos play correctly in standard media players
5. User interface requires no technical training to operate
6. Zero false positives in file validation and error handling

---

*This specification is designed to be iteratively refined based on stakeholder feedback and technical feasibility assessment.*
