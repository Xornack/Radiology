/**
 * Error Code System for Video from Pictures Application
 * 
 * Provides standardized error codes, categories, and messaging for consistent
 * error handling throughout the application.
 */

class ErrorCodeSystem {
    constructor() {
        this.errorCodes = {
            // File System Access Errors (FSA_)
            'FSA_001': {
                code: 'FSA_001',
                category: 'FILE_SYSTEM_ACCESS',
                severity: 'HIGH',
                title: 'Directory Access Denied',
                message: 'Unable to access the selected directory. Please check permissions and try again.',
                userAction: 'Select a different directory or check folder permissions',
                technicalDetails: 'File System Access API returned permission denied'
            },
            'FSA_002': {
                code: 'FSA_002',
                category: 'FILE_SYSTEM_ACCESS',
                severity: 'HIGH',
                title: 'API Not Supported',
                message: 'Your browser does not support the required file access features.',
                userAction: 'Use a modern browser like Chrome, Edge, or Firefox',
                technicalDetails: 'File System Access API or File Input API not available'
            },
            'FSA_003': {
                code: 'FSA_003',
                category: 'FILE_SYSTEM_ACCESS',
                severity: 'MEDIUM',
                title: 'Directory Empty',
                message: 'The selected directory contains no JPEG files.',
                userAction: 'Select a directory containing JPEG images',
                technicalDetails: 'No files with .jpg, .jpeg extensions found in directory'
            },
            'FSA_004': {
                code: 'FSA_004',
                category: 'FILE_SYSTEM_ACCESS',
                severity: 'MEDIUM',
                title: 'File Read Error',
                message: 'Unable to read one or more image files from the directory.',
                userAction: 'Check if files are accessible and not corrupted',
                technicalDetails: 'File reading operation failed during image processing'
            },

            // Image Processing Errors (IMG_)
            'IMG_001': {
                code: 'IMG_001',
                category: 'IMAGE_PROCESSING',
                severity: 'MEDIUM',
                title: 'Invalid Image Format',
                message: 'One or more files are not valid JPEG images.',
                userAction: 'Ensure all files in the directory are valid JPEG images',
                technicalDetails: 'Image failed validation or could not be loaded as JPEG'
            },
            'IMG_002': {
                code: 'IMG_002',
                category: 'IMAGE_PROCESSING',
                severity: 'LOW',
                title: 'Image Dimensions Vary',
                message: 'Images have different dimensions. Video will use the most common size.',
                userAction: 'This is informational - processing will continue',
                technicalDetails: 'Mixed image dimensions detected, using auto-sizing'
            },
            'IMG_003': {
                code: 'IMG_003',
                category: 'IMAGE_PROCESSING',
                severity: 'HIGH',
                title: 'Image Loading Failed',
                message: 'Critical error loading images. Cannot proceed with video creation.',
                userAction: 'Check image files and try again',
                technicalDetails: 'All image loading attempts failed'
            },
            'IMG_004': {
                code: 'IMG_004',
                category: 'IMAGE_PROCESSING',
                severity: 'MEDIUM',
                title: 'Image Corruption Detected',
                message: 'Some images appear to be corrupted and will be skipped.',
                userAction: 'Review skipped files and replace if necessary',
                technicalDetails: 'Image data integrity check failed'
            },

            // Video Encoding Errors (VID_)
            'VID_001': {
                code: 'VID_001',
                category: 'VIDEO_ENCODING',
                severity: 'HIGH',
                title: 'Encoding Initialization Failed',
                message: 'Unable to initialize video encoding engine.',
                userAction: 'Refresh the page and try again',
                technicalDetails: 'FFmpeg.js or WebCodecs initialization failed'
            },
            'VID_002': {
                code: 'VID_002',
                category: 'VIDEO_ENCODING',
                severity: 'HIGH',
                title: 'Encoding Process Failed',
                message: 'Video encoding failed during processing.',
                userAction: 'Try reducing video quality or frame rate in settings',
                technicalDetails: 'Video encoding pipeline encountered fatal error'
            },
            'VID_003': {
                code: 'VID_003',
                category: 'VIDEO_ENCODING',
                severity: 'MEDIUM',
                title: 'Memory Limit Exceeded',
                message: 'Not enough memory available for video processing.',
                userAction: 'Try processing fewer images or reduce video quality',
                technicalDetails: 'Browser memory limit reached during encoding'
            },
            'VID_004': {
                code: 'VID_004',
                category: 'VIDEO_ENCODING',
                severity: 'LOW',
                title: 'Codec Not Optimal',
                message: 'Using fallback codec. Video quality may be reduced.',
                userAction: 'This is informational - processing will continue',
                technicalDetails: 'Preferred codec unavailable, using fallback'
            },

            // File Save Errors (SAV_)
            'SAV_001': {
                code: 'SAV_001',
                category: 'FILE_SAVE',
                severity: 'HIGH',
                title: 'Save Permission Denied',
                message: 'Unable to save video file to the selected location.',
                userAction: 'Choose a different save location or check permissions',
                technicalDetails: 'File write operation denied by browser or OS'
            },
            'SAV_002': {
                code: 'SAV_002',
                category: 'FILE_SAVE',
                severity: 'HIGH',
                title: 'Insufficient Storage Space',
                message: 'Not enough disk space available to save the video file.',
                userAction: 'Free up disk space or choose a different location',
                technicalDetails: 'Disk space quota exceeded during file save'
            },
            'SAV_003': {
                code: 'SAV_003',
                category: 'FILE_SAVE',
                severity: 'MEDIUM',
                title: 'File Already Exists',
                message: 'A file with this name already exists at the save location.',
                userAction: 'Choose a different filename or allow overwrite',
                technicalDetails: 'File conflict detected during save operation'
            },
            'SAV_004': {
                code: 'SAV_004',
                category: 'FILE_SAVE',
                severity: 'MEDIUM',
                title: 'Save Method Fallback',
                message: 'Primary save method failed, using browser download instead.',
                userAction: 'Check your downloads folder for the video file',
                technicalDetails: 'File System Access API save failed, using download API'
            },

            // Validation Errors (VAL_)
            'VAL_001': {
                code: 'VAL_001',
                category: 'VALIDATION',
                severity: 'HIGH',
                title: 'Video Validation Failed',
                message: 'Created video file failed validation tests.',
                userAction: 'Try creating the video again with different settings',
                technicalDetails: 'Video playback test or metadata validation failed'
            },
            'VAL_002': {
                code: 'VAL_002',
                category: 'VALIDATION',
                severity: 'MEDIUM',
                title: 'Playback Issues Detected',
                message: 'Video created successfully but may have playback issues.',
                userAction: 'Test the video in your preferred media player',
                technicalDetails: 'Video validation detected potential compatibility issues'
            },
            'VAL_003': {
                code: 'VAL_003',
                category: 'VALIDATION',
                severity: 'LOW',
                title: 'Quality Validation Warning',
                message: 'Video quality validation detected minor issues.',
                userAction: 'Video should play normally - this is informational',
                technicalDetails: 'Quality metrics outside optimal range but acceptable'
            },

            // System Errors (SYS_)
            'SYS_001': {
                code: 'SYS_001',
                category: 'SYSTEM',
                severity: 'HIGH',
                title: 'Browser Compatibility Issue',
                message: 'Your browser lacks required features for video processing.',
                userAction: 'Update your browser or use Chrome/Edge/Firefox',
                technicalDetails: 'Required Web APIs not available or outdated'
            },
            'SYS_002': {
                code: 'SYS_002',
                category: 'SYSTEM',
                severity: 'HIGH',
                title: 'Memory Allocation Failed',
                message: 'Unable to allocate sufficient memory for processing.',
                userAction: 'Close other browser tabs and try again',
                technicalDetails: 'Browser memory allocation limits reached'
            },
            'SYS_003': {
                code: 'SYS_003',
                category: 'SYSTEM',
                severity: 'MEDIUM',
                title: 'Performance Warning',
                message: 'System performance may affect processing speed.',
                userAction: 'Processing will continue but may take longer',
                technicalDetails: 'Low system resources detected'
            },

            // Network/Resource Errors (NET_)
            'NET_001': {
                code: 'NET_001',
                category: 'NETWORK',
                severity: 'HIGH',
                title: 'Resource Loading Failed',
                message: 'Unable to load required application resources.',
                userAction: 'Check internet connection and refresh the page',
                technicalDetails: 'Failed to load critical JavaScript libraries or resources'
            },
            'NET_002': {
                code: 'NET_002',
                category: 'NETWORK',
                severity: 'MEDIUM',
                title: 'Offline Mode Active',
                message: 'Application running in offline mode with limited features.',
                userAction: 'Some features may be unavailable until reconnected',
                technicalDetails: 'Network unavailable, using cached resources'
            }
        };

        this.categories = {
            'FILE_SYSTEM_ACCESS': {
                name: 'File System Access',
                description: 'Errors related to accessing files and directories',
                icon: '📁'
            },
            'IMAGE_PROCESSING': {
                name: 'Image Processing',
                description: 'Errors during image loading and processing',
                icon: '🖼️'
            },
            'VIDEO_ENCODING': {
                name: 'Video Encoding',
                description: 'Errors during video creation and encoding',
                icon: '🎥'
            },
            'FILE_SAVE': {
                name: 'File Save',
                description: 'Errors when saving output files',
                icon: '💾'
            },
            'VALIDATION': {
                name: 'Validation',
                description: 'Errors during video validation and testing',
                icon: '✅'
            },
            'SYSTEM': {
                name: 'System',
                description: 'System-level errors and browser compatibility',
                icon: '⚙️'
            },
            'NETWORK': {
                name: 'Network',
                description: 'Network and resource loading errors',
                icon: '🌐'
            }
        };

        this.severityLevels = {
            'HIGH': {
                name: 'High',
                description: 'Critical errors that prevent operation completion',
                color: '#dc3545',
                icon: '🚨'
            },
            'MEDIUM': {
                name: 'Medium', 
                description: 'Important errors that may affect functionality',
                color: '#fd7e14',
                icon: '⚠️'
            },
            'LOW': {
                name: 'Low',
                description: 'Minor issues or informational messages',
                color: '#28a745',
                icon: 'ℹ️'
            }
        };
    }

