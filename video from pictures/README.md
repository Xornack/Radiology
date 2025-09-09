# Medical Image Sequence to Video Converter

A secure, browser-based tool for converting medical image sequences (JPEG) to video files. All processing happens locally in the browser - no data ever leaves your device.

## 🏥 **Features**

- **Local-Only Processing**: All image processing and video creation happens in your browser
- **Medical Image Support**: Optimized for JPEG medical image sequences  
- **Secure**: Zero data transmission - files never leave your device
- **Easy to Use**: Drag & drop or browse for image folders
- **Modern Browser Support**: Uses Canvas + MediaRecorder APIs
- **No Dependencies**: No external libraries or CDN dependencies

## 🚀 **Quick Start**

1. **Open the application**: Open `src/index.html` in a modern web browser
2. **Select images**: Click "Browse Folder" or drag & drop a folder containing JPEG images
3. **Create video**: Click "Create Video" to process your images
4. **Download**: The video file will be automatically downloaded

## 📁 **Project Structure**

```
video from pictures/
├── src/                          # Main application files
│   ├── index.html               # Main application interface
│   ├── customVideoEncoder.js   # Canvas/MediaRecorder video encoder
│   ├── imageToVideoConverter.js # Video conversion logic
│   ├── fileSystemAccess.js     # File handling module
│   ├── progressTracker.js      # Progress tracking
│   ├── errorHandler.js         # Error handling
│   ├── fileSaver.js            # File saving functionality
│   ├── successFailureReporter.js # Reporting system
│   └── dataSecurityConfig.js   # Security configuration
│
└── docs/                        # Documentation
    ├── idea.md                  # Original project idea
    ├── get_specification_prompt.md # Specification methodology
    ├── specification.md         # Technical specification
    └── SECURITY_DEPLOYMENT_GUIDE.md # Security & deployment guide
```

## 🔒 **Security & Privacy**

- **Zero Data Transmission**: Files never leave your browser
- **Local Processing**: All video creation happens on your device
- **No Storage**: No data is stored on any server
- **Privacy First**: Designed for sensitive medical data

## 🌐 **Browser Compatibility**

- **Chrome/Edge**: Full functionality with File System Access API
- **Firefox**: Full functionality with fallback file selection
- **Safari**: Basic functionality with file input
- **Mobile**: Limited support due to file system restrictions

## 🛠 **Technical Details**

- **Video Encoding**: Canvas + MediaRecorder APIs (no FFmpeg.js)
- **File Formats**: Input: JPEG images, Output: WebM video
- **Processing**: Client-side only, memory-based
- **Security**: CSP headers, XSS protection, input validation

## 📖 **Documentation**

- **[Complete Specification](docs/specification.md)**: Detailed technical requirements
- **[Security Guide](docs/SECURITY_DEPLOYMENT_GUIDE.md)**: Deployment and security information
- **[Original Idea](docs/idea.md)**: Project conception and goals

## 🎯 **Use Cases**

- Converting medical image sequences (CT, MRI, X-ray series) to videos
- Creating time-lapse videos from image sequences
- Secure processing of sensitive imaging data
- Offline video creation without external dependencies

## ⚙️ **Development**

The application is designed to be deployed as static files - no backend server required. Simply serve the `src/` directory with any web server.

For development with live reload:
```bash
cd src/
python3 -m http.server 8000
```

## 📋 **Requirements**

- Modern web browser with MediaRecorder support
- JavaScript enabled
- Local file access permissions
