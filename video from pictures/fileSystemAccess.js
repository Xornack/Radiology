// File System Access Module - Step 1.2
// Implements hybrid approach: File System Access API -> File Input API -> Drag & Drop
// As specified in TR009: Hybrid file access approach

class FileSystemManager {
    constructor() {
        this.apiSupport = this.detectAPISupport();
        this.bestAPI = this.getBestAvailableAPI();
        console.log('FileSystemManager initialized with:', this.bestAPI);
    }

    // Detect which APIs are supported by the current browser
    detectAPISupport() {
        const support = {
            fileSystemAccess: 'showDirectoryPicker' in window,
            fileInput: 'HTMLInputElement' in window && 'webkitdirectory' in document.createElement('input'),
            dragDrop: 'DataTransfer' in window && 'DataTransferItem' in window
        };
        
        console.log('Browser API Support:', support);
        return support;
    }

    // Get the best available API for file access
    getBestAvailableAPI() {
        if (this.apiSupport.fileSystemAccess) {
            return 'fileSystemAccess';
        } else if (this.apiSupport.fileInput) {
            return 'fileInput';
        } else if (this.apiSupport.dragDrop) {
            return 'dragDrop';
        } else {
            return 'none';
        }
    }

    // Main method to select files using the best available API
    async selectFiles() {
        try {
            switch (this.bestAPI) {
                case 'fileSystemAccess':
                    return await this.accessViaFileSystemAPI();
                case 'fileInput':
                    return await this.accessViaFileInput();
                case 'dragDrop':
                    // Drag & Drop requires user interaction, return instruction
                    return { 
                        method: 'dragDrop', 
                        message: 'Please drag and drop a folder containing JPEG images',
                        requiresUserAction: true 
                    };
                default:
                    throw new Error('No supported file access method available');
            }
        } catch (error) {
            return this.handleAPIError(error);
        }
    }

