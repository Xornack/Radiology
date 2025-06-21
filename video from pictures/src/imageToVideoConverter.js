// Image to Video Conversion Module - Step 2.2
// Implements core image sequence to MP4 conversion logic
// Part of Phase 2: Video Generation Engine

class ImageToVideoConverter {
    constructor() {
        this.videoEncoder = null;
        this.conversionSettings = {
            frameRate: 15,
            quality: 'medium',
            resolution: 'original',
            codec: 'vp8',
            format: 'webm'
        };
        this.onProgress = null;
        this.onError = null;
        this.onComplete = null;
        
        // Enhanced progress tracking (Step 2.3)
        this.progressTracker = new ProgressTracker();
        this.startTime = null;
        
        // Enhanced error handling (Step 2.4)
        this.errorHandler = new ErrorHandler();
        
        console.log('ImageToVideoConverter initialized with enhanced progress tracking and error handling');
    }

    // Set callback functions for progress tracking
    setCallbacks(onProgress, onError, onComplete) {
        this.onProgress = onProgress;
        this.onError = onError;
        this.onComplete = onComplete;
        
        // Set up enhanced progress tracker callbacks (Step 2.3)
        this.progressTracker.setCallbacks(
            (progress) => {
                // Enhanced progress update with detailed information
                if (this.onProgress) {
                    this.onProgress({
                        ...progress,
                        step: 'image-to-video-conversion',
                        enhanced: true
                    });
                }
            },
            (step) => {
                // Step-by-step progress updates
                if (this.onProgress) {
                    this.onProgress({
                        message: `${step.stepName || step.currentStep}`,
                        percentage: Math.round((step.completedSteps / step.totalSteps) * 100),
                        step: 'step-progress',
                        stepInfo: step
                    });
                }
            },
            (eta) => {
                // ETA updates
                if (this.onProgress) {
                    this.onProgress({
                        message: `ETA: ${eta.formatted}`,
                        percentage: null,
                        step: 'eta-update',
                        eta: eta
                    });
                }
            },
            (statistics) => {
                // Statistics updates
                if (this.onProgress) {
                    this.onProgress({
                        message: 'Processing statistics updated',
                        percentage: null,
                        step: 'statistics-update',
                        statistics: statistics
                    });
                }
            }
        );
        
        // Set up error handler callbacks (Step 2.4)
        this.errorHandler.setCallbacks(
            (error) => {
                // Error callback
                if (this.onError) {
                    this.onError({
                        error: error.message,
                        category: error.category,
                        severity: error.severity,
                        code: error.code,
                        timestamp: error.timestamp
                    });
                }
            },
            (warning) => {
                // Warning callback
                if (this.onProgress) {
                    this.onProgress({
                        message: `Warning: ${warning.message}`,
                        percentage: null,
                        step: 'warning',
                        warning: warning
                    });
                }
            },
            (recovery) => {
                // Recovery callback
                if (this.onProgress) {
                    this.onProgress({
                        message: `Recovered from error: ${recovery.strategy}`,
                        percentage: null,
                        step: 'recovery',
                        recovery: recovery
                    });
                }
            }
        );
    }

    // Update conversion settings
    updateSettings(newSettings) {
        this.conversionSettings = {
            ...this.conversionSettings,
            ...newSettings
        };
        console.log('Conversion settings updated:', this.conversionSettings);
    }