    /**
     * Get error information by error code
     * @param {string} errorCode - The error code to look up
     * @returns {Object|null} Error information object or null if not found
     */
    getError(errorCode) {
        return this.errorCodes[errorCode] || null;
    }

    /**
     * Get all errors in a specific category
     * @param {string} category - The category to filter by
     * @returns {Array} Array of error objects in the category
     */
    getErrorsByCategory(category) {
        return Object.values(this.errorCodes).filter(error => error.category === category);
    }

    /**
     * Get all errors with a specific severity level
     * @param {string} severity - The severity level to filter by
     * @returns {Array} Array of error objects with the specified severity
     */
    getErrorsBySeverity(severity) {
        return Object.values(this.errorCodes).filter(error => error.severity === severity);
    }

    /**
     * Get category information
     * @param {string} category - The category name
     * @returns {Object|null} Category information or null if not found
     */
    getCategory(category) {
        return this.categories[category] || null;
    }

    /**
     * Get severity level information
     * @param {string} severity - The severity level
     * @returns {Object|null} Severity information or null if not found
     */
    getSeverityInfo(severity) {
        return this.severityLevels[severity] || null;
    }

    /**
     * Get all available error codes
     * @returns {Array} Array of all error codes
     */
    getAllErrorCodes() {
        return Object.keys(this.errorCodes);
    }

