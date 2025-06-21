// Video Tester Module - Step 3.2
// Implements automatic video playback testing and validation
// Part of Phase 3: Output and Validation

class VideoTester {
    constructor() {
        this.testResults = null;
        this.onTestStart = null;
        this.onTestProgress = null;
        this.onTestComplete = null;
        this.onTestError = null;
        
        this.testConfig = {
            maxTestDuration: 30000, // 30 seconds max test time
            playbackTimeout: 10000,  // 10 seconds timeout for playback start
            frameCheckInterval: 1000, // Check frames every second
            minPlaybackDuration: 2000, // Minimum 2 seconds of playback
            autoStartPlayback: true,
            validateMetadata: true,
            validatePlayback: true,
            validateFrames: false, // Disabled by default (performance)
            generateReport: true
        };
        
        console.log('VideoTester initialized');
    }
    
    // Update test configuration
    updateConfig(newConfig) {
        this.testConfig = { ...this.testConfig, ...newConfig };
        console.log('VideoTester config updated:', this.testConfig);
    }
    
    // Set callback functions
    setCallbacks(onStart, onProgress, onComplete, onError) {
        this.onTestStart = onStart;
        this.onTestProgress = onProgress;
        this.onTestComplete = onComplete;
        this.onTestError = onError;
    }
    
    // Main test function - comprehensive video validation
    async testVideo(videoBlob, filename, metadata = null) {
        try {
            this.testResults = this.initializeTestResults(filename, metadata);
            
            if (this.onTestStart) {
                this.onTestStart({
                    message: 'Starting video validation tests...',
                    filename: filename,
                    testConfig: this.testConfig
                });
            }
            
            // Step 1: Basic blob validation
            await this.validateVideoBlob(videoBlob);
            this.updateProgress('blob-validation', 'Video blob validation completed', 15);
            
            // Step 2: Create video element and test loading
            const videoElement = await this.createVideoElement(videoBlob);
            this.updateProgress('video-creation', 'Video element created and loaded', 30);
            
            // Step 3: Validate metadata if enabled
            if (this.testConfig.validateMetadata) {
                await this.validateVideoMetadata(videoElement, metadata);
                this.updateProgress('metadata-validation', 'Video metadata validation completed', 45);
            }
            
            // Step 4: Test playback if enabled
            if (this.testConfig.validatePlayback) {
                await this.validateVideoPlayback(videoElement);
                this.updateProgress('playback-validation', 'Video playback validation completed', 70);
            }
            
            // Step 5: Frame validation if enabled
            if (this.testConfig.validateFrames) {
                await this.validateFrameRendering(videoElement);
                this.updateProgress('frame-validation', 'Frame rendering validation completed', 85);
            }
            
            // Step 6: Generate final report
            this.finalizeTestResults(videoElement);
            this.updateProgress('test-complete', 'Video validation completed successfully', 100);
            
            // Clean up
            this.cleanupVideoElement(videoElement);
            
            if (this.onTestComplete) {
                this.onTestComplete(this.testResults);
            }
            
            return this.testResults;
            
        } catch (error) {
            console.error('Video testing failed:', error);
            
            const errorResult = {
                success: false,
                error: error.message,
                errorCode: error.code || 'TEST_FAILED',
                timestamp: new Date().toISOString(),
                filename: filename
            };
            
            if (this.onTestError) {
                this.onTestError(errorResult);
            }
            
            return errorResult;
        }
    }
    
    // Initialize test results structure
    initializeTestResults(filename, metadata) {
        return {
            filename: filename,
            testStartTime: Date.now(),
            testEndTime: null,
            success: false,
            tests: {
                blobValidation: { status: 'pending', details: null },
                videoCreation: { status: 'pending', details: null },
                metadataValidation: { status: 'pending', details: null },
                playbackValidation: { status: 'pending', details: null },
                frameValidation: { status: 'pending', details: null }
            },
            videoProperties: {},
            issues: [],
            warnings: [],
            recommendations: [],
            originalMetadata: metadata
        };
    }
    
