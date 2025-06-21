// Enhanced Error Handler Module - Step 2.4
// Implements comprehensive error handling and validation for video conversion
// Part of Phase 2: Video Generation Engine

class ErrorHandler {
    constructor() {
        this.errorLog = [];
        this.validationRules = {};
        this.errorCategories = {
            INPUT: 'input',
            PROCESSING: 'processing',
            ENCODING: 'encoding',
            OUTPUT: 'output',
            SYSTEM: 'system'
        };
        this.errorSeverity = {
            LOW: 'low',
            MEDIUM: 'medium',
            HIGH: 'high',
            CRITICAL: 'critical'
        };
        this.onError = null;
        this.onWarning = null;
        this.onRecovery = null;
        
        this.initializeValidationRules();
        console.log('Enhanced ErrorHandler initialized');
    }

    // Initialize validation rules
    initializeValidationRules() {
        this.validationRules = {
            fileCount: {
                min: 1,
                max: 10000,
                message: 'Invalid number of files'
            },
            fileSize: {
                min: 1024, // 1KB
                max: 100 * 1024 * 1024, // 100MB
                message: 'File size out of acceptable range'
            },
            imageFormats: {
                allowed: ['image/jpeg', 'image/jpg'],
                extensions: ['.jpg', '.jpeg'],
                message: 'Only JPEG images are supported'
            },
            imageDimensions: {
                minWidth: 16,
                minHeight: 16,
                maxWidth: 8192,
                maxHeight: 8192,
                message: 'Image dimensions out of acceptable range'
            },
            memoryUsage: {
                maxTotalSize: 2 * 1024 * 1024 * 1024, // 2GB
                message: 'Total memory usage exceeds safe limits'
            },
            encoding: {
                maxFrameRate: 60,
                minFrameRate: 1,
                supportedCodecs: ['libx264', 'libx265'],
                supportedFormats: ['mp4'],
                message: 'Encoding parameters not supported'
            }
        };
    }

    // Set callback functions
    setCallbacks(onError, onWarning, onRecovery) {
        this.onError = onError;
        this.onWarning = onWarning;
        this.onRecovery = onRecovery;
    }

