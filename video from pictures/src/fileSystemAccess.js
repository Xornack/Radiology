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

    // Get browser information and capabilities
    getBrowserInfo() {
        const userAgent = navigator.userAgent;
        let browserName = 'Unknown';
        let browserVersion = 'Unknown';

        // Detect browser
        if (userAgent.indexOf('Chrome') > -1 && userAgent.indexOf('Edg') === -1) {
            browserName = 'Chrome';
            browserVersion = userAgent.match(/Chrome\/([0-9]+)/)?.[1] || 'Unknown';
        } else if (userAgent.indexOf('Firefox') > -1) {
            browserName = 'Firefox';
            browserVersion = userAgent.match(/Firefox\/([0-9]+)/)?.[1] || 'Unknown';
        } else if (userAgent.indexOf('Safari') > -1 && userAgent.indexOf('Chrome') === -1) {
            browserName = 'Safari';
            browserVersion = userAgent.match(/Version\/([0-9]+)/)?.[1] || 'Unknown';
        } else if (userAgent.indexOf('Edg') > -1) {
            browserName = 'Edge';
            browserVersion = userAgent.match(/Edg\/([0-9]+)/)?.[1] || 'Unknown';
        }

        return {
            browser: browserName,
            version: browserVersion,
            userAgent: userAgent,
            apiSupport: this.apiSupport,
            bestAPI: this.bestAPI,
            platform: navigator.platform || 'Unknown'
        };
    }

    // Handle API errors gracefully
    handleAPIError(error) {
        console.error('File system API error:', error);
        
        if (error.name === 'AbortError') {
            return {
                success: false,
                error: 'File selection was cancelled by user',
                canRetry: true
            };
        } else if (error.name === 'NotAllowedError') {
            return {
                success: false,
                error: 'File access permission denied',
                canRetry: true
            };
        } else if (error.name === 'SecurityError') {
            return {
                success: false,
                error: 'Security error - file access blocked',
                canRetry: false
            };
        } else {
            return {
                success: false,
                error: error.message || 'Unknown file system error',
                canRetry: true
            };
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
                throw new Error('User cancelled directory selection');
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

    // ========== FILE SORTING METHODS - STEP 1.4 ==========
    
    /**
     * Sort files using natural/numerical ordering for medical image sequences
     * Implements TR007 requirement for natural sorting algorithm
     * @param {File[]} files - Array of files to sort
     * @param {string} sortMethod - 'natural' (default) or 'dateModified'
     * @return {File[]} - Sorted array of files
     */
    sortFiles(files, sortMethod = 'natural') {
        if (!Array.isArray(files) || files.length === 0) {
            return files;
        }

        console.log(`Sorting ${files.length} files using ${sortMethod} method`);
        
        switch (sortMethod) {
            case 'natural':
                return this.sortFilesNatural(files);
            case 'dateModified':
                return this.sortFilesByDate(files);
            default:
                console.warn(`Unknown sort method: ${sortMethod}, using natural sort`);
                return this.sortFilesNatural(files);
        }
    }

    /**
     * Natural/numerical sorting algorithm for filenames
     * Handles sequences like: img1.jpg, img2.jpg, img10.jpg, img20.jpg
     * Supports medical imaging conventions: scan001.jpg, scan002.jpg, slice_001.jpg
     */
    sortFilesNatural(files) {
        return [...files].sort((a, b) => {
            return this.compareFilenamesNatural(a.name, b.name);
        });
    }

    /**
     * Compare two filenames using natural ordering
     * Splits filenames into text and numeric parts for proper comparison
     */
    compareFilenamesNatural(filename1, filename2) {
        // Convert to lowercase for case-insensitive comparison
        const name1 = filename1.toLowerCase();
        const name2 = filename2.toLowerCase();

        // Split into chunks of text and numbers
        const chunks1 = this.splitFilenameIntoChunks(name1);
        const chunks2 = this.splitFilenameIntoChunks(name2);

        const maxLength = Math.max(chunks1.length, chunks2.length);

        for (let i = 0; i < maxLength; i++) {
            const chunk1 = chunks1[i] || '';
            const chunk2 = chunks2[i] || '';

            // If both chunks are numbers, compare numerically
            if (this.isNumericChunk(chunk1) && this.isNumericChunk(chunk2)) {
                const num1 = parseInt(chunk1, 10);
                const num2 = parseInt(chunk2, 10);
                if (num1 !== num2) {
                    return num1 - num2;
                }
            } else {
                // String comparison
                if (chunk1 !== chunk2) {
                    return chunk1.localeCompare(chunk2);
                }
            }
        }

        return 0;
    }

    /**
     * Split filename into alternating text and numeric chunks
     * Example: "scan001_slice_02.jpg" -> ["scan", "001", "_slice_", "02", ".jpg"]
     */
    splitFilenameIntoChunks(filename) {
        // Regular expression to split into text and numeric parts
        return filename.match(/(\d+|\D+)/g) || [filename];
    }

    /**
     * Check if a chunk represents a number
     */
    isNumericChunk(chunk) {
        return /^\d+$/.test(chunk);
    }

    /**
     * Sort files by modification date (fallback option)
     * Implements TR008 requirement for date-based sorting fallback
     */
    sortFilesByDate(files) {
        return [...files].sort((a, b) => {
            const dateA = a.lastModified || 0;
            const dateB = b.lastModified || 0;
            return dateA - dateB;
        });
    }

    /**
     * Analyze filename patterns to determine best sorting method
     * Returns recommendation for sorting method based on filename analysis
     */
    analyzeSortingPattern(files) {
        if (!Array.isArray(files) || files.length === 0) {
            return { recommended: 'natural', confidence: 0, reason: 'No files to analyze' };
        }

        let numericPatternCount = 0;
        let sequentialPatternCount = 0;
        const sampleSize = Math.min(10, files.length); // Analyze sample for performance

        for (let i = 0; i < sampleSize; i++) {
            const filename = files[i].name.toLowerCase();
            
            // Check for numeric patterns (digits in filename)
            if (/\d+/.test(filename)) {
                numericPatternCount++;
            }

            // Check for sequential patterns if we have enough files
            if (i > 0) {
                const prevFilename = files[i-1].name.toLowerCase();
                const chunks1 = this.splitFilenameIntoChunks(prevFilename);
                const chunks2 = this.splitFilenameIntoChunks(filename);
                
                // Look for incrementing numbers
                for (let j = 0; j < Math.min(chunks1.length, chunks2.length); j++) {
                    if (this.isNumericChunk(chunks1[j]) && this.isNumericChunk(chunks2[j])) {
                        const num1 = parseInt(chunks1[j], 10);
                        const num2 = parseInt(chunks2[j], 10);
                        if (num2 === num1 + 1) {
                            sequentialPatternCount++;
                            break;
                        }
                    }
                }
            }
        }

        const numericRatio = numericPatternCount / sampleSize;
        const sequentialRatio = sequentialPatternCount / Math.max(1, sampleSize - 1);

        // Determine recommendation
        if (numericRatio >= 0.7) {
            return {
                recommended: 'natural',
                confidence: Math.min(0.9, numericRatio + sequentialRatio * 0.3),
                reason: `High numeric pattern detected (${Math.round(numericRatio * 100)}% of files)`
            };
        } else if (numericRatio >= 0.3) {
            return {
                recommended: 'natural',
                confidence: 0.6,
                reason: `Moderate numeric pattern detected (${Math.round(numericRatio * 100)}% of files)`
            };
        } else {
            return {
                recommended: 'dateModified',
                confidence: 0.5,
                reason: `Low numeric pattern detected, date sorting may be more appropriate`
            };
        }
    }

    // ========== END FILE SORTING METHODS ==========
}

// Create global instance
const fileSystemManager = new FileSystemManager();

// Create a clean module object without circular references
window.fileSystemModule = {
    // Properties
    apiSupport: fileSystemManager.apiSupport,
    bestAPI: fileSystemManager.bestAPI,
    
    // Methods - properly bound to avoid circular references
    detectAPISupport: () => fileSystemManager.apiSupport,
    getBestAvailableAPI: () => fileSystemManager.bestAPI,
    handleAPIError: (error) => fileSystemManager.handleAPIError(error),
    selectFiles: () => fileSystemManager.selectFiles(),
    accessViaDragDrop: (dataTransfer) => fileSystemManager.accessViaDragDrop(dataTransfer),
    isValidJPEGFile: (file) => fileSystemManager.isValidJPEGFile(file),
    isJPEGFile: (file) => fileSystemManager.isJPEGFile(file),
    validateJPEGSignature: (file) => fileSystemManager.validateJPEGSignature(file),
    validateFilesBatch: (files, options) => fileSystemManager.validateFilesBatch(files, options),
    getBrowserInfo: () => fileSystemManager.getBrowserInfo(),
    
    // Step 1.4: File sorting methods - properly bound
    sortFiles: (files, sortMethod) => fileSystemManager.sortFiles(files, sortMethod),
    sortFilesNatural: (files) => fileSystemManager.sortFilesNatural(files),
    sortFilesByDate: (files) => fileSystemManager.sortFilesByDate(files),
    analyzeSortingPattern: (files) => fileSystemManager.analyzeSortingPattern(files)
};

console.log('File System Access Module loaded successfully');
console.log('Available APIs:', window.fileSystemModule.apiSupport);
console.log('Best API:', window.fileSystemModule.bestAPI);