    // Validate video blob
    async validateVideoBlob(videoBlob) {
        const test = this.testResults.tests.blobValidation;
        
        try {
            // Check blob validity
            if (!videoBlob || !(videoBlob instanceof Blob)) {
                throw new Error('Invalid video blob provided');
            }
            
            // Check blob size
            if (videoBlob.size === 0) {
                throw new Error('Video blob is empty');
            }
            
            // Check MIME type
            if (!videoBlob.type.startsWith('video/')) {
                this.testResults.warnings.push('Video blob MIME type may not be standard video format');
            }
            
            test.status = 'passed';
            test.details = {
                size: videoBlob.size,
                type: videoBlob.type,
                sizeFormatted: this.formatFileSize(videoBlob.size)
            };
            
            this.testResults.videoProperties.fileSize = videoBlob.size;
            this.testResults.videoProperties.mimeType = videoBlob.type;
            
        } catch (error) {
            test.status = 'failed';
            test.details = { error: error.message };
            throw error;
        }
    }
    
    // Create video element and load the blob
    async createVideoElement(videoBlob) {
        const test = this.testResults.tests.videoCreation;
        
        return new Promise((resolve, reject) => {
            try {
                const video = document.createElement('video');
                video.style.display = 'none';
                video.preload = 'metadata';
                video.controls = false;
                
                // Set up event listeners
                const cleanup = () => {
                    video.removeEventListener('loadedmetadata', onLoadedMetadata);
                    video.removeEventListener('error', onError);
                    video.removeEventListener('canplay', onCanPlay);
                };
                
                const onLoadedMetadata = () => {
                    test.status = 'passed';
                    test.details = {
                        duration: video.duration,
                        videoWidth: video.videoWidth,
                        videoHeight: video.videoHeight,
                        readyState: video.readyState
                    };
                    
                    this.testResults.videoProperties.duration = video.duration;
                    this.testResults.videoProperties.width = video.videoWidth;
                    this.testResults.videoProperties.height = video.videoHeight;
                    
                    cleanup();
                    resolve(video);
                };
                
                const onError = (event) => {
                    cleanup();
                    test.status = 'failed';
                    test.details = { 
                        error: 'Failed to load video metadata',
                        errorCode: video.error ? video.error.code : 'UNKNOWN',
                        errorMessage: video.error ? video.error.message : 'Unknown error'
                    };
                    reject(new Error(`Video loading failed: ${video.error ? video.error.message : 'Unknown error'}`));
                };
                
                const onCanPlay = () => {
                    // Video is ready to play, metadata should be loaded
                    if (!test.details) {
                        onLoadedMetadata();
                    }
                };
                
                // Add event listeners
                video.addEventListener('loadedmetadata', onLoadedMetadata);
                video.addEventListener('error', onError);
                video.addEventListener('canplay', onCanPlay);
                
                // Create object URL and set source
                const videoUrl = URL.createObjectURL(videoBlob);
                video.src = videoUrl;
                
                // Add to DOM temporarily (required for some browsers)
                document.body.appendChild(video);
                
                // Timeout fallback
                setTimeout(() => {
                    if (test.status === 'pending') {
                        cleanup();
                        test.status = 'failed';
                        test.details = { error: 'Video loading timeout' };
                        reject(new Error('Video loading timeout'));
                    }
                }, this.testConfig.playbackTimeout);
                
            } catch (error) {
                test.status = 'failed';
                test.details = { error: error.message };
                reject(error);
            }
        });
    }
    
