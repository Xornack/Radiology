// Test Suite for Enhanced Error Handler - Step 2.4
// Tests comprehensive error handling and validation
// Part of Phase 2: Video Generation Engine

class ErrorHandlerTests {
    constructor() {
        this.testResults = [];
        this.currentTest = null;
    }

    // Run all tests
    async runAllTests() {
        console.log('Starting Error Handler Tests (Step 2.4)...');
        
        const tests = [
            'testInitialization',
            'testFileValidation',
            'testImageValidation',
            'testEncodingValidation',
            'testErrorHandling',
            'testRecoveryMechanisms',
            'testValidationSummary',
            'testMemoryValidation',
            'testErrorReporting',
            'testErrorCategories'
        ];

        for (const test of tests) {
            try {
                this.currentTest = test;
                console.log(`Running test: ${test}`);
                await this[test]();
                this.recordResult(test, 'PASS', null);
            } catch (error) {
                console.error(`Test ${test} failed:`, error);
                this.recordResult(test, 'FAIL', error.message);
            }
        }

        return this.generateTestReport();
    }

    // Test basic initialization
    async testInitialization() {
        const errorHandler = new ErrorHandler();
        
        // Check initialization
        if (!errorHandler.errorLog) throw new Error('Error log not initialized');
        if (!errorHandler.validationRules) throw new Error('Validation rules not initialized');
        if (!errorHandler.errorCategories) throw new Error('Error categories not initialized');
        if (!errorHandler.errorSeverity) throw new Error('Error severity levels not initialized');
        
        // Check validation rules structure
        const requiredRules = ['fileCount', 'fileSize', 'imageFormats', 'imageDimensions', 'memoryUsage', 'encoding'];
        requiredRules.forEach(rule => {
            if (!errorHandler.validationRules[rule]) {
                throw new Error(`Validation rule ${rule} not found`);
            }
        });
        
        console.log('✓ Initialization test passed');
    }

    // Test file validation
    async testFileValidation() {
        const errorHandler = new ErrorHandler();
        
        // Create mock files for testing
        const validFile = this.createMockFile('test.jpg', 'image/jpeg', 1024 * 100); // 100KB
        const invalidFile = this.createMockFile('test.txt', 'text/plain', 1024); // Wrong type
        const tooLargeFile = this.createMockFile('large.jpg', 'image/jpeg', 200 * 1024 * 1024); // 200MB
        
        const files = [validFile, invalidFile, tooLargeFile];
        
        const result = await errorHandler.validateInputFiles(files);
        
        // Check validation results
        if (result.validFiles.length !== 1) throw new Error('Expected 1 valid file');
        if (result.invalidFiles.length !== 2) throw new Error('Expected 2 invalid files');
        if (result.errors.length === 0) throw new Error('Expected validation errors');
        
        console.log('✓ File validation test passed');
    }

    // Test image validation
    async testImageValidation() {
        const errorHandler = new ErrorHandler();
        
        // Test individual file validation
        const validFile = this.createMockFile('test.jpg', 'image/jpeg', 50000);
        const invalidFile = this.createMockFile('test.pdf', 'application/pdf', 50000);
        
        const validResult = await errorHandler.validateSingleFile(validFile, 0);
        const invalidResult = await errorHandler.validateSingleFile(invalidFile, 1);
        
        // Note: In a real test, we'd need actual image files to test readability
        // For this test, we check the validation logic structure
        if (invalidResult.isValid === true) throw new Error('PDF file should not be valid');
        if (invalidResult.errors.length === 0) throw new Error('PDF file should have errors');
        
        console.log('✓ Image validation test passed');
    }

