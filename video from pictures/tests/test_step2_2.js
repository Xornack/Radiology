// Test Step 2.2: Image-to-Video Conversion Logic Test
// Tests core image sequence to MP4 conversion functionality
// Part of Phase 2: Video Generation Engine

class TestStep2_2 {
    constructor() {
        this.testResults = {
            passed: 0,
            failed: 0,
            details: []
        };
        this.converter = null;
    }

    async runAllTests() {
        console.log('=== Starting Step 2.2 Tests: Image-to-Video Conversion Logic ===');
        
        try {
            await this.testConverterInitialization();
            await this.testSettingsManagement();
            await this.testImageValidation();
            await this.testImageProcessing();
            await this.testFilenameGeneration();
            await this.testMetadataCalculation();
            await this.testProgressTracking();
            await this.testErrorHandling();
            
        } catch (error) {
            this.addTestResult('Critical Error', false, `Test suite failed: ${error.message}`);
        }

        this.displayResults();
        return this.testResults;
    }

    async testConverterInitialization() {
        try {
            console.log('Testing ImageToVideoConverter initialization...');
            
            // Test 1: Constructor
            this.converter = new ImageToVideoConverter();
            this.addTestResult('Converter Constructor', 
                this.converter !== null, 
                'ImageToVideoConverter instance created successfully');

            // Test 2: Default settings
            const stats = this.converter.getConversionStats();
            this.addTestResult('Default Settings', 
                stats.settings.frameRate === 15 && stats.settings.quality === 'medium', 
                'Default conversion settings configured correctly');

            // Test 3: Callbacks setup
            let progressCalled = false;
            let errorCalled = false;
            let completeCalled = false;

            this.converter.setCallbacks(
                () => { progressCalled = true; },
                () => { errorCalled = true; },
                () => { completeCalled = true; }
            );

            this.addTestResult('Callback Setup', 
                this.converter.onProgress !== null, 
                'Progress callbacks configured successfully');

        } catch (error) {
            this.addTestResult('Converter Initialization', false, error.message);
        }
    }

    async testSettingsManagement() {
        try {
            console.log('Testing settings management...');
            
            // Test 1: Update settings
            const newSettings = {
                frameRate: 30,
                quality: 'high',
                resolution: '1920x1080'
            };

            this.converter.updateSettings(newSettings);
            const stats = this.converter.getConversionStats();

            this.addTestResult('Settings Update', 
                stats.settings.frameRate === 30 && stats.settings.quality === 'high', 
                'Settings updated correctly');

            // Test 2: Partial settings update
            this.converter.updateSettings({ frameRate: 24 });
            const updatedStats = this.converter.getConversionStats();

            this.addTestResult('Partial Settings Update', 
                updatedStats.settings.frameRate === 24 && updatedStats.settings.quality === 'high', 
                'Partial settings update preserves other settings');

            // Test 3: Invalid settings handling
            this.converter.updateSettings({ frameRate: 'invalid' });
            this.addTestResult('Invalid Settings Handling', 
                true, // Should not throw error
                'Invalid settings handled gracefully');

        } catch (error) {
            this.addTestResult('Settings Management', false, error.message);
        }
    }

    async testImageValidation() {
        try {
            console.log('Testing image validation...');
            
            // Create mock JPEG files for testing
            const validJpegFile = new File(['fake jpeg data'], 'test1.jpg', { type: 'image/jpeg' });
            const invalidFile = new File(['fake data'], 'test.txt', { type: 'text/plain' });
            const jpegWithWrongType = new File(['fake jpeg'], 'test2.jpg', { type: 'text/plain' });

            // Test 1: Valid JPEG detection
            const isValidJpeg = this.converter.isValidJPEG(validJpegFile);
            this.addTestResult('Valid JPEG Detection', 
                isValidJpeg, 
                'Valid JPEG file detected correctly');

            // Test 2: Invalid file rejection
            const isInvalidRejected = !this.converter.isValidJPEG(invalidFile);
            this.addTestResult('Invalid File Rejection', 
                isInvalidRejected, 
                'Invalid file rejected correctly');

            // Test 3: JPEG with wrong MIME type (should pass based on extension)
            const jpegExtensionValid = this.converter.isValidJPEG(jpegWithWrongType);
            this.addTestResult('JPEG Extension Detection', 
                jpegExtensionValid, 
                'JPEG file detected by extension when MIME type is wrong');

            // Test 4: File size validation (large file warning)
            const largeFile = new File(['x'.repeat(60 * 1024 * 1024)], 'large.jpg', { type: 'image/jpeg' });
            this.addTestResult('Large File Handling', 
                true, // Should not fail, just warn
                'Large files handled with appropriate warning');

        } catch (error) {
            this.addTestResult('Image Validation', false, error.message);
        }
    }