    // Validate video metadata
    async validateVideoMetadata(videoElement, originalMetadata) {
        const test = this.testResults.tests.metadataValidation;
        
        try {
            const detectedProperties = {
                duration: videoElement.duration,
                width: videoElement.videoWidth,
                height: videoElement.videoHeight,
                aspectRatio: (videoElement.videoWidth / videoElement.videoHeight).toFixed(3),
                readyState: videoElement.readyState
            };
            
            // Compare with original metadata if provided
            const validation = {
                properties: detectedProperties,
                comparison: null,
                issues: []
            };
            
            if (originalMetadata) {
                validation.comparison = this.compareMetadata(detectedProperties, originalMetadata);
                
                // Check for significant discrepancies
                if (validation.comparison.durationDifference > 1) { // More than 1 second difference
                    validation.issues.push('Duration mismatch detected');
                }
                
                if (validation.comparison.dimensionMismatch) {
                    validation.issues.push('Video dimensions do not match expected values');
                }
            }
            
            // Validate basic properties
            if (!detectedProperties.duration || detectedProperties.duration <= 0) {
                validation.issues.push('Invalid or zero duration');
            }
            
            if (!detectedProperties.width || !detectedProperties.height) {
                validation.issues.push('Invalid video dimensions');
            }
            
            if (detectedProperties.width < 16 || detectedProperties.height < 16) {
                validation.issues.push('Video dimensions are unusually small');
            }
            
            test.status = validation.issues.length === 0 ? 'passed' : 'warning';
            test.details = validation;
            
            if (validation.issues.length > 0) {
                this.testResults.warnings.push(...validation.issues);
            }
            
        } catch (error) {
            test.status = 'failed';
            test.details = { error: error.message };
            throw error;
        }
    }
    
    // Validate video playback
    async validateVideoPlayback(videoElement) {
        const test = this.testResults.tests.playbackValidation;
        
        return new Promise((resolve, reject) => {
            try {
                const playbackTest = {
                    startTime: Date.now(),
                    playbackStarted: false,
                    playbackProgressed: false,
                    playbackDuration: 0,
                    frameUpdates: 0,
                    errors: []
                };
                
                let playbackTimer = null;
                let progressCheckTimer = null;
                let lastCurrentTime = 0;
                
                const cleanup = () => {
                    if (playbackTimer) clearTimeout(playbackTimer);
                    if (progressCheckTimer) clearInterval(progressCheckTimer);
                    
                    videoElement.removeEventListener('play', onPlay);
                    videoElement.removeEventListener('timeupdate', onTimeUpdate);
                    videoElement.removeEventListener('error', onPlaybackError);
                    videoElement.removeEventListener('ended', onEnded);
                    
                    try {
                        videoElement.pause();
                    } catch (e) {
                        // Ignore pause errors during cleanup
                    }
                };
                
                const finishTest = (success, error = null) => {
                    cleanup();
                    playbackTest.playbackDuration = Date.now() - playbackTest.startTime;
                    
                    if (success) {
                        test.status = 'passed';
                        test.details = playbackTest;
                        resolve();
                    } else {
                        test.status = 'failed';
                        test.details = { ...playbackTest, error: error };
                        reject(new Error(error));
                    }
                };
                
                const onPlay = () => {
                    playbackTest.playbackStarted = true;
                    
                    // Check for progress updates
                    progressCheckTimer = setInterval(() => {
                        if (videoElement.currentTime > lastCurrentTime) {
                            playbackTest.playbackProgressed = true;
                            playbackTest.frameUpdates++;
                            lastCurrentTime = videoElement.currentTime;
                        }
                        
                        // If we've played for minimum duration, consider it successful
                        if (playbackTest.playbackProgressed && 
                            (Date.now() - playbackTest.startTime) >= this.testConfig.minPlaybackDuration) {
                            finishTest(true);
                        }
                    }, this.testConfig.frameCheckInterval);
                };
                
                const onTimeUpdate = () => {
                    if (videoElement.currentTime > lastCurrentTime) {
                        playbackTest.playbackProgressed = true;
                        playbackTest.frameUpdates++;
                        lastCurrentTime = videoElement.currentTime;
                    }
                };
                
                const onPlaybackError = (event) => {
                    const errorMsg = `Playback error: ${videoElement.error ? videoElement.error.message : 'Unknown error'}`;
                    playbackTest.errors.push(errorMsg);
                    finishTest(false, errorMsg);
                };
                
                const onEnded = () => {
                    // Video ended naturally, this is good
                    if (playbackTest.playbackProgressed) {
                        finishTest(true);
                    } else {
                        finishTest(false, 'Video ended without detectable playback progress');
                    }
                };
                
                // Set up event listeners
                videoElement.addEventListener('play', onPlay);
                videoElement.addEventListener('timeupdate', onTimeUpdate);
                videoElement.addEventListener('error', onPlaybackError);
                videoElement.addEventListener('ended', onEnded);
                
                // Start playback test
                const playPromise = videoElement.play();
                
                if (playPromise) {
                    playPromise.catch((error) => {
                        finishTest(false, `Failed to start playback: ${error.message}`);
                    });
                }
                
                // Overall timeout
                playbackTimer = setTimeout(() => {
                    if (playbackTest.playbackProgressed) {
                        finishTest(true);
                    } else {
                        finishTest(false, 'Playback validation timeout - no progress detected');
                    }
                }, this.testConfig.maxTestDuration);
                
            } catch (error) {
                test.status = 'failed';
                test.details = { error: error.message };
                reject(error);
            }
        });
    }
    
