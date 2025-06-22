# Video from Pictures - Python Version

A PyQt6-based desktop application for converting medical image sequences (JPEG, PNG, DICOM) to MP4 videos.

## Project Structure

```
python_version/
├── src/                    # Source code
├── tests/                  # Test files
├── requirements.txt        # Python dependencies
├── config.json            # Default configuration
└── README.md              # This file
```

## Development Status

- [x] Step 1.1: Project directory structure created
- [x] Step 1.2: Virtual environment and dependencies
- [x] Step 1.3: GUI design
- [x] Step 1.4: Basic GUI functionality
- [x] Step 2.1: Image file loading and validation
- [x] Step 2.2: Sorting algorithms implementation
- [x] Step 2.3: Video encoding integration
- [x] Step 2.4: Progress tracking and reporting
- [x] Step 2.5: Error handling and logging

### Phase 2 Complete! ✅
All core processing logic has been implemented with comprehensive error handling and testing.

### Next: Phase 3 - GUI Integration and Testing
- Step 3.1: Connect GUI elements to core processing functions
- Step 3.2: Implement settings functionality
- Step 3.3: Thoroughly test the application
- Step 3.4: Refine the user interface and overall application flow

## Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python src/main.py
```
