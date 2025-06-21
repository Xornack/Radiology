/**
 * Test Suite for Step 3.4: Error Codes and Messaging System
 * Tests the ErrorCodeSystem and ErrorCodeManager components
 */

class TestStep3_4 {
    constructor() {
        this.testResults = [];
        this.errorCodeSystem = new ErrorCodeSystem();
        this.errorCodeManager = new ErrorCodeManager({
            enableLogging: false, // Disable for testing
            enableUserNotification: false
        });
    }

    /**
     * Run all tests for Step 3.4
     * @returns {Object} Complete test results
     */
    async runAllTests() {
        console.log('🧪 Starting Step 3.4 Tests: Error Codes and Messaging');
        
        const testSuites = [
            () => this.testErrorCodeSystem(),
            () => this.testErrorCodeManager(),
            () => this.testErrorCategorization(),
            () => this.testErrorReporting(),
            () => this.testIntegration(),
            () => this.testPerformance()
        ];

        for (const testSuite of testSuites) {
            try {
                await testSuite();
            } catch (error) {
                this.addTestResult('ERROR', `Test suite failed: ${error.message}`, false);
            }
        }

        return this.generateTestReport();
    }

    /**
     * Test ErrorCodeSystem functionality
     */
    testErrorCodeSystem() {
        console.log('🔍 Testing ErrorCodeSystem...');

        // Test error code retrieval
        this.testErrorCodeRetrieval();
        
        // Test category functionality
        this.testCategoryFunctionality();
        
        // Test severity levels
        this.testSeverityLevels();
        
        // Test error formatting
        this.testErrorFormatting();
        
        // Test validation methods
        this.testValidationMethods();
    }

    /**
     * Test error code retrieval
     */
    testErrorCodeRetrieval() {
        // Test valid error code
        const error = this.errorCodeSystem.getError('FSA_001');
        this.addTestResult(
            'ErrorCodeSystem.getError',
            'Should retrieve valid error code',
            error && error.code === 'FSA_001' && error.category === 'FILE_SYSTEM_ACCESS'
        );

        // Test invalid error code
        const invalidError = this.errorCodeSystem.getError('INVALID_CODE');
        this.addTestResult(
            'ErrorCodeSystem.getError',
            'Should return null for invalid error code',
            invalidError === null
        );

        // Test error code validation
        this.addTestResult(
            'ErrorCodeSystem.isValidErrorCode',
            'Should validate existing error codes',
            this.errorCodeSystem.isValidErrorCode('VID_001') === true
        );

        this.addTestResult(
            'ErrorCodeSystem.isValidErrorCode',
            'Should reject invalid error codes',
            this.errorCodeSystem.isValidErrorCode('FAKE_001') === false
        );
    }

    /**
     * Test category functionality
     */
    testCategoryFunctionality() {
        // Test category retrieval
        const category = this.errorCodeSystem.getCategory('IMAGE_PROCESSING');
        this.addTestResult(
            'ErrorCodeSystem.getCategory',
            'Should retrieve valid category',
            category && category.name === 'Image Processing'
        );

        // Test errors by category
        const fileSystemErrors = this.errorCodeSystem.getErrorsByCategory('FILE_SYSTEM_ACCESS');
        this.addTestResult(
            'ErrorCodeSystem.getErrorsByCategory',
            'Should return errors in category',
            Array.isArray(fileSystemErrors) && fileSystemErrors.length > 0
        );

        // Test all categories
        const allCategories = this.errorCodeSystem.getAllCategories();
        this.addTestResult(
            'ErrorCodeSystem.getAllCategories',
            'Should return all category names',
            Array.isArray(allCategories) && allCategories.includes('VIDEO_ENCODING')
        );
    }

    /**
     * Test severity levels
     */
    testSeverityLevels() {
        // Test severity info
        const severityInfo = this.errorCodeSystem.getSeverityInfo('HIGH');
        this.addTestResult(
            'ErrorCodeSystem.getSeverityInfo',
            'Should retrieve severity information',
            severityInfo && severityInfo.name === 'High' && severityInfo.color === '#dc3545'
        );

        // Test errors by severity
        const highSeverityErrors = this.errorCodeSystem.getErrorsBySeverity('HIGH');
        this.addTestResult(
            'ErrorCodeSystem.getErrorsBySeverity',
            'Should return high severity errors',
            Array.isArray(highSeverityErrors) && highSeverityErrors.length > 0
        );
    }

