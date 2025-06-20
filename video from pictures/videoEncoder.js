// Video Encoder Module - Step 2.1
// Implements browser-based video encoding using FFmpeg.js
// Part of Phase 2: Video Generation Engine

class VideoEncoder {
    constructor() {
        this.ffmpeg = null;
        this.isLoaded = false;
        this.loadingProgress = 0;
        this.onProgress = null;
        this.onLog = null;
        
        console.log('VideoEncoder initialized');
    }

    // Initialize and load FFmpeg.js
    async initialize(onProgress = null, onLog = null) {
        this.onProgress = onProgress;
        this.onLog = onLog;
        
        try {
            // Update progress
            this.updateProgress('Initializing video encoder...', 0);
            
            // Check for SharedArrayBuffer (required for optimal performance)
            const hasSharedArrayBuffer = typeof SharedArrayBuffer !== 'undefined';
            
            if (!hasSharedArrayBuffer) {
                this.updateProgress('SharedArrayBuffer not available - using fallback mode', 10);
                console.warn('SharedArrayBuffer not available. FFmpeg.js will use slower fallback mode.');
                
                if (this.onLog) {
                    this.onLog('WARNING: SharedArrayBuffer disabled. Video encoding will be slower but functional.');
                }
            }
            
            // Load FFmpeg from CDN
            if (!window.FFmpeg) {
                await this.loadFFmpegScript();
            }
            
            this.updateProgress('Creating FFmpeg instance...', 20);
            
            // Create FFmpeg instance
            const { FFmpeg } = window.FFmpeg;
            this.ffmpeg = new FFmpeg();
            
            // Set up logging
            this.ffmpeg.on('log', ({ message }) => {
                if (this.onLog) {
                    this.onLog(message);
                }
                console.log('FFmpeg:', message);
            });
            
            // Set up progress tracking
            this.ffmpeg.on('progress', ({ progress, time }) => {
                const percentage = Math.round(progress * 100);
                this.updateProgress(`Encoding video... ${percentage}%`, 50 + (percentage * 0.4));
            });
            
            this.updateProgress('Loading FFmpeg core...', 40);
            
            // Load FFmpeg core
            await this.ffmpeg.load();
            
            this.isLoaded = true;
            this.updateProgress('Video encoder ready', 100);
            
            console.log('FFmpeg.js loaded successfully');
            return true;
            
        } catch (error) {
            console.error('Failed to initialize FFmpeg:', error);
            throw new Error(`Video encoder initialization failed: ${error.message}`);
        }
    }

    // Load FFmpeg.js script dynamically
    async loadFFmpegScript() {
        return new Promise((resolve, reject) => {
            // Check if already loaded
            if (window.FFmpeg) {
                resolve();
                return;
            }
            
            const script = document.createElement('script');
            script.src = 'https://unpkg.com/@ffmpeg/ffmpeg@0.12.7/dist/umd/ffmpeg.js';
            script.crossOrigin = 'anonymous';
            
            script.onload = () => {
                console.log('FFmpeg.js script loaded');
                resolve();
            };
            
            script.onerror = () => {
                reject(new Error('Failed to load FFmpeg.js script'));
            };
            
            document.head.appendChild(script);
        });
    }

    // Convert image sequence to MP4 video
    async createVideoFromImages(images, options = {}) {
        if (!this.isLoaded) {
            throw new Error('Video encoder not initialized. Call initialize() first.');
        }

        // Default video settings as per TR005
        const settings = {
            frameRate: options.frameRate || 15,
            quality: options.quality || 'medium', // high, medium, low
            resolution: options.resolution || 'original',
            codec: options.codec || 'libx264',
            format: options.format || 'mp4',
            ...options
        };

        try {
            this.updateProgress('Preparing images for encoding...', 0);
            
            // Write input images to FFmpeg file system
            await this.writeImagesToFFmpeg(images);
            
            this.updateProgress('Configuring video parameters...', 20);
            
            // Build FFmpeg command
            const command = this.buildFFmpegCommand(images.length, settings);
            
            this.updateProgress('Starting video encoding...', 30);
            
            // Execute FFmpeg command
            await this.ffmpeg.exec(command);
            
            this.updateProgress('Retrieving encoded video...', 90);
            
            // Read output file
            const outputData = await this.ffmpeg.readFile('output.mp4');
            
            // Clean up temporary files
            await this.cleanupTempFiles(images.length);
            
            this.updateProgress('Video encoding complete', 100);
            
            // Convert to blob for download
            const videoBlob = new Blob([outputData.buffer], { type: 'video/mp4' });
            
            return {
                blob: videoBlob,
                size: videoBlob.size,
                settings: settings,
                inputCount: images.length,
                success: true
            };
            
        } catch (error) {
            console.error('Video encoding failed:', error);
            throw new Error(`Video encoding failed: ${error.message}`);
        }
    }