    // Main conversion method
    async convertImagesToVideo(images, outputFilename = null) {
        try {
            this.startTime = Date.now();
            
            // Enhanced input validation (Step 2.4)
            this.updateProgress('Validating input files...', 0);
            const validationResult = await this.errorHandler.validateInputFiles(images);
            
            if (!validationResult.isValid) {
                const errorSummary = validationResult.summary;
                throw new Error(`Input validation failed: ${errorSummary.errorCount} errors, ${errorSummary.criticalErrors} critical errors`);
            }
            
            // Use validated files
            const validatedImages = validationResult.validFiles;
            
            // Report validation warnings if any
            if (validationResult.warnings.length > 0) {
                this.updateProgress(`Validation completed with ${validationResult.warnings.length} warnings`, 5);
            }
            
            // Validate encoding settings (Step 2.4)
            console.log('Current conversion settings:', this.conversionSettings);
            const encodingValidation = this.errorHandler.validateEncodingParameters(this.conversionSettings);
            console.log('Validation result:', encodingValidation);
            if (!encodingValidation.isValid) {
                throw new Error(`Invalid encoding settings: ${encodingValidation.errors.map(e => e.message).join(', ')}`);
            }
            
            // Initialize enhanced progress tracking (Step 2.3)
            const stepDefinitions = [
                { id: 'validation', name: 'Image Validation', estimatedDuration: 2000, weight: 0.1 },
                { id: 'processing', name: 'Image Processing', estimatedDuration: 3000, weight: 0.15 },
                { id: 'encoder-init', name: 'Video Encoder Initialization', estimatedDuration: 5000, weight: 0.2 },
                { id: 'encoding', name: 'Video Encoding', estimatedDuration: 15000, weight: 0.5 },
                { id: 'finalization', name: 'Output Finalization', estimatedDuration: 1000, weight: 0.05 }
            ];
            
            this.progressTracker.startTracking(5, validatedImages.length, stepDefinitions);
            this.updateProgress('Starting image to video conversion...', 10);
            
            // Step 1: Validate input images (already done above)
            this.progressTracker.startStep('validation', 'Image Validation', validatedImages.length);
            this.progressTracker.completeStep();

            // Step 2: Process and prepare images with error handling
            this.progressTracker.startStep('processing', 'Image Processing', validatedImages.length);
            const processedImages = await this.processImagesWithErrorHandling(validatedImages);
            this.progressTracker.completeStep();

            // Step 3: Initialize video encoder with error handling
            this.progressTracker.startStep('encoder-init', 'Video Encoder Initialization', 1);
            if (!this.videoEncoder) {
                console.log('Creating VideoEncoder...');
                console.log('VideoEncoder type:', typeof VideoEncoder);
                console.log('VideoEncoder name:', VideoEncoder ? VideoEncoder.name : 'undefined');
                console.log('VideoEncoder constructor:', VideoEncoder);
                
                try {
                    // Always use CustomVideoEncoder approach - create with null canvas parameter
                    // The CustomVideoEncoder will create its own canvas if needed
                    this.videoEncoder = new VideoEncoder(null);
                    console.log('VideoEncoder created successfully:', this.videoEncoder.constructor.name);
                } catch (error) {
                    console.error('VideoEncoder creation failed:', error);
                    
                    // Direct fallback to CustomVideoEncoder if global override failed
                    if (typeof CustomVideoEncoder !== 'undefined') {
                        console.log('Trying direct CustomVideoEncoder fallback...');
                        this.videoEncoder = new CustomVideoEncoder(null);
                        console.log('CustomVideoEncoder created successfully');
                    } else {
                        // Last resort: throw error with helpful message
                        const errorMessage = `VideoEncoder initialization failed. Original error: ${error.message}. Please ensure customVideoEncoder.js is loaded correctly.`;
                        throw new Error(errorMessage);
                    }
                }
            }
            
            await this.initializeEncoderWithErrorHandling();
            this.progressTracker.completeStep();

            // Step 4: Create video from processed images with error handling
            this.progressTracker.startStep('encoding', 'Video Encoding', processedImages.length);
            
            const videoResult = await this.encodeVideoWithErrorHandling(processedImages);
            this.progressTracker.completeStep();

            // Step 5: Generate output filename and finalize
            this.progressTracker.startStep('finalization', 'Output Finalization', 1);
            const finalFilename = outputFilename || this.generateOutputFilename(images);
            
            // Prepare final result with enhanced metadata
            const result = {
                success: true,
                videoBlob: videoResult.blob,
                filename: finalFilename,
                metadata: {
                    inputImageCount: validatedImages.length,
                    processedImageCount: processedImages.length,
                    validationResult: validationResult.summary,
                    videoSize: videoResult.size,
                    duration: this.calculateDuration(processedImages.length),
                    settings: this.conversionSettings,
                    dimensions: await this.getVideoDimensions(processedImages[0]),
                    createdAt: new Date().toISOString()
                },
                statistics: {
                    totalProcessingTime: Date.now() - this.startTime,
                    averageImageSize: this.calculateAverageImageSize(validatedImages),
                    compressionRatio: this.calculateCompressionRatio(validatedImages, videoResult.size)
                },
                // Enhanced progress tracking results (Step 2.3)
                enhancedStats: this.progressTracker.completeTracking(),
                // Error handling report (Step 2.4)
                errorReport: this.errorHandler.getErrorReport()
            };

            this.progressTracker.updateStepProgress(1, finalFilename, 'Finalizing output');
            this.progressTracker.completeStep();
            
            this.updateProgress('Conversion completed successfully', 100);
            
            if (this.onComplete) {
                this.onComplete(result);
            }

            return result;

        } catch (error) {
            console.error('Image to video conversion failed:', error);
            
            // Enhanced error handling (Step 2.4)
            try {
                const handledError = await this.errorHandler.handleProcessingError(error, {
                    step: 'conversion',
                    images: images.length,
                    settings: this.conversionSettings
                });
                
                // If error was recovered, return the recovery result
                if (handledError.recovered) {
                    const errorResult = {
                        success: true,
                        recovered: true,
                        recoveryInfo: handledError,
                        message: 'Conversion completed with error recovery',
                        timestamp: new Date().toISOString()
                    };
                    
                    if (this.onComplete) {
                        this.onComplete(errorResult);
                    }
                    
                    return errorResult;
                }
            } catch (recoveryError) {
                // Recovery failed, proceed with original error handling
                console.error('Error recovery failed:', recoveryError);
            }
            
            const errorResult = {
                success: false,
                error: error.message,
                errorReport: this.errorHandler.getErrorReport(),
                timestamp: new Date().toISOString()
            };

            if (this.onError) {
                this.onError(errorResult);
            }

            throw error;
        } finally {
            // Cleanup
            if (this.videoEncoder) {
                await this.videoEncoder.terminate();
            }
        }
    }