    /**
     * Test error formatting
     */
    testErrorFormatting() {
        const formatted = this.errorCodeSystem.formatError('IMG_001', { filename: 'test.jpg' });
        
        this.addTestResult(
            'ErrorCodeSystem.formatError',
            'Should format error correctly',
            formatted.success === true &&
            formatted.code === 'IMG_001' &&
            formatted.category &&
            formatted.severity &&
            formatted.context.filename === 'test.jpg'
        );

        // Test formatting invalid error
        const invalidFormatted = this.errorCodeSystem.formatError('INVALID');
        this.addTestResult(
            'ErrorCodeSystem.formatError',
            'Should handle invalid error codes',
            invalidFormatted.success === false
        );
    }

    /**
     * Test validation methods
     */
    testValidationMethods() {
        // Test statistics
        const stats = this.errorCodeSystem.getErrorStatistics();
        this.addTestResult(
            'ErrorCodeSystem.getErrorStatistics',
            'Should return valid statistics',
            stats.totalErrors > 0 &&
            stats.totalCategories > 0 &&
            typeof stats.categoryCounts === 'object'
        );

        // Test error creation
        const createdError = this.errorCodeSystem.createError('SAV_001', new Error('Test error'), { test: true });
        this.addTestResult(
            'ErrorCodeSystem.createError',
            'Should create standardized error object',
            createdError.success === true &&
            createdError.id &&
            createdError.originalError &&
            createdError.context.test === true
        );
    }

    /**
     * Test ErrorCodeManager functionality
     */
    testErrorCodeManager() {
        console.log('🔍 Testing ErrorCodeManager...');

        // Test error reporting
        this.testBasicErrorReporting();
        
        // Test unhandled error reporting
        this.testUnhandledErrorReporting();
        
        // Test error history
        this.testErrorHistory();
        
        // Test session statistics
        this.testSessionStatistics();
        
        // Test report generation
        this.testReportGeneration();
    }

    /**
     * Test basic error reporting
     */
    testBasicErrorReporting() {
        const reportedError = this.errorCodeManager.reportError('VID_002', new Error('Encoding failed'), {
            operationId: 'test_op_1',
            videoSettings: { quality: 'high' }
        });

        this.addTestResult(
            'ErrorCodeManager.reportError',
            'Should report error correctly',
            reportedError.success === true &&
            reportedError.code === 'VID_002' &&
            reportedError.id &&
            reportedError.context.operationId === 'test_op_1'
        );

        // Test invalid error code handling
        const invalidReport = this.errorCodeManager.reportError('INVALID_CODE', new Error('Test'));
        this.addTestResult(
            'ErrorCodeManager.reportError',
            'Should handle invalid error codes gracefully',
            invalidReport.code === 'UNKNOWN' || invalidReport.success === false
        );
    }

    /**
     * Test unhandled error reporting
     */
    testUnhandledErrorReporting() {
        // Test permission error categorization
        const permissionError = new Error('Permission denied');
        const categorized = this.errorCodeManager.reportUnhandledError(permissionError);
        
        this.addTestResult(
            'ErrorCodeManager.categorizeUnhandledError',
            'Should categorize permission errors',
            categorized.code === 'FSA_001' || categorized.code === 'UNKNOWN'
        );

        // Test memory error categorization
        const memoryError = new Error('Out of memory');
        const categorizedMemory = this.errorCodeManager.reportUnhandledError(memoryError);
        
        this.addTestResult(
            'ErrorCodeManager.categorizeUnhandledError',
            'Should categorize memory errors',
            categorizedMemory.code === 'SYS_002' || categorizedMemory.code === 'UNKNOWN'
        );
    }

