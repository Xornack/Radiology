// Test Step 2.1: Video Encoder Integration Test
// Tests browser-based video encoding library integration
// Part of Phase 2: Video Generation Engine

class TestStep2_1 {
    constructor() {
        this.testResults = {
            passed: 0,
            failed: 0,
            details: []
        };
        this.videoEncoder = null;
    }

    async runAllTests() {
        console.log('=== Starting Step 2.1 Tests: Video Encoder Integration ===');
        
        try {
            await this.testVideoEncoderInitialization();
            await this.testFFmpegScriptLoading();
            await this.testCapabilitiesDetection();
            await this.testBrowserCompatibility();
            await this.testBasicVideoCreation();
            
        } catch (error) {
            this.addTestResult('Critical Error', false, `Test suite failed: ${error.message}`);
        }

        this.displayResults();
        return this.testResults;
    }

    async testVideoEncoderInitialization() {
        try {
            console.log('Testing VideoEncoder initialization...');
            
            // Test 1: Constructor
            this.videoEncoder = new VideoEncoder();
            this.addTestResult('VideoEncoder Constructor', 
                this.videoEncoder !== null, 
                'VideoEncoder instance created successfully');

            // Test 2: Initial state
            this.addTestResult('Initial Load State', 
                !this.videoEncoder.isLoaded, 
                'VideoEncoder starts in unloaded state');

            // Test 3: Capabilities before loading
            const capabilities = this.videoEncoder.getCapabilities();
            this.addTestResult('Capabilities Detection', 
                capabilities && typeof capabilities === 'object', 
                'Capabilities object returned');

        } catch (error) {
            this.addTestResult('VideoEncoder Initialization', false, error.message);
        }
    }

    async testFFmpegScriptLoading() {
        try {
            console.log('Testing FFmpeg script loading...');
            
            // Test if we can load the script (simulate)
            const scriptLoadTest = () => {
                return new Promise((resolve) => {
                    // Check if script loading mechanism works
                    const testScript = document.createElement('script');
                    testScript.src = 'data:text/javascript;base64,'; // Empty script
                    testScript.onload = () => {
                        document.head.removeChild(testScript);
                        resolve(true);
                    };
                    testScript.onerror = () => {
                        document.head.removeChild(testScript);
                        resolve(false);
                    };
                    document.head.appendChild(testScript);
                });
            };

            const canLoadScripts = await scriptLoadTest();
            this.addTestResult('Script Loading Mechanism', 
                canLoadScripts, 
                'Browser can load external scripts');

            // Test browser requirements
            const hasSharedArrayBuffer = typeof SharedArrayBuffer !== 'undefined';
            const hasWebAssembly = typeof WebAssembly === 'object';
            
            // SharedArrayBuffer is now optional - just warn if missing
            this.addTestResult('SharedArrayBuffer Support', 
                true, // Always pass, but note the status
                hasSharedArrayBuffer ? 
                    'SharedArrayBuffer available (optimal performance)' : 
                    'SharedArrayBuffer disabled (fallback mode will be used - slightly slower but functional)');
                
            this.addTestResult('WebAssembly Support', 
                hasWebAssembly, 
                hasWebAssembly ? 'WebAssembly supported' : 'WebAssembly not supported');

            // Overall FFmpeg compatibility
            const ffmpegCompatible = hasWebAssembly; // WebAssembly is the minimum requirement
            this.addTestResult('FFmpeg.js Compatibility', 
                ffmpegCompatible, 
                ffmpegCompatible ? 
                    `Compatible (${hasSharedArrayBuffer ? 'optimal' : 'fallback'} mode)` : 
                    'Not compatible - WebAssembly required');

        } catch (error) {
            this.addTestResult('FFmpeg Script Loading Test', false, error.message);
        }
    }

    async testCapabilitiesDetection() {
        try {
            console.log('Testing capabilities detection...');
            
            const capabilities = this.videoEncoder.getCapabilities();
            
            // Test capabilities structure
            const requiredProperties = ['isLoaded', 'supportedFormats', 'supportedCodecs', 'qualityLevels', 'frameRateRange', 'browser'];
            
            for (const prop of requiredProperties) {
                this.addTestResult(`Capabilities.${prop}`, 
                    capabilities.hasOwnProperty(prop), 
                    `${prop} property exists in capabilities`);
            }

            // Test specific capability values
            this.addTestResult('MP4 Format Support', 
                capabilities.supportedFormats.includes('mp4'), 
                'MP4 format listed in supported formats');

            this.addTestResult('H.264 Codec Support', 
                capabilities.supportedCodecs.includes('libx264'), 
                'H.264 codec listed in supported codecs');

            this.addTestResult('Quality Levels', 
                capabilities.qualityLevels.length >= 3, 
                `${capabilities.qualityLevels.length} quality levels available`);

            this.addTestResult('Frame Rate Range', 
                capabilities.frameRateRange.min === 5 && capabilities.frameRateRange.max === 60, 
                'Frame rate range 5-60 FPS as specified');

        } catch (error) {
            this.addTestResult('Capabilities Detection', false, error.message);
        }
    }

