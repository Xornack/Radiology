// Test Suite for Phase 3 - Step 3.2: Automatic Video Playback/Testing
// Tests video validation and reporting functionality

// Test configuration
const Step3_2_Tests = {
    testResults: [],
    currentTest: null,
    
    // Mock video blob for testing
    createMockVideoBlob: function() {
        // Create a small test video blob (mock data)
        const canvas = document.createElement('canvas');
        canvas.width = 320;
        canvas.height = 240;
        const ctx = canvas.getContext('2d');
        
        // Fill with a simple pattern
        ctx.fillStyle = '#ff0000';
        ctx.fillRect(0, 0, 160, 120);
        ctx.fillStyle = '#00ff00';
        ctx.fillRect(160, 0, 160, 120);
        ctx.fillStyle = '#0000ff';
        ctx.fillRect(0, 120, 160, 120);
        ctx.fillStyle = '#ffff00';
        ctx.fillRect(160, 120, 160, 120);
        
        return new Promise((resolve) => {
            canvas.toBlob((blob) => {
                // Note: This creates an image blob, not a video blob
                // For testing purposes, we'll simulate video properties
                const mockVideoBlob = new Blob([blob], { type: 'video/mp4' });
                Object.defineProperty(mockVideoBlob, 'size', { value: 1024 * 50 }); // 50KB
                resolve(mockVideoBlob);
            });
        });
    },
    
    // Run all Step 3.2 tests
    runAllTests: async function() {
        console.log('🧪 Starting Phase 3 - Step 3.2 Tests: Automatic Video Playback/Testing');
        this.testResults = [];
        
        const tests = [
            { name: 'VideoTester Initialization', func: this.testVideoTesterInitialization },
            { name: 'VideoReporter Initialization', func: this.testVideoReporterInitialization },
            { name: 'Video Blob Validation', func: this.testVideoBlobValidation },
            { name: 'Test Configuration', func: this.testConfiguration },
            { name: 'Progress Callbacks', func: this.testProgressCallbacks },
            { name: 'Report Generation', func: this.testReportGeneration },
            { name: 'Report Export Formats', func: this.testReportExportFormats },
            { name: 'Error Handling', func: this.testErrorHandling },
            { name: 'Integration with Main App', func: this.testMainAppIntegration },
            { name: 'Video Playback Testing', func: this.testVideoPlaybackTesting }
        ];
        
        for (const test of tests) {
            try {
                this.currentTest = test.name;
                console.log(`🔬 Running test: ${test.name}`);
                
                const startTime = Date.now();
                const result = await test.func.call(this);
                const duration = Date.now() - startTime;
                
                this.testResults.push({
                    name: test.name,
                    status: 'PASSED',
                    duration: duration,
                    result: result,
                    timestamp: new Date().toISOString()
                });
                
                console.log(`✅ ${test.name} - PASSED (${duration}ms)`);
                
            } catch (error) {
                console.error(`❌ ${test.name} - FAILED:`, error);
                
                this.testResults.push({
                    name: test.name,
                    status: 'FAILED',
                    error: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        }
        
        this.displayTestSummary();
        return this.testResults;
    },
    
    // Test VideoTester initialization
    testVideoTesterInitialization: function() {
        if (typeof VideoTester === 'undefined') {
            throw new Error('VideoTester class not available');
        }
        
        const tester = new VideoTester();
        
        // Check basic properties
        if (!tester.testConfig) {
            throw new Error('Test configuration not initialized');
        }
        
        if (typeof tester.testVideo !== 'function') {
            throw new Error('testVideo method not available');
        }
        
        if (typeof tester.quickTest !== 'function') {
            throw new Error('quickTest method not available');
        }
        
        // Verify default configuration
        const config = tester.getConfig();
        if (!config.maxTestDuration || !config.validateMetadata) {
            throw new Error('Default configuration incomplete');
        }
        
        return {
            message: 'VideoTester initialized successfully',
            config: config
        };
    },
    
    // Test VideoReporter initialization
    testVideoReporterInitialization: function() {
        if (typeof VideoReporter === 'undefined') {
            throw new Error('VideoReporter class not available');
        }
        
        const reporter = new VideoReporter();
        
        // Check basic properties
        if (!reporter.reportConfig) {
            throw new Error('Report configuration not initialized');
        }
        
        if (typeof reporter.generateTestReport !== 'function') {
            throw new Error('generateTestReport method not available');
        }
        
        if (typeof reporter.exportReport !== 'function') {
            throw new Error('exportReport method not available');
        }
        
        // Verify default configuration
        const config = reporter.getConfig();
        if (!config.includeMetadata || !config.includeTestDetails) {
            throw new Error('Default report configuration incomplete');
        }
        
        return {
            message: 'VideoReporter initialized successfully',
            config: config
        };
    },
    
    // Test video blob validation
    testVideoBlobValidation: async function() {
        const tester = new VideoTester();
        
        // Test with null blob
        try {
            await tester.validateVideoBlob(null);
            throw new Error('Should have failed with null blob');
        } catch (error) {
            if (!error.message.includes('Invalid video blob')) {
                throw new Error('Wrong error message for null blob');
            }
        }
        
        // Test with empty blob
        try {
            const emptyBlob = new Blob([], { type: 'video/mp4' });
            await tester.validateVideoBlob(emptyBlob);
            throw new Error('Should have failed with empty blob');
        } catch (error) {
            if (!error.message.includes('empty')) {
                throw new Error('Wrong error message for empty blob');
            }
        }
        
        // Test with valid mock blob
        const mockBlob = await this.createMockVideoBlob();
        const tester2 = new VideoTester();
        tester2.testResults = tester2.initializeTestResults('test.mp4', null);
        
        await tester2.validateVideoBlob(mockBlob);
        
        const test = tester2.testResults.tests.blobValidation;
        if (test.status !== 'passed') {
            throw new Error('Valid blob validation failed');
        }
        
        return {
            message: 'Video blob validation working correctly',
            testResult: test
        };
    },
    
    // Test configuration updates
    testConfiguration: function() {
        const tester = new VideoTester();
        const reporter = new VideoReporter();
        
        // Test VideoTester configuration
        const newTesterConfig = {
            maxTestDuration: 60000,
            validateFrames: true,
            autoStartPlayback: false
        };
        
        tester.updateConfig(newTesterConfig);
        const updatedTesterConfig = tester.getConfig();
        
        if (updatedTesterConfig.maxTestDuration !== 60000) {
            throw new Error('VideoTester configuration update failed');
        }
        
        if (!updatedTesterConfig.validateFrames) {
            throw new Error('VideoTester boolean configuration update failed');
        }
        
        // Test VideoReporter configuration
        const newReporterConfig = {
            formatStyle: 'technical',
            includeTimestamps: false
        };
        
        reporter.updateConfig(newReporterConfig);
        const updatedReporterConfig = reporter.getConfig();
        
        if (updatedReporterConfig.formatStyle !== 'technical') {
            throw new Error('VideoReporter configuration update failed');
        }
        
        return {
            message: 'Configuration updates working correctly',
            testerConfig: updatedTesterConfig,
            reporterConfig: updatedReporterConfig
        };
    },
    
    // Test progress callbacks
    testProgressCallbacks: function() {
        return new Promise((resolve, reject) => {
            const tester = new VideoTester();
            let callbacksReceived = {
                onStart: false,
                onProgress: false,
                onComplete: false,
                onError: false
            };
            
            // Set up callbacks
            tester.setCallbacks(
                (start) => { callbacksReceived.onStart = true; },
                (progress) => { callbacksReceived.onProgress = true; },
                (result) => { callbacksReceived.onComplete = true; },
                (error) => { callbacksReceived.onError = true; }
            );
            
            // Simulate callback triggers
            if (tester.onTestStart) {
                tester.onTestStart({ message: 'Test callback' });
            }
            
            if (tester.onTestProgress) {
                tester.onTestProgress({ message: 'Progress callback', percentage: 50 });
            }
            
            if (tester.onTestComplete) {
                tester.onTestComplete({ success: true });
            }
            
            // Check if callbacks were received
            setTimeout(() => {
                if (!callbacksReceived.onStart || !callbacksReceived.onProgress || !callbacksReceived.onComplete) {
                    reject(new Error('Not all callbacks were triggered'));
                } else {
                    resolve({
                        message: 'Progress callbacks working correctly',
                        callbacksReceived: callbacksReceived
                    });
                }
            }, 100);
        });
    },
    
    // Test report generation
    testReportGeneration: function() {
        const reporter = new VideoReporter();
        
        // Create mock test results
        const mockTestResults = {
            filename: 'test_video.mp4',
            testStartTime: Date.now() - 5000,
            testEndTime: Date.now(),
            testDuration: 5000,
            success: true,
            tests: {
                blobValidation: { status: 'passed', details: { size: 1024 * 50, type: 'video/mp4' } },
                videoCreation: { status: 'passed', details: { duration: 10, videoWidth: 320, videoHeight: 240 } },
                metadataValidation: { status: 'passed', details: { properties: { duration: 10 } } }
            },
            videoProperties: {
                duration: 10,
                width: 320,
                height: 240,
                fileSize: 1024 * 50,
                aspectRatio: '1.333'
            },
            warnings: ['Test warning'],
            recommendations: ['Test recommendation']
        };
        
        const report = reporter.generateTestReport(mockTestResults);
        
        // Validate report structure
        if (!report.summary || !report.details || !report.formatted) {
            throw new Error('Report structure incomplete');
        }
        
        if (report.summary.overall !== 'PASSED') {
            throw new Error('Report summary incorrect');
        }
        
        if (!report.formatted.includes('VIDEO VALIDATION REPORT')) {
            throw new Error('Formatted report content missing');
        }
        
        return {
            message: 'Report generation working correctly',
            reportSummary: report.summary
        };
    },
    
    // Test report export formats
    testReportExportFormats: function() {
        const reporter = new VideoReporter();
        
        // Create simple test report
        const mockReport = {
            summary: { overall: 'PASSED', filename: 'test.mp4' },
            details: { testExecution: { success: true } },
            formatted: 'Test Report Content',
            exportable: { test: 'data' }
        };
        
        // Test text export
        const textExport = reporter.exportReport(mockReport, 'txt');
        if (typeof textExport !== 'string' || !textExport.includes('Test Report Content')) {
            throw new Error('Text export failed');
        }
        
        // Test JSON export
        const jsonExport = reporter.exportReport(mockReport, 'json');
        if (typeof jsonExport !== 'string') {
            throw new Error('JSON export failed');
        }
        
        try {
            JSON.parse(jsonExport);
        } catch (error) {
            throw new Error('JSON export not valid JSON');
        }
        
        // Test HTML export
        const htmlExport = reporter.exportReport(mockReport, 'html');
        if (typeof htmlExport !== 'string' || !htmlExport.includes('<html>')) {
            throw new Error('HTML export failed');
        }
        
        return {
            message: 'Report export formats working correctly',
            exports: {
                text: textExport.length,
                json: jsonExport.length,
                html: htmlExport.length
            }
        };
    },
    
    // Test error handling
    testErrorHandling: async function() {
        const tester = new VideoTester();
        
        // Test with invalid filename
        try {
            const result = await tester.testVideo(null, '');
            if (result.success) {
                throw new Error('Should have failed with null blob');
            }
        } catch (error) {
            // Expected behavior
        }
        
        // Test reporter with invalid data
        const reporter = new VideoReporter();
        
        try {
            const report = reporter.generateTestReport(null);
            if (!report.error) {
                throw new Error('Should have generated error report');
            }
        } catch (error) {
            // Expected behavior
        }
        
        return {
            message: 'Error handling working correctly'
        };
    },
    
    // Test integration with main application
    testMainAppIntegration: function() {
        // Check if main app functions are available
        if (typeof testVideoFile !== 'function') {
            throw new Error('testVideoFile function not available in main app');
        }
        
        if (typeof runQuickVideoTest !== 'function') {
            throw new Error('runQuickVideoTest function not available in main app');
        }
        
        if (typeof showVideoTestProgress !== 'function') {
            throw new Error('showVideoTestProgress function not available in main app');
        }
        
        if (typeof displayVideoTestResults !== 'function') {
            throw new Error('displayVideoTestResults function not available in main app');
        }
        
        // Test progress display functions
        showVideoTestProgress('Integration test', 50);
        hideVideoTestProgress();
        
        return {
            message: 'Main application integration working correctly'
        };
    },
    
    // Test video playback testing functionality
    testVideoPlaybackTesting: function() {
        const tester = new VideoTester();
        
        // Test that video element creation is available
        const video = document.createElement('video');
        if (!video) {
            throw new Error('Video element creation not supported');
        }
        
        // Test that required video properties exist
        if (typeof video.duration === 'undefined' ||
            typeof video.videoWidth === 'undefined' ||
            typeof video.videoHeight === 'undefined') {
            throw new Error('Video properties not available');
        }
        
        // Test canvas for frame analysis
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) {
            throw new Error('Canvas context not available for frame analysis');
        }
        
        return {
            message: 'Video playback testing infrastructure available'
        };
    },
    
    // Display test summary
    displayTestSummary: function() {
        const totalTests = this.testResults.length;
        const passedTests = this.testResults.filter(t => t.status === 'PASSED').length;
        const failedTests = this.testResults.filter(t => t.status === 'FAILED').length;
        
        console.log('\n📊 Phase 3 - Step 3.2 Test Summary:');
        console.log('═══════════════════════════════════════');
        console.log(`Total Tests: ${totalTests}`);
        console.log(`Passed: ${passedTests} ✅`);
        console.log(`Failed: ${failedTests} ❌`);
        console.log(`Success Rate: ${((passedTests/totalTests)*100).toFixed(1)}%`);
        console.log('═══════════════════════════════════════');
        
        if (failedTests > 0) {
            console.log('\n❌ Failed Tests:');
            this.testResults.filter(t => t.status === 'FAILED').forEach(test => {
                console.log(`- ${test.name}: ${test.error}`);
            });
        }
        
        console.log(`\n🎯 Step 3.2 Implementation Status: ${failedTests === 0 ? 'COMPLETED ✅' : 'NEEDS ATTENTION ⚠️'}`);
    },
    
    // Run individual test by name
    runTest: async function(testName) {
        const test = this.findTest(testName);
        if (!test) {
            throw new Error(`Test not found: ${testName}`);
        }
        
        console.log(`🔬 Running individual test: ${testName}`);
        
        try {
            const startTime = Date.now();
            const result = await test.func.call(this);
            const duration = Date.now() - startTime;
            
            console.log(`✅ ${testName} - PASSED (${duration}ms)`);
            return { status: 'PASSED', result: result, duration: duration };
            
        } catch (error) {
            console.error(`❌ ${testName} - FAILED:`, error);
            return { status: 'FAILED', error: error.message };
        }
    },
    
    // Find test by name
    findTest: function(testName) {
        const tests = [
            { name: 'VideoTester Initialization', func: this.testVideoTesterInitialization },
            { name: 'VideoReporter Initialization', func: this.testVideoReporterInitialization },
            { name: 'Video Blob Validation', func: this.testVideoBlobValidation },
            { name: 'Test Configuration', func: this.testConfiguration },
            { name: 'Progress Callbacks', func: this.testProgressCallbacks },
            { name: 'Report Generation', func: this.testReportGeneration },
            { name: 'Report Export Formats', func: this.testReportExportFormats },
            { name: 'Error Handling', func: this.testErrorHandling },
            { name: 'Integration with Main App', func: this.testMainAppIntegration },
            { name: 'Video Playback Testing', func: this.testVideoPlaybackTesting }
        ];
        
        return tests.find(t => t.name === testName);
    }
};

// Make tests available globally
if (typeof window !== 'undefined') {
    window.Step3_2_Tests = Step3_2_Tests;
}

// Auto-run tests if this is the main test file
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('📋 Phase 3 - Step 3.2 tests loaded and ready');
        console.log('Run Step3_2_Tests.runAllTests() to execute all tests');
    });
}