    // Validate frame rendering (optional, performance-intensive)
    async validateFrameRendering(videoElement) {
        const test = this.testResults.tests.frameValidation;
        
        try {
            // Create canvas for frame analysis
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            
            canvas.width = videoElement.videoWidth;
            canvas.height = videoElement.videoHeight;
            
            const frameAnalysis = {
                framesAnalyzed: 0,
                uniqueFrames: 0,
                frameHashes: new Set(),
                avgFrameBrightness: [],
                frameErrors: []
            };
            
            // Analyze frames at different time positions
            const timePositions = [0, 0.25, 0.5, 0.75, 1.0]; // Start, quarter, middle, three-quarter, end
            
            for (const position of timePositions) {
                try {
                    videoElement.currentTime = videoElement.duration * position;
                    
                    // Wait for seek to complete
                    await new Promise(resolve => {
                        const onSeeked = () => {
                            videoElement.removeEventListener('seeked', onSeeked);
                            resolve();
                        };
                        videoElement.addEventListener('seeked', onSeeked);
                        
                        // Fallback timeout
                        setTimeout(resolve, 1000);
                    });
                    
                    // Draw frame to canvas
                    ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
                    
                    // Calculate frame hash for uniqueness check
                    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    const frameHash = this.calculateFrameHash(imageData);
                    
                    frameAnalysis.framesAnalyzed++;
                    frameAnalysis.frameHashes.add(frameHash);
                    
                    // Calculate average brightness
                    const brightness = this.calculateFrameBrightness(imageData);
                    frameAnalysis.avgFrameBrightness.push(brightness);
                    
                } catch (error) {
                    frameAnalysis.frameErrors.push(`Frame at ${position}: ${error.message}`);
                }
            }
            
            frameAnalysis.uniqueFrames = frameAnalysis.frameHashes.size;
            frameAnalysis.avgBrightness = frameAnalysis.avgFrameBrightness.reduce((a, b) => a + b, 0) / frameAnalysis.avgFrameBrightness.length;
            
            // Validate results
            const issues = [];
            if (frameAnalysis.uniqueFrames < 2) {
                issues.push('Too few unique frames detected - video may be static');
            }
            
            if (frameAnalysis.avgBrightness < 10) {
                issues.push('Video appears very dark - possible rendering issue');
            }
            
            if (frameAnalysis.frameErrors.length > 0) {
                issues.push(`Frame rendering errors: ${frameAnalysis.frameErrors.length}`);
            }
            
            test.status = issues.length === 0 ? 'passed' : 'warning';
            test.details = frameAnalysis;
            
            if (issues.length > 0) {
                this.testResults.warnings.push(...issues);
            }
            
            // Clean up canvas
            canvas.remove();
            
        } catch (error) {
            test.status = 'failed';
            test.details = { error: error.message };
            throw error;
        }
    }
    