    // Process images with error handling (Step 2.4)
    async processImagesWithErrorHandling(images) {
        const processedImages = [];

        for (let i = 0; i < images.length; i++) {
            const image = images[i];
            
            try {
                // Update progress for current image
                this.progressTracker.updateStepProgress(i + 1, image.name || `image_${i + 1}`, `Processing ${image.name || `image ${i + 1}`}`);
                
                // For now, we pass images through without modification
                // In future versions, we might add resizing, format conversion, etc.
                processedImages.push(image);

            } catch (error) {
                console.warn(`Error processing image ${i + 1}:`, error);
                
                // Try error recovery
                try {
                    await this.errorHandler.handleProcessingError(error, {
                        step: 'image-processing',
                        imageIndex: i,
                        imageName: image.name
                    });
                    // If recovery succeeds, continue with other images
                } catch (recoveryError) {
                    // Log but continue with other images
                    console.warn(`Failed to recover from image processing error: ${recoveryError.message}`);
                }
            }
        }

        return processedImages;
    }

    // Initialize encoder with error handling (Step 2.4)
    async initializeEncoderWithErrorHandling() {
        try {
            await this.videoEncoder.initialize(
                (progress) => {
                    // Map encoder progress to current step
                    this.progressTracker.updateStepProgress(null, 'Video encoder initialization', progress.message);
                },
                (log) => {
                    console.log('Video encoder log:', log);
                }
            );
        } catch (error) {
            // Try error recovery for encoder initialization
            const handledError = await this.errorHandler.handleProcessingError(error, {
                step: 'encoder-initialization',
                encoderType: 'Canvas+MediaRecorder'
            });
            
            if (!handledError.recovered) {
                throw new Error(`Failed to initialize video encoder: ${error.message}`);
            }
        }
    }