    /**
     * Test error history functionality
     */
    testErrorHistory() {
        // Clear history first
        this.errorCodeManager.clearErrorHistory();
        
        // Report a few errors
        this.errorCodeManager.reportError('IMG_001', null, { test: 'history1' });
        this.errorCodeManager.reportError('VID_001', null, { test: 'history2' });
        this.errorCodeManager.reportError('SAV_001', null, { test: 'history3' });

        const history = this.errorCodeManager.getErrorHistory();
        this.addTestResult(
            'ErrorCodeManager.getErrorHistory',
            'Should maintain error history',
            history.length === 3
        );

        // Test filtered history
        const filteredHistory = this.errorCodeManager.getErrorHistory({ category: 'Image Processing' });
        this.addTestResult(
            'ErrorCodeManager.getErrorHistory (filtered)',
            'Should filter history by category',
            filteredHistory.length === 1 && filteredHistory[0].code === 'IMG_001'
        );

        // Test error resolution
        const errorId = history[0].id;
        this.errorCodeManager.resolveError(errorId, 'Test resolution');
        const updatedHistory = this.errorCodeManager.getErrorHistory();
        const resolvedError = updatedHistory.find(e => e.id === errorId);
        
        this.addTestResult(
            'ErrorCodeManager.resolveError',
            'Should mark errors as resolved',
            resolvedError && resolvedError.resolved === true && resolvedError.resolution === 'Test resolution'
        );
    }

    /**
     * Test session statistics
     */
    testSessionStatistics() {
        const stats = this.errorCodeManager.getSessionStatistics();
        
        this.addTestResult(
            'ErrorCodeManager.getSessionStatistics',
            'Should provide session statistics',
            typeof stats.totalErrors === 'number' &&
            typeof stats.unresolvedErrors === 'number' &&
            typeof stats.sessionDuration === 'number' &&
            typeof stats.errorsByCategory === 'object'
        );

        // Test most common error
        const mostCommon = this.errorCodeManager.getMostCommonError();
        this.addTestResult(
            'ErrorCodeManager.getMostCommonError',
            'Should identify most common error',
            mostCommon === null || (mostCommon.code && mostCommon.count > 0)
        );
    }

    /**
     * Test report generation
     */
    testReportGeneration() {
        // Test JSON report
        const jsonReport = this.errorCodeManager.generateErrorReport('json');
        this.addTestResult(
            'ErrorCodeManager.generateErrorReport (JSON)',
            'Should generate JSON report',
            typeof jsonReport === 'string' && jsonReport.includes('"errors"')
        );

        // Test CSV report
        const csvReport = this.errorCodeManager.generateErrorReport('csv');
        this.addTestResult(
            'ErrorCodeManager.generateErrorReport (CSV)',
            'Should generate CSV report',
            typeof csvReport === 'string' && csvReport.includes('ID,Code,Title')
        );

        // Test HTML report
        const htmlReport = this.errorCodeManager.generateErrorReport('html');
        this.addTestResult(
            'ErrorCodeManager.generateErrorReport (HTML)',
            'Should generate HTML report',
            typeof htmlReport === 'string' && htmlReport.includes('<html>') && htmlReport.includes('Error Report')
        );

        // Test export functionality
        const exportData = this.errorCodeManager.exportErrorData('json');
        this.addTestResult(
            'ErrorCodeManager.exportErrorData',
            'Should export error data with metadata',
            exportData.data && exportData.filename && exportData.mimeType === 'application/json'
        );
    }

    /**
     * Test error categorization accuracy
     */
    testErrorCategorization() {
        console.log('🔍 Testing Error Categorization...');

        const testCases = [
            // File system errors
            { error: new Error('Permission denied'), expectedCategory: 'FSA_001' },
            { error: new Error('Access denied to directory'), expectedCategory: 'FSA_001' },
            { error: new Error('File API not supported'), expectedCategory: 'FSA_002' },
            
            // Memory errors
            { error: new Error('Out of memory'), expectedCategory: 'SYS_002' },
            { error: new Error('Memory allocation failed'), expectedCategory: 'SYS_002' },
            
            // Network errors
            { error: new Error('Network request failed'), expectedCategory: 'NET_001' },
            { error: new Error('Fetch failed'), expectedCategory: 'NET_001' },
            
            // Video encoding errors
            { error: new Error('Video encoding failed'), expectedCategory: 'VID_002' },
            { error: new Error('Codec not available'), expectedCategory: 'VID_002' }
        ];

        let correctCategorizations = 0;
        testCases.forEach((testCase, index) => {
            const result = this.errorCodeManager.reportUnhandledError(testCase.error);
            if (result.code === testCase.expectedCategory) {
                correctCategorizations++;
            }
        });

        this.addTestResult(
            'ErrorCodeManager.categorizeUnhandledError',
            'Should correctly categorize common error types',
            correctCategorizations >= testCases.length * 0.7 // Allow 70% accuracy
        );
    }