    // Write images to FFmpeg virtual file system
    async writeImagesToFFmpeg(images) {
        const total = images.length;
        
        for (let i = 0; i < total; i++) {
            const image = images[i];
            const filename = `input_${String(i + 1).padStart(4, '0')}.jpg`;
            
            // Convert image to Uint8Array
            const arrayBuffer = await this.imageToArrayBuffer(image);
            const uint8Array = new Uint8Array(arrayBuffer);
            
            // Write to FFmpeg file system
            await this.ffmpeg.writeFile(filename, uint8Array);
            
            // Update progress
            const progress = Math.round((i + 1) / total * 20); // 0-20% for writing files
            this.updateProgress(`Writing image ${i + 1}/${total}...`, progress);
        }
    }

    // Convert image file/blob to ArrayBuffer
    async imageToArrayBuffer(image) {
        if (image instanceof File || image instanceof Blob) {
            return await image.arrayBuffer();
        } else if (image instanceof ArrayBuffer) {
            return image;
        } else {
            throw new Error('Invalid image format. Expected File, Blob, or ArrayBuffer.');
        }
    }

    // Build FFmpeg command based on settings
    buildFFmpegCommand(imageCount, settings) {
        const command = [
            '-framerate', settings.frameRate.toString(),
            '-i', 'input_%04d.jpg',
            '-c:v', settings.codec
        ];

        // Add quality settings
        switch (settings.quality) {
            case 'high':
                command.push('-crf', '18');
                break;
            case 'medium':
                command.push('-crf', '23');
                break;
            case 'low':
                command.push('-crf', '28');
                break;
        }

        // Add resolution settings if specified
        if (settings.resolution && settings.resolution !== 'original') {
            if (typeof settings.resolution === 'string' && settings.resolution.includes('x')) {
                command.push('-s', settings.resolution);
            }
        }

        // Add output format and codec parameters
        command.push(
            '-pix_fmt', 'yuv420p', // Ensure compatibility
            '-movflags', '+faststart', // Enable streaming
            'output.mp4'
        );

        return command;
    }

    // Clean up temporary files from FFmpeg file system
    async cleanupTempFiles(imageCount) {
        try {
            for (let i = 1; i <= imageCount; i++) {
                const filename = `input_${String(i).padStart(4, '0')}.jpg`;
                try {
                    await this.ffmpeg.deleteFile(filename);
                } catch (error) {
                    // Ignore errors for individual file deletions
                    console.warn(`Could not delete temp file ${filename}:`, error);
                }
            }
        } catch (error) {
            console.warn('Cleanup warning:', error);
        }
    }

    // Update progress and notify callbacks
    updateProgress(message, percentage) {
        this.loadingProgress = percentage;
        
        if (this.onProgress) {
            this.onProgress({
                message: message,
                percentage: Math.round(percentage),
                step: 'video-encoding'
            });
        }
        
        console.log(`VideoEncoder Progress: ${message} (${Math.round(percentage)}%)`);
    }

    // Get encoding capabilities and settings info
    getCapabilities() {
        return {
            isLoaded: this.isLoaded,
            supportedFormats: ['mp4'],
            supportedCodecs: ['libx264', 'libx265'],
            qualityLevels: ['high', 'medium', 'low'],
            frameRateRange: { min: 5, max: 60, default: 15 },
            maxResolution: '4K',
            browser: this.getBrowserInfo()
        };
    }

    // Get browser information for compatibility
    getBrowserInfo() {
        const userAgent = navigator.userAgent;
        let browser = 'Unknown';
        
        if (userAgent.includes('Chrome')) browser = 'Chrome';
        else if (userAgent.includes('Firefox')) browser = 'Firefox';
        else if (userAgent.includes('Safari')) browser = 'Safari';
        else if (userAgent.includes('Edge')) browser = 'Edge';
        
        const hasSharedArrayBuffer = typeof SharedArrayBuffer !== 'undefined';
        const hasWebAssembly = typeof WebAssembly === 'object';
        
        return {
            name: browser,
            supportsFFmpeg: hasWebAssembly, // WebAssembly is the minimum requirement
            supportsWASM: hasWebAssembly,
            hasSharedArrayBuffer: hasSharedArrayBuffer,
            performanceMode: hasSharedArrayBuffer ? 'optimal' : 'fallback',
            compatibilityNotes: hasSharedArrayBuffer ? 
                'Full performance mode available' : 
                'Fallback mode - video encoding will be slower but functional'
        };
    }

    // Terminate FFmpeg instance and clean up
    async terminate() {
        if (this.ffmpeg && this.isLoaded) {
            try {
                await this.ffmpeg.terminate();
                this.isLoaded = false;
                console.log('FFmpeg terminated successfully');
            } catch (error) {
                console.warn('Error terminating FFmpeg:', error);
            }
        }
    }
}

// Export for use in other modules
window.VideoEncoder = VideoEncoder;