    // Encode video with error handling (Step 2.4)
    async encodeVideoWithErrorHandling(processedImages) {
        try {
            const videoResult = await this.videoEncoder.createVideoFromImages(
                processedImages, 
                this.conversionSettings,
                // Enhanced progress callback for encoding
                (encodingProgress) => {
                    this.progressTracker.updateStepProgress(
                        encodingProgress.currentFrame,
                        `Frame ${encodingProgress.currentFrame}/${encodingProgress.totalFrames}`,
                        `Encoding: ${encodingProgress.message || ''}`
                    );
                }
            );
            
            return videoResult;
            
        } catch (error) {
            // Try error recovery for video encoding
            const handledError = await this.errorHandler.handleProcessingError(error, {
                step: 'video-encoding',
                imageCount: processedImages.length,
                settings: this.conversionSettings
            });
            
            if (handledError.recovered) {
                // Retry encoding with recovered state
                return await this.videoEncoder.createVideoFromImages(
                    processedImages, 
                    this.conversionSettings
                );
            } else {
                throw new Error(`Video encoding failed: ${error.message}`);
            }
        }
    }

    // Validate input images
    async validateImages(images) {
        const validImages = [];
        const errors = [];

        for (let i = 0; i < images.length; i++) {
            const image = images[i];
            
            try {
                // Update progress for current image
                this.progressTracker.updateStepProgress(i + 1, image.name || `image_${i + 1}`, `Validating ${image.name || `image ${i + 1}`}`);
                
                // Check if it's a valid file
                if (!(image instanceof File) && !(image instanceof Blob)) {
                    throw new Error(`Invalid image format at index ${i}`);
                }

                // Validate JPEG format
                if (!this.isValidJPEG(image)) {
                    throw new Error(`Invalid JPEG file: ${image.name}`);
                }

                // Check file size (reasonable limits)
                if (image.size > 50 * 1024 * 1024) { // 50MB limit
                    console.warn(`Large image file: ${image.name} (${(image.size / 1024 / 1024).toFixed(1)} MB)`);
                }

                // Try to load the image to verify it's readable
                await this.validateImageReadability(image);

                validImages.push(image);

            } catch (error) {
                console.warn(`Skipping invalid image ${i + 1}:`, error.message);
                errors.push({
                    index: i,
                    filename: image.name || `image_${i + 1}`,
                    error: error.message
                });
            }
        }

        if (validImages.length === 0) {
            throw new Error('No valid images found for conversion');
        }

        if (errors.length > 0) {
            console.warn(`Skipped ${errors.length} invalid images:`, errors);
        }

        return validImages;
    }

    // Check if file is valid JPEG
    isValidJPEG(file) {
        const validTypes = ['image/jpeg', 'image/jpg'];
        const validExtensions = ['.jpg', '.jpeg'];
        
        const hasValidType = validTypes.includes(file.type);
        const hasValidExtension = validExtensions.some(ext => 
            file.name.toLowerCase().endsWith(ext)
        );

        return hasValidType || hasValidExtension;
    }

    // Validate that image can be read
    async validateImageReadability(imageFile) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            const url = URL.createObjectURL(imageFile);

            img.onload = () => {
                URL.revokeObjectURL(url);
                resolve(true);
            };