    /**
     * Test integration with existing systems
     */
    testIntegration() {
        console.log('🔍 Testing System Integration...');

        // Test callback integration
        let callbackTriggered = false;
        const testManager = new ErrorCodeManager({
            enableLogging: false,
            enableUserNotification: false,
            onErrorReported: (error) => {
                callbackTriggered = true;
            }
        });

        testManager.reportError('IMG_001');
        this.addTestResult(
            'ErrorCodeManager.onErrorReported',
            'Should trigger error reported callback',
            callbackTriggered === true
        );

        // Test status callback integration
        let statusCallbackTriggered = false;
        const statusManager = new ErrorCodeManager({
            enableLogging: false,
            enableUserNotification: false,
            statusCallback: (type, message, details) => {
                statusCallbackTriggered = true;
            }
        });

        statusManager.reportError('VID_001');
        this.addTestResult(
            'ErrorCodeManager.statusCallback',
            'Should trigger status callback',
            statusCallbackTriggered === true
        );

        // Test error resolution callback
        let resolutionCallbackTriggered = false;
        const resolveManager = new ErrorCodeManager({
            enableLogging: false,
            onErrorResolved: (error) => {
                resolutionCallbackTriggered = true;
            }
        });

        const reportedError = resolveManager.reportError('SAV_001');
        resolveManager.resolveError(reportedError.id, 'Test resolution');
        
        this.addTestResult(
            'ErrorCodeManager.onErrorResolved',
            'Should trigger error resolved callback',
            resolutionCallbackTriggered === true
        );
    }

    /**
     * Test performance and memory usage
     */
    testPerformance() {
        console.log('🔍 Testing Performance...');

        // Test bulk error reporting performance
        const startTime = performance.now();
        const bulkManager = new ErrorCodeManager({
            enableLogging: false,
            enableUserNotification: false
        });

        // Report 100 errors
        for (let i = 0; i < 100; i++) {
            bulkManager.reportError('IMG_001', null, { iteration: i });
        }

        const endTime = performance.now();
        const duration = endTime - startTime;

        this.addTestResult(
            'ErrorCodeManager.performance',
            'Should handle bulk error reporting efficiently (< 100ms for 100 errors)',
            duration < 100
        );

        // Test memory usage with history rotation
        const memoryManager = new ErrorCodeManager({
            maxHistorySize: 10,
            enableLogging: false,
            enableUserNotification: false
        });

        // Report more errors than history size
        for (let i = 0; i < 25; i++) {
            memoryManager.reportError('VID_001', null, { iteration: i });
        }

        const history = memoryManager.getErrorHistory();
        this.addTestResult(
            'ErrorCodeManager.historyRotation',
            'Should rotate history to prevent memory bloat',
            history.length <= 10
        );

        // Test report generation performance
        const reportStartTime = performance.now();
        const report = bulkManager.generateErrorReport('json');
        const reportEndTime = performance.now();
        const reportDuration = reportEndTime - reportStartTime;

        this.addTestResult(
            'ErrorCodeManager.reportGeneration',
            'Should generate reports efficiently (< 50ms)',
            reportDuration < 50 && report.length > 0
        );
    }

    /**
     * Add a test result
     * @param {string} component - Component being tested
     * @param {string} description - Test description
     * @param {boolean} passed - Whether the test passed
     */
    addTestResult(component, description, passed) {
        this.testResults.push({
            component,
            description,
            passed,
            timestamp: new Date().toISOString()
        });

        const status = passed ? '✅' : '❌';
        console.log(`  ${status} ${component}: ${description}`);
    }