    // Test encoding parameter validation
    async testEncodingValidation() {
        const errorHandler = new ErrorHandler();
        
        // Test valid encoding settings
        const validSettings = {
            frameRate: 15,
            codec: 'libx264',
            format: 'mp4',
            quality: 'medium'
        };
        
        const validResult = errorHandler.validateEncodingParameters(validSettings);
        if (!validResult.isValid) throw new Error('Valid settings should pass validation');
        
        // Test invalid settings
        const invalidSettings = {
            frameRate: 120, // Too high
            codec: 'invalidcodec',
            format: 'avi', // Not supported
            quality: 'medium'
        };
        
        const invalidResult = errorHandler.validateEncodingParameters(invalidSettings);
        if (invalidResult.isValid) throw new Error('Invalid settings should fail validation');
        if (invalidResult.errors.length === 0) throw new Error('Invalid settings should have errors');
        
        console.log('✓ Encoding validation test passed');
    }

    // Test error handling mechanisms
    async testErrorHandling() {
        const errorHandler = new ErrorHandler();
        
        let errorCaught = false;
        let errorInfo = null;
        
        // Set error callback
        errorHandler.setCallbacks(
            (error) => {
                errorCaught = true;
                errorInfo = error;
            },
            null,
            null
        );
        
        try {
            // Simulate a processing error
            const error = new Error('Test processing error');
            await errorHandler.handleProcessingError(error, { step: 'test' });
        } catch (e) {
            // Expected to throw since recovery will fail in test
        }
        
        // Check error logging
        if (errorHandler.errorLog.length === 0) throw new Error('Error should be logged');
        if (!errorCaught) throw new Error('Error callback should be called');
        
        console.log('✓ Error handling test passed');
    }

    // Test recovery mechanisms
    async testRecoveryMechanisms() {
        const errorHandler = new ErrorHandler();
        
        // Test memory error recovery
        const memoryError = { code: 'MEMORY_ERROR', context: { step: 'encoding' } };
        const memoryRecovery = await errorHandler.recoverFromMemoryError(memoryError);
        if (!memoryRecovery.success) throw new Error('Memory recovery should succeed');
        
        // Test encoding error recovery
        const encodingError = { code: 'ENCODING_ERROR', context: { step: 'encoding' } };
        const encodingRecovery = await errorHandler.recoverFromEncodingError(encodingError);
        if (!encodingRecovery.success) throw new Error('Encoding recovery should succeed');
        
        console.log('✓ Recovery mechanisms test passed');
    }

    // Test validation summary generation
    async testValidationSummary() {
        const errorHandler = new ErrorHandler();
        
        // Create mock validation result
        const mockResult = {
            validFiles: [1, 2, 3], // 3 valid files
            invalidFiles: [1], // 1 invalid file
            warnings: [{}, {}], // 2 warnings
            errors: [
                { severity: errorHandler.errorSeverity.CRITICAL },
                { severity: errorHandler.errorSeverity.HIGH }
            ],
            isValid: false
        };
        
        const summary = errorHandler.generateValidationSummary(mockResult);
        
        if (summary.totalFiles !== 4) throw new Error('Total files count incorrect');
        if (summary.validFiles !== 3) throw new Error('Valid files count incorrect');
        if (summary.invalidFiles !== 1) throw new Error('Invalid files count incorrect');
        if (summary.warningCount !== 2) throw new Error('Warning count incorrect');
        if (summary.errorCount !== 2) throw new Error('Error count incorrect');
        if (summary.criticalErrors !== 1) throw new Error('Critical errors count incorrect');
        if (summary.validationPassed !== false) throw new Error('Validation passed should be false');
        
        console.log('✓ Validation summary test passed');
    }

    // Test memory usage validation
    async testMemoryValidation() {
        const errorHandler = new ErrorHandler();
        
        // Test normal memory usage
        const normalFiles = [
            this.createMockFile('test1.jpg', 'image/jpeg', 1024 * 1024), // 1MB
            this.createMockFile('test2.jpg', 'image/jpeg', 1024 * 1024)  // 1MB
        ];
        
        const normalResult = errorHandler.validateMemoryUsage(normalFiles);
        if (!normalResult.isValid) throw new Error('Normal memory usage should be valid');
        
        // Test high memory usage
        const highMemoryFiles = [
            this.createMockFile('large1.jpg', 'image/jpeg', 1024 * 1024 * 1024), // 1GB
            this.createMockFile('large2.jpg', 'image/jpeg', 1024 * 1024 * 1024 * 1.5) // 1.5GB
        ];
        
        const highMemoryResult = errorHandler.validateMemoryUsage(highMemoryFiles);
        if (highMemoryResult.warnings.length === 0) throw new Error('High memory usage should generate warnings');
        
        console.log('✓ Memory validation test passed');
    }