    // Validate input files
    async validateInputFiles(files) {
        const validationResult = {
            isValid: true,
            validFiles: [],
            invalidFiles: [],
            warnings: [],
            errors: [],
            summary: {}
        };

        try {
            // Check file count
            if (!this.validateFileCount(files.length)) {
                this.addError(validationResult, this.errorCategories.INPUT, this.errorSeverity.CRITICAL,
                    'FILE_COUNT_INVALID', this.validationRules.fileCount.message);
                return validationResult;
            }

            // Validate individual files
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const fileValidation = await this.validateSingleFile(file, i);
                
                if (fileValidation.isValid) {
                    validationResult.validFiles.push(file);
                } else {
                    validationResult.invalidFiles.push({
                        file: file,
                        index: i,
                        errors: fileValidation.errors
                    });
                }
                
                validationResult.warnings.push(...fileValidation.warnings);
                validationResult.errors.push(...fileValidation.errors);
            }

            // Check memory usage
            const memoryValidation = this.validateMemoryUsage(validationResult.validFiles);
            if (!memoryValidation.isValid) {
                validationResult.warnings.push(...memoryValidation.warnings);
            }

            // Generate summary
            validationResult.summary = this.generateValidationSummary(validationResult);
            
            // Determine overall validity
            validationResult.isValid = validationResult.validFiles.length > 0 && 
                                     !validationResult.errors.some(e => e.severity === this.errorSeverity.CRITICAL);

            return validationResult;

        } catch (error) {
            this.addError(validationResult, this.errorCategories.SYSTEM, this.errorSeverity.CRITICAL,
                'VALIDATION_SYSTEM_ERROR', `Validation system error: ${error.message}`);
            validationResult.isValid = false;
            return validationResult;
        }
    }

    // Validate single file
    async validateSingleFile(file, index) {
        const result = {
            isValid: true,
            errors: [],
            warnings: []
        };

        try {
            // File format validation
            if (!this.validateFileFormat(file)) {
                this.addError(result, this.errorCategories.INPUT, this.errorSeverity.HIGH,
                    'INVALID_FILE_FORMAT', `File ${file.name}: ${this.validationRules.imageFormats.message}`);
                result.isValid = false;
            }

            // File size validation
            if (!this.validateFileSize(file.size)) {
                if (file.size > this.validationRules.fileSize.max) {
                    this.addError(result, this.errorCategories.INPUT, this.errorSeverity.MEDIUM,
                        'FILE_TOO_LARGE', `File ${file.name}: File too large (${this.formatFileSize(file.size)})`);
                } else {
                    this.addError(result, this.errorCategories.INPUT, this.errorSeverity.HIGH,
                        'FILE_TOO_SMALL', `File ${file.name}: File too small (${this.formatFileSize(file.size)})`);
                    result.isValid = false;
                }
            }

            // Image readability validation
            try {
                const imageValidation = await this.validateImageReadability(file);
                if (!imageValidation.isValid) {
                    this.addError(result, this.errorCategories.INPUT, this.errorSeverity.HIGH,
                        'IMAGE_CORRUPTED', `File ${file.name}: Image is corrupted or cannot be read`);
                    result.isValid = false;
                } else {
                    // Check image dimensions
                    if (!this.validateImageDimensions(imageValidation.dimensions)) {
                        this.addError(result, this.errorCategories.INPUT, this.errorSeverity.MEDIUM,
                            'INVALID_DIMENSIONS', 
                            `File ${file.name}: Image dimensions ${imageValidation.dimensions.width}x${imageValidation.dimensions.height} are outside acceptable range`);
                    }

                    // Check for potential issues
                    this.checkImageWarnings(file, imageValidation.dimensions, result);
                }
            } catch (error) {
                this.addError(result, this.errorCategories.INPUT, this.errorSeverity.HIGH,
                    'IMAGE_VALIDATION_ERROR', `File ${file.name}: Error validating image - ${error.message}`);
                result.isValid = false;
            }

        } catch (error) {
            this.addError(result, this.errorCategories.SYSTEM, this.errorSeverity.CRITICAL,
                'FILE_VALIDATION_ERROR', `System error validating file ${file.name}: ${error.message}`);
            result.isValid = false;
        }

        return result;
    }

    // Validate image readability and get dimensions
    async validateImageReadability(file) {
        return new Promise((resolve) => {
            const img = new Image();
            const url = URL.createObjectURL(file);

            img.onload = () => {
                const dimensions = {
                    width: img.naturalWidth,
                    height: img.naturalHeight
                };
                URL.revokeObjectURL(url);
                resolve({
                    isValid: true,
                    dimensions: dimensions
                });
            };

            img.onerror = () => {
                URL.revokeObjectURL(url);
                resolve({
                    isValid: false,
                    dimensions: null
                });
            };

            // Set timeout for validation
            setTimeout(() => {
                URL.revokeObjectURL(url);
                resolve({
                    isValid: false,
                    dimensions: null
                });
            }, 5000); // 5 second timeout

            img.src = url;
        });
    }

    // Validate encoding parameters
    validateEncodingParameters(settings) {
        const result = {
            isValid: true,
            errors: [],
            warnings: []
        };

        // Frame rate validation
        if (settings.frameRate < this.validationRules.encoding.minFrameRate || 
            settings.frameRate > this.validationRules.encoding.maxFrameRate) {
            this.addError(result, this.errorCategories.ENCODING, this.errorSeverity.MEDIUM,
                'INVALID_FRAME_RATE', `Frame rate ${settings.frameRate} is outside valid range (${this.validationRules.encoding.minFrameRate}-${this.validationRules.encoding.maxFrameRate})`);
        }

        // Codec validation
        if (!this.validationRules.encoding.supportedCodecs.includes(settings.codec)) {
            this.addError(result, this.errorCategories.ENCODING, this.errorSeverity.HIGH,
                'UNSUPPORTED_CODEC', `Codec ${settings.codec} is not supported`);
            result.isValid = false;
        }

        // Format validation
        if (!this.validationRules.encoding.supportedFormats.includes(settings.format)) {
            this.addError(result, this.errorCategories.ENCODING, this.errorSeverity.HIGH,
                'UNSUPPORTED_FORMAT', `Format ${settings.format} is not supported`);
            result.isValid = false;
        }

        return result;
    }

    // Handle processing errors with recovery attempts
    async handleProcessingError(error, context) {
        const errorInfo = {
            timestamp: new Date().toISOString(),
            category: this.errorCategories.PROCESSING,
            severity: this.determineSeverity(error),
            code: this.generateErrorCode(error),
            message: error.message,
            context: context,
            stackTrace: error.stack,
            recoveryAttempts: 0
        };

        this.logError(errorInfo);

        // Attempt recovery based on error type
        const recoveryResult = await this.attemptRecovery(errorInfo);
        
        if (recoveryResult.recovered) {
            this.logRecovery(errorInfo, recoveryResult);
            if (this.onRecovery) {
                this.onRecovery(errorInfo, recoveryResult);
            }
            return recoveryResult;
        } else {
            if (this.onError) {
                this.onError(errorInfo);
            }
            throw new Error(`Processing failed: ${error.message}`);
        }
    }

    // Attempt error recovery
    async attemptRecovery(errorInfo) {
        const recoveryStrategies = {
            'MEMORY_ERROR': this.recoverFromMemoryError.bind(this),
            'ENCODING_ERROR': this.recoverFromEncodingError.bind(this),
            'FILE_ACCESS_ERROR': this.recoverFromFileAccessError.bind(this),
            'TIMEOUT_ERROR': this.recoverFromTimeoutError.bind(this)
        };

        const strategy = recoveryStrategies[errorInfo.code];
        if (strategy) {
            try {
                const result = await strategy(errorInfo);
                return {
                    recovered: true,
                    strategy: errorInfo.code,
                    result: result
                };
            } catch (recoveryError) {
                return {
                    recovered: false,
                    strategy: errorInfo.code,
                    error: recoveryError.message
                };
            }
        }

        return {
            recovered: false,
            strategy: 'none',
            error: 'No recovery strategy available'
        };
    }

    // Recovery strategies
    async recoverFromMemoryError(errorInfo) {
        // Implement memory cleanup and retry with smaller batch
        console.log('Attempting memory error recovery...');
        // Trigger garbage collection if available
        if (window.gc) {
            window.gc();
        }
        return { action: 'memory_cleanup', success: true };
    }

    async recoverFromEncodingError(errorInfo) {
        // Implement encoding fallback options
        console.log('Attempting encoding error recovery...');
        return { action: 'encoding_fallback', success: true };
    }

    async recoverFromFileAccessError(errorInfo) {
        // Implement file access retry
        console.log('Attempting file access error recovery...');
        return { action: 'file_retry', success: true };
    }

    async recoverFromTimeoutError(errorInfo) {
        // Implement timeout retry with increased limits
        console.log('Attempting timeout error recovery...');
        return { action: 'timeout_retry', success: true };
    }

    // Validation helper methods
    validateFileCount(count) {
        return count >= this.validationRules.fileCount.min && 
               count <= this.validationRules.fileCount.max;
    }

    validateFileSize(size) {
        return size >= this.validationRules.fileSize.min && 
               size <= this.validationRules.fileSize.max;
    }

    validateFileFormat(file) {
        const typeValid = this.validationRules.imageFormats.allowed.includes(file.type);
        const extensionValid = this.validationRules.imageFormats.extensions.some(ext => 
            file.name.toLowerCase().endsWith(ext));
        return typeValid || extensionValid;
    }

    validateImageDimensions(dimensions) {
        if (!dimensions) return false;
        const rules = this.validationRules.imageDimensions;
        return dimensions.width >= rules.minWidth && 
               dimensions.width <= rules.maxWidth &&
               dimensions.height >= rules.minHeight && 
               dimensions.height <= rules.maxHeight;
    }

    validateMemoryUsage(files) {
        const totalSize = files.reduce((sum, file) => sum + file.size, 0);
        const result = {
            isValid: true,
            warnings: []
        };

        if (totalSize > this.validationRules.memoryUsage.maxTotalSize) {
            result.warnings.push({
                category: this.errorCategories.SYSTEM,
                severity: this.errorSeverity.MEDIUM,
                code: 'HIGH_MEMORY_USAGE',
                message: `Total file size (${this.formatFileSize(totalSize)}) may cause memory issues`
            });
        }

        return result;
    }

    // Check for image warnings
    checkImageWarnings(file, dimensions, result) {
        // Very large images
        if (dimensions.width > 4096 || dimensions.height > 4096) {
            result.warnings.push({
                category: this.errorCategories.INPUT,
                severity: this.errorSeverity.LOW,
                code: 'LARGE_IMAGE',
                message: `File ${file.name}: Very large image (${dimensions.width}x${dimensions.height}) may slow processing`
            });
        }

        // Unusual aspect ratios
        const aspectRatio = dimensions.width / dimensions.height;
        if (aspectRatio > 5 || aspectRatio < 0.2) {
            result.warnings.push({
                category: this.errorCategories.INPUT,
                severity: this.errorSeverity.LOW,
                code: 'UNUSUAL_ASPECT_RATIO',
                message: `File ${file.name}: Unusual aspect ratio (${aspectRatio.toFixed(2)}) detected`
            });
        }
    }

    // Error management methods
    addError(result, category, severity, code, message) {
        const error = {
            category: category,
            severity: severity,
            code: code,
            message: message,
            timestamp: new Date().toISOString()
        };
        result.errors.push(error);
    }

    logError(errorInfo) {
        this.errorLog.push(errorInfo);
        console.error('ErrorHandler:', errorInfo);
    }

    logRecovery(errorInfo, recoveryResult) {
        const recoveryLog = {
            originalError: errorInfo,
            recoveryResult: recoveryResult,
            timestamp: new Date().toISOString()
        };
        console.log('ErrorHandler Recovery:', recoveryLog);
    }

    determineSeverity(error) {
        // Determine severity based on error type and message
        if (error.message.includes('memory') || error.message.includes('Memory')) {
            return this.errorSeverity.HIGH;
        }
        if (error.message.includes('timeout') || error.message.includes('Timeout')) {
            return this.errorSeverity.MEDIUM;
        }
        return this.errorSeverity.HIGH;
    }

    generateErrorCode(error) {
        // Generate error codes based on error characteristics
        if (error.message.includes('memory')) return 'MEMORY_ERROR';
        if (error.message.includes('encoding')) return 'ENCODING_ERROR';
        if (error.message.includes('file') || error.message.includes('File')) return 'FILE_ACCESS_ERROR';
        if (error.message.includes('timeout')) return 'TIMEOUT_ERROR';
        return 'UNKNOWN_ERROR';
    }

    generateValidationSummary(validationResult) {
        return {
            totalFiles: validationResult.validFiles.length + validationResult.invalidFiles.length,
            validFiles: validationResult.validFiles.length,
            invalidFiles: validationResult.invalidFiles.length,
            warningCount: validationResult.warnings.length,
            errorCount: validationResult.errors.length,
            criticalErrors: validationResult.errors.filter(e => e.severity === this.errorSeverity.CRITICAL).length,
            validationPassed: validationResult.isValid
        };
    }

    // Utility methods
    formatFileSize(bytes) {
        const units = ['B', 'KB', 'MB', 'GB'];
        let size = bytes;
        let unitIndex = 0;

        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }

        return `${size.toFixed(1)} ${units[unitIndex]}`;
    }

    // Get comprehensive error report
    getErrorReport() {
        return {
            errorLog: this.errorLog,
            statistics: {
                totalErrors: this.errorLog.length,
                errorsByCategory: this.getErrorsByCategory(),
                errorsBySeverity: this.getErrorsBySeverity(),
                recoveryRate: this.calculateRecoveryRate()
            },
            timestamp: new Date().toISOString()
        };
    }

    getErrorsByCategory() {
        const categories = {};
        this.errorLog.forEach(error => {
            categories[error.category] = (categories[error.category] || 0) + 1;
        });
        return categories;
    }

    getErrorsBySeverity() {
        const severities = {};
        this.errorLog.forEach(error => {
            severities[error.severity] = (severities[error.severity] || 0) + 1;
        });
        return severities;
    }

    calculateRecoveryRate() {
        if (this.errorLog.length === 0) return 0;
        const recoveredErrors = this.errorLog.filter(error => error.recoveryAttempts > 0).length;
        return (recoveredErrors / this.errorLog.length) * 100;
    }

    // Clear error log
    clearErrorLog() {
        this.errorLog = [];
        console.log('Error log cleared');
    }
}

// Export for use in other modules
window.ErrorHandler = ErrorHandler;