    // Finalize test results
    finalizeTestResults(videoElement) {
        this.testResults.testEndTime = Date.now();
        this.testResults.testDuration = this.testResults.testEndTime - this.testResults.testStartTime;
        
        // Determine overall success
        const failedTests = Object.values(this.testResults.tests).filter(test => test.status === 'failed');
        this.testResults.success = failedTests.length === 0;
        
        // Generate recommendations
        this.generateRecommendations();
        
        // Add final video properties
        this.testResults.videoProperties.finalDuration = videoElement.duration;
        this.testResults.videoProperties.finalDimensions = `${videoElement.videoWidth}x${videoElement.videoHeight}`;
        this.testResults.videoProperties.aspectRatio = (videoElement.videoWidth / videoElement.videoHeight).toFixed(3);
    }
    
    // Generate recommendations based on test results
    generateRecommendations() {
        const recommendations = [];
        
        // Check for common issues and provide recommendations
        if (this.testResults.videoProperties.duration < 1) {
            recommendations.push('Video duration is very short - consider adding more images or reducing frame rate');
        }
        
        if (this.testResults.videoProperties.width < 100 || this.testResults.videoProperties.height < 100) {
            recommendations.push('Video dimensions are small - consider using higher resolution source images');
        }
        
        if (this.testResults.warnings.length > 0) {
            recommendations.push('Review warnings for potential quality improvements');
        }
        
        const failedTests = Object.values(this.testResults.tests).filter(test => test.status === 'failed');
        if (failedTests.length > 0) {
            recommendations.push('Some validation tests failed - video may not play correctly in all environments');
        }
        
        this.testResults.recommendations = recommendations;
    }
    
    // Helper functions
    updateProgress(step, message, percentage) {
        if (this.onTestProgress) {
            this.onTestProgress({
                step: step,
                message: message,
                percentage: percentage,
                timestamp: new Date().toISOString()
            });
        }
    }
    
    compareMetadata(detected, original) {
        const comparison = {
            durationDifference: Math.abs(detected.duration - (original.duration?.seconds || 0)),
            dimensionMismatch: detected.width !== original.dimensions?.width || detected.height !== original.dimensions?.height,
            aspectRatioMatch: Math.abs(parseFloat(detected.aspectRatio) - parseFloat(original.dimensions?.aspectRatio || '0')) < 0.01
        };
        
        return comparison;
    }
    
    calculateFrameHash(imageData) {
        // Simple hash based on pixel data
        let hash = 0;
        const data = imageData.data;
        for (let i = 0; i < data.length; i += 100) { // Sample every 100th pixel for performance
            hash = ((hash << 5) - hash + data[i]) & 0xffffffff;
        }
        return hash.toString(36);
    }
    
    calculateFrameBrightness(imageData) {
        const data = imageData.data;
        let totalBrightness = 0;
        let pixelCount = 0;
        
        for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            const brightness = (r * 0.299 + g * 0.587 + b * 0.114);
            totalBrightness += brightness;
            pixelCount++;
        }
        
        return totalBrightness / pixelCount;
    }
    
    cleanupVideoElement(videoElement) {
        try {
            if (videoElement.src) {
                URL.revokeObjectURL(videoElement.src);
            }
            if (videoElement.parentNode) {
                videoElement.parentNode.removeChild(videoElement);
            }
        } catch (error) {
            console.warn('Error cleaning up video element:', error);
        }
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Get test configuration
    getConfig() {
        return { ...this.testConfig };
    }
    
    // Get last test results
    getLastResults() {
        return this.testResults;
    }
    
    // Quick test function for basic validation only
    async quickTest(videoBlob, filename) {
        const quickConfig = {
            validateMetadata: true,
            validatePlayback: false,
            validateFrames: false,
            maxTestDuration: 5000
        };
        
        const originalConfig = this.testConfig;
        this.updateConfig(quickConfig);
        
        try {
            const result = await this.testVideo(videoBlob, filename);
            return result;
        } finally {
            this.testConfig = originalConfig;
        }
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.VideoTester = VideoTester;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = VideoTester;
}