    // File System Access API implementation (Chrome, Edge)
    async accessViaFileSystemAPI() {
        try {
            console.log('Using File System Access API');
            
            if (!('showDirectoryPicker' in window)) {
                throw new Error('File System Access API not supported');
            }

            // Request directory picker
            const dirHandle = await window.showDirectoryPicker({
                mode: 'read'
            });

            const files = [];
            
            // Iterate through directory entries
            for await (const [name, handle] of dirHandle.entries()) {
                if (handle.kind === 'file') {
                    const file = await handle.getFile();
                    
                    // Filter for JPEG files using enhanced validation
                    if (this.isValidJPEGFile(file)) {
                        // Add webkitRelativePath-like property for compatibility
                        Object.defineProperty(file, 'webkitRelativePath', {
                            value: `${dirHandle.name}/${file.name}`,
                            writable: false
                        });
                        files.push(file);
                    }
                }
            }

            if (files.length === 0) {
                throw new Error('No JPEG files found in selected directory');
            }

            return {
                method: 'fileSystemAccess',
                files: files,
                folderName: dirHandle.name,
                success: true
            };

        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('Directory selection was cancelled');
            }
            throw error;
        }
    }

    // File Input API implementation (fallback for most browsers)
    async accessViaFileInput() {
        console.log('Using File Input API');
        
        return new Promise((resolve, reject) => {
            try {
                // Create or use existing file input
                let fileInput = document.getElementById('folderInput');
                
                if (!fileInput) {
                    fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.webkitdirectory = true;
                    fileInput.multiple = true;
                    fileInput.accept = 'image/jpeg,image/jpg';
                    fileInput.style.display = 'none';
                    document.body.appendChild(fileInput);
                }

                // Set up event listener
                const handleChange = (event) => {
                    fileInput.removeEventListener('change', handleChange);
                    
                    const files = Array.from(event.target.files).filter(file => this.isValidJPEGFile(file));
                    
                    if (files.length === 0) {
                        reject(new Error('No JPEG files found in selected folder'));
                        return;
                    }

                    // Extract folder name
                    const folderName = files[0].webkitRelativePath 
                        ? files[0].webkitRelativePath.split('/')[0] 
                        : 'selected_folder';

                    resolve({
                        method: 'fileInput',
                        files: files,
                        folderName: folderName,
                        success: true
                    });
                };

                fileInput.addEventListener('change', handleChange);
                
                // Trigger file picker
                fileInput.click();

            } catch (error) {
                reject(error);
            }
        });
    }

    // Drag & Drop API implementation 
    accessViaDragDrop(dataTransfer) {
        console.log('Processing Drag & Drop files');
        
        try {
            const files = [];
            const items = dataTransfer.items || [];

            // Process dropped items
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item.kind === 'file') {
                    const file = item.getAsFile();
                    if (file && this.isValidJPEGFile(file)) {
                        files.push(file);
                    }
                }
            }

            if (files.length === 0) {
                throw new Error('No JPEG files found in dropped items');
            }

            // Try to extract folder name from file paths
            let folderName = 'dropped_files';
            if (files[0].webkitRelativePath) {
                folderName = files[0].webkitRelativePath.split('/')[0];
            }

            return {
                method: 'dragDrop',
                files: files,
                folderName: folderName,
                success: true
            };

        } catch (error) {
            throw error;
        }
    }

    // Check if file is a JPEG image
    isJPEGFile(file) {
        return file.type === 'image/jpeg' || 
               file.name.toLowerCase().endsWith('.jpg') || 
               file.name.toLowerCase().endsWith('.jpeg');
    }

    // Enhanced JPEG validation - Step 1.3
    isValidJPEGFile(file) {
        if (!file) {
            return false;
        }

        // Check basic properties
        if (!file.name || !file.type) {
            return false;
        }

        // Check file extension (case insensitive)
        const name = file.name.toLowerCase();
        const hasValidExtension = name.endsWith('.jpg') || name.endsWith('.jpeg');

        // Check MIME type
        const hasValidMimeType = file.type === 'image/jpeg' || file.type === 'image/jpg';

        // For basic validation, require either valid extension OR valid MIME type
        // This handles cases where one might be missing or incorrect
        return hasValidExtension || hasValidMimeType;
    }

    // Validate JPEG binary signature (magic bytes)
    async validateJPEGSignature(fileOrBuffer) {
        try {
            let buffer;
            
            if (fileOrBuffer instanceof Uint8Array) {
                buffer = fileOrBuffer;
            } else if (fileOrBuffer instanceof File) {
                // Read first few bytes of the file
                const arrayBuffer = await fileOrBuffer.slice(0, 10).arrayBuffer();
                buffer = new Uint8Array(arrayBuffer);
            } else {
                throw new Error('Invalid input type for signature validation');
            }

            // JPEG files start with FF D8 FF
            if (buffer.length < 3) {
                return false;
            }

            return buffer[0] === 0xFF && buffer[1] === 0xD8 && buffer[2] === 0xFF;
        } catch (error) {
            console.error('Error validating JPEG signature:', error);
            return false;
        }
    }

    // Validate JPEG file integrity (basic check)
    async validateJPEGIntegrity(fileOrBuffer) {
        try {
            let buffer;
            
            if (fileOrBuffer instanceof Uint8Array) {
                buffer = fileOrBuffer;
            } else if (fileOrBuffer instanceof File) {
                // For performance, only read first and last few bytes
                const size = fileOrBuffer.size;
                if (size < 4) {
                    return { isValid: false, error: 'File too small to be a valid JPEG' };
                }

                // Read first 10 bytes and last 2 bytes
                const startBuffer = await fileOrBuffer.slice(0, 10).arrayBuffer();
                const endBuffer = await fileOrBuffer.slice(-2).arrayBuffer();
                
                const start = new Uint8Array(startBuffer);
                const end = new Uint8Array(endBuffer);
                
                // Check JPEG start marker (FF D8 FF)
                const hasValidStart = start[0] === 0xFF && start[1] === 0xD8 && start[2] === 0xFF;
                
                // Check JPEG end marker (FF D9)
                const hasValidEnd = end[0] === 0xFF && end[1] === 0xD9;
                
                return {
                    isValid: hasValidStart && hasValidEnd,
                    error: !hasValidStart ? 'Invalid JPEG start marker' : 
                           !hasValidEnd ? 'Invalid JPEG end marker' : null,
                    details: {
                        hasValidStart,
                        hasValidEnd,
                        fileSize: size
                    }
                };
            } else {
                throw new Error('Invalid input type for integrity validation');
            }

            // For raw buffer, just check basic structure
            if (buffer.length < 4) {
                return { isValid: false, error: 'Buffer too small' };
            }

            const hasValidStart = buffer[0] === 0xFF && buffer[1] === 0xD8 && buffer[2] === 0xFF;
            return {
                isValid: hasValidStart,
                error: hasValidStart ? null : 'Invalid JPEG signature',
                details: { hasValidStart }
            };

        } catch (error) {
            return {
                isValid: false,
                error: `Integrity check failed: ${error.message}`,
                details: { exception: error.message }
            };
        }
    }

    // Batch validation of multiple files
    async validateFilesBatch(files, options = {}) {
        const {
            includeIntegrityCheck = false,
            maxConcurrent = 10,
            onProgress = null
        } = options;

        const results = {
            validFiles: [],
            invalidFiles: [],
            errors: [],
            summary: {
                totalFiles: files.length,
                validCount: 0,
                invalidCount: 0,
                errorCount: 0,
                processingTime: 0
            }
        };

        const startTime = performance.now();

        try {
            // Process files in batches to avoid overwhelming the browser
            for (let i = 0; i < files.length; i += maxConcurrent) {
                const batch = files.slice(i, i + maxConcurrent);
                const batchPromises = batch.map(async (file, index) => {
                    try {
                        // Basic validation
                        const isBasicValid = this.isValidJPEGFile(file);
                        
                        if (!isBasicValid) {
                            results.invalidFiles.push({
                                file,
                                reason: 'Failed basic JPEG validation',
                                index: i + index
                            });
                            return;
                        }

                        // Optional integrity check
                        if (includeIntegrityCheck) {
                            const integrityResult = await this.validateJPEGIntegrity(file);
                            if (!integrityResult.isValid) {
                                results.invalidFiles.push({
                                    file,
                                    reason: `Integrity check failed: ${integrityResult.error}`,
                                    index: i + index,
                                    details: integrityResult.details
                                });
                                return;
                            }
                        }

                        // File is valid
                        results.validFiles.push({
                            file,
                            index: i + index,
                            validated: true
                        });

                    } catch (error) {
                        results.errors.push({
                            file,
                            error: error.message,
                            index: i + index
                        });
                    }
                });

                await Promise.all(batchPromises);

                // Report progress if callback provided
                if (onProgress) {
                    onProgress({
                        processed: Math.min(i + maxConcurrent, files.length),
                        total: files.length,
                        percentage: Math.round((Math.min(i + maxConcurrent, files.length) / files.length) * 100)
                    });
                }
            }

            // Update summary
            results.summary.validCount = results.validFiles.length;
            results.summary.invalidCount = results.invalidFiles.length;
            results.summary.errorCount = results.errors.length;
            results.summary.processingTime = performance.now() - startTime;

            return results;

        } catch (error) {
            throw new Error(`Batch validation failed: ${error.message}`);
        }
    }
}

// Create global instance
window.fileSystemModule = new FileSystemManager();

// Expose methods for testing and external use
window.fileSystemModule.detectAPISupport = function() {
    return this.apiSupport;
};

window.fileSystemModule.getBestAvailableAPI = function() {
    return this.bestAPI;
};

window.fileSystemModule.handleAPIError = function(error) {
    return this.handleAPIError(error);
};

console.log('File System Access Module loaded successfully');
console.log('Available APIs:', window.fileSystemModule.apiSupport);
console.log('Best API:', window.fileSystemModule.bestAPI);