            img.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error('Image cannot be loaded or is corrupted'));
            };

            img.src = url;
        });
    }

    // Process images for video conversion
    async processImages(images) {
        const processedImages = [];

        for (let i = 0; i < images.length; i++) {
            const image = images[i];
            
            try {
                // Update progress for current image
                this.progressTracker.updateStepProgress(i + 1, image.name || `image_${i + 1}`, `Processing ${image.name || `image ${i + 1}`}`);
                
                // For now, we pass images through without modification
                // In future versions, we might add resizing, format conversion, etc.
                processedImages.push(image);

            } catch (error) {
                console.warn(`Error processing image ${i + 1}:`, error);
                // Continue with other images
            }
        }

        return processedImages;
    }

    // Generate output filename based on input images
    generateOutputFilename(images) {
        // Extract common folder name or create generic name
        let baseName = 'medical_images';
        
        if (images.length > 0 && images[0].webkitRelativePath) {
            const path = images[0].webkitRelativePath;
            const folderName = path.split('/')[0];
            baseName = folderName || 'medical_images';
        }

        // Add timestamp for uniqueness
        const timestamp = new Date().toISOString()
            .slice(0, 19)
            .replace(/[:.]/g, '-');

        return `${baseName}_${timestamp}.webm`;
    }

    // Calculate video duration based on frame count and frame rate
    calculateDuration(frameCount) {
        const durationSeconds = frameCount / this.conversionSettings.frameRate;
        return {
            seconds: durationSeconds,
            formatted: this.formatDuration(durationSeconds)
        };
    }

    // Format duration in human-readable format
    formatDuration(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = (seconds % 60).toFixed(1);
        
        if (minutes > 0) {
            return `${minutes}m ${remainingSeconds}s`;
        } else {
            return `${remainingSeconds}s`;
        }
    }

    // Get video dimensions from first image
    async getVideoDimensions(firstImage) {
        return new Promise((resolve) => {
            const img = new Image();
            const url = URL.createObjectURL(firstImage);

            img.onload = () => {
                const dimensions = {
                    width: img.naturalWidth,
                    height: img.naturalHeight,
                    aspectRatio: (img.naturalWidth / img.naturalHeight).toFixed(2)
                };
                URL.revokeObjectURL(url);
                resolve(dimensions);
            };

            img.onerror = () => {
                URL.revokeObjectURL(url);
                // Return default dimensions if image can't be loaded
                resolve({
                    width: 1024,
                    height: 768,
                    aspectRatio: '1.33'
                });
            };

            img.src = url;
        });
    }

    // Calculate average image size
    calculateAverageImageSize(images) {
        const totalSize = images.reduce((sum, img) => sum + img.size, 0);
        return {
            bytes: Math.round(totalSize / images.length),
            formatted: this.formatFileSize(totalSize / images.length)
        };
    }

    // Calculate compression ratio
    calculateCompressionRatio(images, videoSize) {
        const totalImageSize = images.reduce((sum, img) => sum + img.size, 0);
        const ratio = totalImageSize / videoSize;
        
        return {
            ratio: ratio.toFixed(2),
            percentage: ((1 - videoSize / totalImageSize) * 100).toFixed(1),
            originalSize: this.formatFileSize(totalImageSize),
            compressedSize: this.formatFileSize(videoSize)
        };
    }

    // Format file size in human-readable format
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

    // Update progress and notify callback
    updateProgress(message, percentage) {
        if (this.onProgress) {
            this.onProgress({
                message: message,
                percentage: Math.round(percentage),
                step: 'image-to-video-conversion'
            });
        }
        
        console.log(`Conversion Progress: ${message} (${Math.round(percentage)}%)`);
    }

    // Get conversion statistics
    getConversionStats() {
        return {
            settings: this.conversionSettings,
            capabilities: this.videoEncoder ? this.videoEncoder.getCapabilities() : null,
            supportedFormats: ['mp4'],
            supportedCodecs: ['libx264', 'libx265'],
            qualityLevels: ['high', 'medium', 'low']
        };
    }

    // Cleanup resources
    async cleanup() {
        if (this.videoEncoder) {
            await this.videoEncoder.terminate();
            this.videoEncoder = null;
        }
        
        console.log('ImageToVideoConverter cleanup completed');
    }
}

// Export for use in other modules
window.ImageToVideoConverter = ImageToVideoConverter;