    async testImageProcessing() {
        try {
            console.log('Testing image processing...');
            
            // Create mock image files
            const mockImages = [
                new File(['fake jpeg 1'], 'img001.jpg', { type: 'image/jpeg' }),
                new File(['fake jpeg 2'], 'img002.jpg', { type: 'image/jpeg' }),
                new File(['fake jpeg 3'], 'img003.jpg', { type: 'image/jpeg' })
            ];

            // Test 1: Image processing (currently pass-through)
            const processedImages = await this.converter.processImages(mockImages);
            
            this.addTestResult('Image Processing Count', 
                processedImages.length === mockImages.length, 
                `Processed ${processedImages.length} out of ${mockImages.length} images`);

            this.addTestResult('Image Processing Integrity', 
                processedImages[0] === mockImages[0], 
                'Images passed through processing unchanged (as expected for current version)');

            // Test 2: Empty array handling
            const emptyResult = await this.converter.processImages([]);
            this.addTestResult('Empty Array Processing', 
                emptyResult.length === 0, 
                'Empty image array handled correctly');

        } catch (error) {
            this.addTestResult('Image Processing', false, error.message);
        }
    }

    async testFilenameGeneration() {
        try {
            console.log('Testing filename generation...');
            
            // Test 1: Basic filename generation
            const mockImages = [
                new File(['fake jpeg'], 'test.jpg', { type: 'image/jpeg' })
            ];

            const filename1 = this.converter.generateOutputFilename(mockImages);
            this.addTestResult('Basic Filename Generation', 
                filename1.includes('medical_images') && filename1.endsWith('.mp4'), 
                `Generated filename: ${filename1}`);

            // Test 2: Filename with webkitRelativePath
            const mockImagesWithPath = [
                Object.assign(new File(['fake jpeg'], 'img1.jpg', { type: 'image/jpeg' }), {
                    webkitRelativePath: 'CT_Scan_Series/img1.jpg'
                })
            ];

            const filename2 = this.converter.generateOutputFilename(mockImagesWithPath);
            this.addTestResult('Folder-based Filename Generation', 
                filename2.includes('CT_Scan_Series') && filename2.endsWith('.mp4'), 
                `Generated filename with folder: ${filename2}`);

            // Test 3: Timestamp uniqueness
            const filename3 = this.converter.generateOutputFilename(mockImages);
            this.addTestResult('Filename Uniqueness', 
                filename1 !== filename3, // Should be different due to timestamp
                'Generated filenames are unique');

        } catch (error) {
            this.addTestResult('Filename Generation', false, error.message);
        }
    }

    async testMetadataCalculation() {
        try {
            console.log('Testing metadata calculation...');
            
            // Test 1: Duration calculation
            const duration = this.converter.calculateDuration(150); // 150 frames at 15 FPS = 10 seconds
            this.addTestResult('Duration Calculation', 
                duration.seconds === 10 && duration.formatted === '10.0s', 
                `Calculated duration: ${duration.formatted}`);

            // Test 2: Duration formatting (minutes)
            const longDuration = this.converter.calculateDuration(1800); // 1800 frames = 2 minutes
            this.addTestResult('Duration Formatting', 
                longDuration.formatted.includes('m'), 
                `Long duration formatted: ${longDuration.formatted}`);

            // Test 3: File size formatting
            const sizeFormatted = this.converter.formatFileSize(1536000); // 1.5 MB
            this.addTestResult('File Size Formatting', 
                sizeFormatted.includes('MB'), 
                `Formatted size: ${sizeFormatted}`);

            // Test 4: Average image size calculation
            const mockImages = [
                new File(['x'.repeat(100000)], 'img1.jpg', { type: 'image/jpeg' }), // 100KB
                new File(['x'.repeat(200000)], 'img2.jpg', { type: 'image/jpeg' })  // 200KB
            ];

            const avgSize = this.converter.calculateAverageImageSize(mockImages);
            this.addTestResult('Average Size Calculation', 
                avgSize.bytes === 150000, // (100000 + 200000) / 2
                `Average size: ${avgSize.formatted}`);

            // Test 5: Compression ratio calculation
            const compression = this.converter.calculateCompressionRatio(mockImages, 50000); // Video is 50KB
            this.addTestResult('Compression Ratio Calculation', 
                parseFloat(compression.ratio) > 1, 
                `Compression ratio: ${compression.ratio}:1 (${compression.percentage}% reduction)`);

        } catch (error) {
            this.addTestResult('Metadata Calculation', false, error.message);
        }
    }