    /**
     * Generate comprehensive test report
     * @returns {Object} Test report
     */
    generateTestReport() {
        const totalTests = this.testResults.length;
        const passedTests = this.testResults.filter(r => r.passed).length;
        const failedTests = totalTests - passedTests;
        const successRate = totalTests > 0 ? (passedTests / totalTests) * 100 : 0;

        const report = {
            summary: {
                totalTests,
                passedTests,
                failedTests,
                successRate: Math.round(successRate * 100) / 100,
                timestamp: new Date().toISOString()
            },
            results: this.testResults,
            componentSummary: this.generateComponentSummary(),
            recommendations: this.generateRecommendations()
        };

        console.log('\n📊 Step 3.4 Test Results Summary:');
        console.log(`   Total Tests: ${totalTests}`);
        console.log(`   Passed: ${passedTests} ✅`);
        console.log(`   Failed: ${failedTests} ❌`);
        console.log(`   Success Rate: ${successRate.toFixed(1)}%`);

        if (successRate >= 90) {
            console.log('🎉 Step 3.4 Implementation: EXCELLENT');
        } else if (successRate >= 75) {
            console.log('👍 Step 3.4 Implementation: GOOD');
        } else if (successRate >= 60) {
            console.log('⚠️ Step 3.4 Implementation: NEEDS IMPROVEMENT');
        } else {
            console.log('🚨 Step 3.4 Implementation: CRITICAL ISSUES');
        }

        return report;
    }

    /**
     * Generate summary by component
     * @returns {Object} Component-wise summary
     */
    generateComponentSummary() {
        const componentStats = {};
        
        this.testResults.forEach(result => {
            if (!componentStats[result.component]) {
                componentStats[result.component] = { total: 0, passed: 0 };
            }
            componentStats[result.component].total++;
            if (result.passed) {
                componentStats[result.component].passed++;
            }
        });

        // Calculate success rates
        Object.keys(componentStats).forEach(component => {
            const stats = componentStats[component];
            stats.successRate = (stats.passed / stats.total) * 100;
        });

        return componentStats;
    }

    /**
     * Generate recommendations based on test results
     * @returns {Array} Array of recommendations
     */
    generateRecommendations() {
        const recommendations = [];
        const failedTests = this.testResults.filter(r => !r.passed);

        if (failedTests.length === 0) {
            recommendations.push('✅ All tests passed! The error code system is fully functional.');
            return recommendations;
        }

        // Analyze failure patterns
        const failuresByComponent = {};
        failedTests.forEach(test => {
            if (!failuresByComponent[test.component]) {
                failuresByComponent[test.component] = [];
            }
            failuresByComponent[test.component].push(test.description);
        });

        Object.keys(failuresByComponent).forEach(component => {
            const failures = failuresByComponent[component];
            recommendations.push(`⚠️ ${component}: ${failures.length} failed test(s) - Review implementation`);
        });

        if (failedTests.length > this.testResults.length * 0.3) {
            recommendations.push('🚨 High failure rate detected - Consider refactoring core functionality');
        }

        return recommendations;
    }
}

// Export for use in test runner
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TestStep3_4;
} else if (typeof window !== 'undefined') {
    window.TestStep3_4 = TestStep3_4;
}

// Auto-run tests if this file is loaded directly
if (typeof window !== 'undefined' && window.location.pathname.includes('test_step3_4')) {
    document.addEventListener('DOMContentLoaded', async () => {
        const tester = new TestStep3_4();
        const results = await tester.runAllTests();
        
        // Display results in page if available
        const resultsElement = document.getElementById('test-results');
        if (resultsElement) {
            resultsElement.innerHTML = `
                <h2>Step 3.4 Test Results</h2>
                <div class="summary">
                    <p>Success Rate: ${results.summary.successRate}%</p>
                    <p>Passed: ${results.summary.passedTests}/${results.summary.totalTests}</p>
                </div>
                <div class="recommendations">
                    ${results.recommendations.map(rec => `<p>${rec}</p>`).join('')}
                </div>
            `;
        }
    });
}