    // Test error reporting
    async testErrorReporting() {
        const errorHandler = new ErrorHandler();
        
        // Generate some test errors
        errorHandler.logError({
            category: errorHandler.errorCategories.INPUT,
            severity: errorHandler.errorSeverity.HIGH,
            code: 'TEST_ERROR_1',
            message: 'Test error 1'
        });
        
        errorHandler.logError({
            category: errorHandler.errorCategories.PROCESSING,
            severity: errorHandler.errorSeverity.CRITICAL,
            code: 'TEST_ERROR_2',
            message: 'Test error 2'
        });
        
        const report = errorHandler.getErrorReport();
        
        if (!report.errorLog) throw new Error('Error report should have error log');
        if (!report.statistics) throw new Error('Error report should have statistics');
        if (report.statistics.totalErrors !== 2) throw new Error('Total errors should be 2');
        if (!report.statistics.errorsByCategory) throw new Error('Should have errors by category');
        if (!report.statistics.errorsBySeverity) throw new Error('Should have errors by severity');
        
        console.log('✓ Error reporting test passed');
    }

    // Test error categories and severities
    async testErrorCategories() {
        const errorHandler = new ErrorHandler();
        
        // Check all error categories exist
        const requiredCategories = ['INPUT', 'PROCESSING', 'ENCODING', 'OUTPUT', 'SYSTEM'];
        requiredCategories.forEach(category => {
            if (!errorHandler.errorCategories[category]) {
                throw new Error(`Error category ${category} not found`);
            }
        });
        
        // Check all severity levels exist
        const requiredSeverities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
        requiredSeverities.forEach(severity => {
            if (!errorHandler.errorSeverity[severity]) {
                throw new Error(`Error severity ${severity} not found`);
            }
        });
        
        console.log('✓ Error categories test passed');
    }

    // Helper method to create mock files
    createMockFile(name, type, size) {
        // Create a mock file object for testing
        const mockFile = {
            name: name,
            type: type,
            size: size,
            lastModified: Date.now()
        };
        
        // Add File-like methods if needed
        Object.defineProperty(mockFile, 'constructor', {
            value: File
        });
        
        return mockFile;
    }

    // Utility function to simulate delay
    simulateDelay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Record test result
    recordResult(testName, status, error) {
        this.testResults.push({
            test: testName,
            status: status,
            error: error,
            timestamp: new Date().toISOString()
        });
    }

    // Generate test report
    generateTestReport() {
        const totalTests = this.testResults.length;
        const passedTests = this.testResults.filter(r => r.status === 'PASS').length;
        const failedTests = this.testResults.filter(r => r.status === 'FAIL').length;
        
        const report = {
            summary: {
                total: totalTests,
                passed: passedTests,
                failed: failedTests,
                passRate: totalTests > 0 ? ((passedTests / totalTests) * 100).toFixed(1) : '0.0'
            },
            results: this.testResults,
            timestamp: new Date().toISOString()
        };
        
        console.log('Error Handler Test Report:');
        console.log(`Total: ${totalTests}, Passed: ${passedTests}, Failed: ${failedTests}`);
        console.log(`Pass Rate: ${report.summary.passRate}%`);
        
        if (failedTests > 0) {
            console.log('Failed tests:');
            this.testResults.filter(r => r.status === 'FAIL').forEach(result => {
                console.log(`- ${result.test}: ${result.error}`);
            });
        }
        
        return report;
    }
}

// Export for use in test runners
window.ErrorHandlerTests = ErrorHandlerTests;

// Auto-run tests if this script is loaded directly
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', async () => {
        // Only auto-run if we're in a test environment
        if (window.location.pathname.includes('test') || window.location.search.includes('test=error')) {
            const tests = new ErrorHandlerTests();
            await tests.runAllTests();
        }
    });
}