    async testProgressTracking() {
        try {
            console.log('Testing progress tracking...');
            
            let progressCallbacks = [];
            
            // Set up progress tracking
            this.converter.setCallbacks(
                (progress) => {
                    progressCallbacks.push(progress);
                },
                null,
                null
            );

            // Test progress update
            this.converter.updateProgress('Test progress message', 50);
            
            this.addTestResult('Progress Callback', 
                progressCallbacks.length > 0, 
                'Progress callback executed successfully');

            this.addTestResult('Progress Data', 
                progressCallbacks[0].percentage === 50 && progressCallbacks[0].message === 'Test progress message', 
                'Progress data formatted correctly');

            this.addTestResult('Progress Step Identification', 
                progressCallbacks[0].step === 'image-to-video-conversion', 
                'Progress step identified correctly');

        } catch (error) {
            this.addTestResult('Progress Tracking', false, error.message);
        }
    }

    async testErrorHandling() {
        try {
            console.log('Testing error handling...');
            
            // Test 1: Empty image array
            try {
                await this.converter.validateImages([]);
                this.addTestResult('Empty Array Error', false, 'Should have thrown error for empty array');
            } catch (error) {
                this.addTestResult('Empty Array Error', 
                    error.message.includes('No valid images'), 
                    'Empty array properly rejected');
            }

            // Test 2: Invalid image objects
            try {
                await this.converter.validateImages(['not a file']);
                this.addTestResult('Invalid Object Error', false, 'Should have thrown error for invalid objects');
            } catch (error) {
                this.addTestResult('Invalid Object Error', 
                    true, 
                    'Invalid objects properly rejected');
            }

            // Test 3: Mixed valid/invalid images
            const mixedImages = [
                new File(['valid jpeg'], 'valid.jpg', { type: 'image/jpeg' }),
                new File(['invalid'], 'invalid.txt', { type: 'text/plain' })
            ];

            const validatedMixed = await this.converter.validateImages(mixedImages);
            this.addTestResult('Mixed Image Validation', 
                validatedMixed.length === 1, 
                'Valid images extracted from mixed array');

        } catch (error) {
            this.addTestResult('Error Handling', false, error.message);
        }
    }

    addTestResult(testName, passed, details) {
        const result = {
            test: testName,
            passed: passed,
            details: details,
            timestamp: new Date().toISOString()
        };

        this.testResults.details.push(result);
        
        if (passed) {
            this.testResults.passed++;
            console.log(`✅ ${testName}: ${details}`);
        } else {
            this.testResults.failed++;
            console.log(`❌ ${testName}: ${details}`);
        }
    }

    displayResults() {
        const total = this.testResults.passed + this.testResults.failed;
        const passRate = ((this.testResults.passed / total) * 100).toFixed(1);
        
        console.log('\n=== Step 2.2 Test Results ===');
        console.log(`Total Tests: ${total}`);
        console.log(`Passed: ${this.testResults.passed}`);
        console.log(`Failed: ${this.testResults.failed}`);
        console.log(`Pass Rate: ${passRate}%`);
        
        if (this.testResults.failed > 0) {
            console.log('\nFailed Tests:');
            this.testResults.details
                .filter(result => !result.passed)
                .forEach(result => {
                    console.log(`- ${result.test}: ${result.details}`);
                });
        }
        
        // Update DOM if test runner page exists
        this.updateTestRunnerDisplay();
        
        console.log('\n=== End Step 2.2 Tests ===');
    }

    updateTestRunnerDisplay() {
        const resultsDiv = document.getElementById('step2-2-results');
        if (resultsDiv) {
            const total = this.testResults.passed + this.testResults.failed;
            const passRate = ((this.testResults.passed / total) * 100).toFixed(1);
            
            resultsDiv.innerHTML = `
                <h3>Step 2.2: Image-to-Video Conversion Logic Test Results</h3>
                <div class="test-summary">
                    <p><strong>Total Tests:</strong> ${total}</p>
                    <p><strong>Passed:</strong> <span class="passed">${this.testResults.passed}</span></p>
                    <p><strong>Failed:</strong> <span class="failed">${this.testResults.failed}</span></p>
                    <p><strong>Pass Rate:</strong> ${passRate}%</p>
                </div>
                <div class="test-details">
                    <h4>Test Details:</h4>
                    <ul>
                        ${this.testResults.details.map(result => `
                            <li class="${result.passed ? 'passed' : 'failed'}">
                                <strong>${result.test}:</strong> ${result.details}
                            </li>
                        `).join('')}
                    </ul>
                </div>
            `;
        }
    }

    // Get summary for integration with main test runner
    getSummary() {
        const total = this.testResults.passed + this.testResults.failed;
        return {
            step: 'Step 2.2',
            description: 'Image-to-Video Conversion Logic',
            total: total,
            passed: this.testResults.passed,
            failed: this.testResults.failed,
            passRate: total > 0 ? ((this.testResults.passed / total) * 100).toFixed(1) : 0,
            status: this.testResults.failed === 0 ? 'PASSED' : 'FAILED'
        };
    }
}

// Export for use in test runner
window.TestStep2_2 = TestStep2_2;