    /**
     * Get all categories
     * @returns {Array} Array of category names
     */
    getAllCategories() {
        return Object.keys(this.categories);
    }

    /**
     * Get all severity levels
     * @returns {Array} Array of severity level names
     */
    getAllSeverityLevels() {
        return Object.keys(this.severityLevels);
    }

    /**
     * Validate if an error code exists
     * @param {string} errorCode - The error code to validate
     * @returns {boolean} True if error code exists
     */
    isValidErrorCode(errorCode) {
        return errorCode in this.errorCodes;
    }

    /**
     * Get formatted error message for display
     * @param {string} errorCode - The error code
     * @param {Object} context - Additional context information
     * @returns {Object} Formatted error message object
     */
    formatError(errorCode, context = {}) {
        const error = this.getError(errorCode);
        if (!error) {
            return {
                success: false,
                message: `Unknown error code: ${errorCode}`
            };
        }

        const category = this.getCategory(error.category);
        const severity = this.getSeverityInfo(error.severity);

        return {
            success: true,
            code: error.code,
            title: error.title,
            message: error.message,
            userAction: error.userAction,
            technicalDetails: error.technicalDetails,
            category: {
                name: category.name,
                icon: category.icon
            },
            severity: {
                name: severity.name,
                color: severity.color,
                icon: severity.icon
            },
            timestamp: new Date().toISOString(),
            context: context
        };
    }

    /**
     * Create a standardized error object
     * @param {string} errorCode - The error code
     * @param {Error} originalError - The original error object (optional)
     * @param {Object} context - Additional context information
     * @returns {Object} Standardized error object
     */
    createError(errorCode, originalError = null, context = {}) {
        const formattedError = this.formatError(errorCode, context);
        
        if (!formattedError.success) {
            return formattedError;
        }

        return {
            ...formattedError,
            originalError: originalError ? {
                name: originalError.name,
                message: originalError.message,
                stack: originalError.stack
            } : null,
            id: this.generateErrorId(),
            timestamp: new Date().toISOString()
        };
    }

    /**
     * Generate a unique error ID for tracking
     * @returns {string} Unique error ID
     */
    generateErrorId() {
        return `ERR_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Get error statistics
     * @returns {Object} Statistics about the error system
     */
    getErrorStatistics() {
        const totalErrors = Object.keys(this.errorCodes).length;
        const categoryCounts = {};
        const severityCounts = {};

        Object.values(this.errorCodes).forEach(error => {
            categoryCounts[error.category] = (categoryCounts[error.category] || 0) + 1;
            severityCounts[error.severity] = (severityCounts[error.severity] || 0) + 1;
        });

        return {
            totalErrors,
            totalCategories: Object.keys(this.categories).length,
            totalSeverityLevels: Object.keys(this.severityLevels).length,
            categoryCounts,
            severityCounts
        };
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorCodeSystem;
} else if (typeof window !== 'undefined') {
    window.ErrorCodeSystem = ErrorCodeSystem;
}