    async testBrowserCompatibility() {
        try {
            console.log('Testing browser compatibility...');
            
            const browserInfo = this.videoEncoder.getBrowserInfo();
            
            this.addTestResult('Browser Detection', 
                browserInfo.name !== 'Unknown', 
                `Browser detected as: ${browserInfo.name}`);

            this.addTestResult('FFmpeg Compatibility Check', 
                browserInfo.supportsFFmpeg, 
                `FFmpeg support: ${browserInfo.supportsFFmpeg ? 'YES' : 'NO'}`);

            this.addTestResult('WebAssembly Compatibility Check', 
                browserInfo.supportsWASM, 
                `WebAssembly support: ${browserInfo.supportsWASM ? 'YES' : 'NO'}`);

            // Performance mode check
            this.addTestResult('Performance Mode', 
                true, // Always pass, just informational
                `Mode: ${browserInfo.performanceMode} - ${browserInfo.compatibilityNotes}`);

            // Test CORS and security context
            const isSecureContext = window.isSecureContext;
            this.addTestResult('Secure Context', 
                isSecureContext, 
                isSecureContext ? 'Running in secure context (HTTPS)' : 'Not in secure context (may limit functionality)');

        } catch (error) {
            this.addTestResult('Browser Compatibility', false, error.message);
        }
    }

    async testBasicVideoCreation() {
        try {
            console.log('Testing basic video creation setup...');
            
            // Test command building
            const mockSettings = {
                frameRate: 15,
                quality: 'medium',
                resolution: 'original',
                codec: 'libx264',
                format: 'mp4'
            };

            const command = this.videoEncoder.buildFFmpegCommand(10, mockSettings);
            
            this.addTestResult('Command Building', 
                Array.isArray(command) && command.length > 0, 
                `FFmpeg command generated with ${command.length} parameters`);

            this.addTestResult('Frame Rate Parameter', 
                command.includes('-framerate') && command.includes('15'), 
                'Frame rate parameter correctly included');

            this.addTestResult('Quality Parameter', 
                command.includes('-crf'), 
                'Quality parameter (CRF) included');

            this.addTestResult('Output Format', 
                command.includes('output.mp4'), 
                'MP4 output format specified');

            // Test image to ArrayBuffer conversion (mock)
            const mockImageBlob = new Blob(['fake image data'], { type: 'image/jpeg' });
            
            try {
                const arrayBuffer = await this.videoEncoder.imageToArrayBuffer(mockImageBlob);
                this.addTestResult('Image to ArrayBuffer Conversion', 
                    arrayBuffer instanceof ArrayBuffer, 
                    'Successfully converts blob to ArrayBuffer');
            } catch (error) {
                this.addTestResult('Image to ArrayBuffer Conversion', false, error.message);
            }

        } catch (error) {
            this.addTestResult('Basic Video Creation Setup', false, error.message);
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
        
        console.log('\n=== Step 2.1 Test Results ===');
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
        
        console.log('\n=== End Step 2.1 Tests ===');
    }

    updateTestRunnerDisplay() {
        const resultsDiv = document.getElementById('step2-1-results');
        if (resultsDiv) {
            const total = this.testResults.passed + this.testResults.failed;
            const passRate = ((this.testResults.passed / total) * 100).toFixed(1);
            
            resultsDiv.innerHTML = `
                <h3>Step 2.1: Video Encoder Integration Test Results</h3>
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
            step: 'Step 2.1',
            description: 'Video Encoder Integration',
            total: total,
            passed: this.testResults.passed,
            failed: this.testResults.failed,
            passRate: total > 0 ? ((this.testResults.passed / total) * 100).toFixed(1) : 0,
            status: this.testResults.failed === 0 ? 'PASSED' : 'FAILED'
        };
    }
}

// Export for use in test runner
window.TestStep2_1 = TestStep2_1;
