// Test Suite for Enhanced Progress Tracker - Step 2.3
// Tests comprehensive progress tracking with ETA, step-by-step status, and statistics
// Part of Phase 2: Video Generation Engine

class ProgressTrackerTests {
    constructor() {
        this.testResults = [];
        this.currentTest = null;
    }

    // Run all tests
    async runAllTests() {
        console.log('Starting Progress Tracker Tests (Step 2.3)...');
        
        const tests = [
            'testInitialization',
            'testBasicTracking',
            'testStepProgression',
            'testETACalculation',
            'testStatisticsGeneration',
            'testPerformanceMetrics',
            'testCallbackSystem',
            'testErrorHandling',
            'testResetFunctionality',
            'testComplexScenario'
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
        const tracker = new ProgressTracker();
        
        // Check initial state
        if (tracker.startTime !== null) throw new Error('Start time should be null initially');
        if (tracker.currentStep !== null) throw new Error('Current step should be null initially');
        if (tracker.totalSteps !== 0) throw new Error('Total steps should be 0 initially');
        if (tracker.completedSteps !== 0) throw new Error('Completed steps should be 0 initially');
        
        console.log('✓ Initialization test passed');
    }

    // Test basic tracking functionality
    async testBasicTracking() {
        const tracker = new ProgressTracker();
        
        // Start tracking
        tracker.startTracking(5, 10);
        
        if (tracker.startTime === null) throw new Error('Start time should be set');
        if (tracker.totalSteps !== 5) throw new Error('Total steps not set correctly');
        if (tracker.totalItems !== 10) throw new Error('Total items not set correctly');
        
        // Test progress calculation
        const initialProgress = tracker.calculateOverallProgress();
        if (initialProgress !== 0) throw new Error('Initial progress should be 0');
        
        console.log('✓ Basic tracking test passed');
    }

    // Test step progression
    async testStepProgression() {
        const tracker = new ProgressTracker();
        tracker.startTracking(3, 6);
        
        // Start first step
        tracker.startStep('validation', 'Image Validation', 2);
        if (tracker.currentStep !== 'validation') throw new Error('Current step not set correctly');
        
        // Update step progress
        tracker.updateStepProgress(1, 'image1.jpg', 'Validating image 1');
        if (tracker.currentStepProcessedItems !== 1) throw new Error('Step progress not updated');
        
        // Complete step
        tracker.completeStep();
        if (tracker.completedSteps !== 1) throw new Error('Completed steps not incremented');
        if (tracker.currentStep !== null) throw new Error('Current step should be cleared');
        
        // Verify step history
        if (tracker.stepHistory.length !== 1) throw new Error('Step history not updated');
        if (tracker.stepHistory[0].status !== 'completed') throw new Error('Step status not updated');
        
        console.log('✓ Step progression test passed');
    }

    // Test ETA calculation
    async testETACalculation() {
        const tracker = new ProgressTracker();
        tracker.startTracking(4, 8);
        
        // Complete some steps to enable ETA calculation
        tracker.startStep('step1', 'Step 1', 2);
        await this.simulateDelay(100);
        tracker.updateStepProgress(1, 'item1');
        await this.simulateDelay(100);
        tracker.updateStepProgress(2, 'item2');
        tracker.completeStep();
        
        tracker.startStep('step2', 'Step 2', 2);
        await this.simulateDelay(100);
        tracker.updateStepProgress(1, 'item3');
        
        // Calculate ETA
        const eta = tracker.calculateETA();
        
        if (typeof eta.remaining !== 'number') throw new Error('ETA remaining should be a number');
        if (typeof eta.formatted !== 'string') throw new Error('ETA formatted should be a string');
        if (!['low', 'medium', 'high'].includes(eta.confidence)) throw new Error('Invalid confidence level');
        
        console.log('✓ ETA calculation test passed');
    }

    // Test statistics generation
    async testStatisticsGeneration() {
        const tracker = new ProgressTracker();
        tracker.startTracking(3, 6);
        
        // Add some progress
        tracker.startStep('validation', 'Validation', 3);
        tracker.updateStepProgress(1, 'file1.jpg');
        tracker.updateStepProgress(2, 'file2.jpg');
        
        const stats = tracker.getStatistics();
        
        // Verify statistics structure
        if (!stats.timing) throw new Error('Statistics missing timing data');
        if (!stats.progress) throw new Error('Statistics missing progress data');
        if (!stats.performance) throw new Error('Statistics missing performance data');
        if (!stats.steps) throw new Error('Statistics missing steps data');
        
        // Verify timing data
        if (typeof stats.timing.totalElapsed !== 'number') throw new Error('Invalid total elapsed time');
        if (typeof stats.timing.totalElapsedFormatted !== 'string') throw new Error('Invalid formatted elapsed time');
        
        // Verify progress data
        if (typeof stats.progress.overall !== 'number') throw new Error('Invalid overall progress');
        if (stats.progress.steps.total !== 3) throw new Error('Invalid total steps in stats');
        if (stats.progress.items.total !== 6) throw new Error('Invalid total items in stats');
        
        console.log('✓ Statistics generation test passed');
    }

    // Test performance metrics
    async testPerformanceMetrics() {
        const tracker = new ProgressTracker();
        tracker.startTracking(2, 4);
        
        tracker.startStep('processing', 'Processing', 2);
        
        // Simulate processing with timing
        await this.simulateDelay(100);
        tracker.updateStepProgress(1, 'item1');
        await this.simulateDelay(100);
        tracker.updateStepProgress(2, 'item2');
        
        const stats = tracker.getStatistics();
        const performanceMetrics = stats.performance.currentStepMetrics;
        
        if (!performanceMetrics) throw new Error('Performance metrics not generated');
        if (typeof performanceMetrics.itemsPerSecond !== 'number') throw new Error('Invalid items per second');
        if (typeof performanceMetrics.averageItemTime !== 'number') throw new Error('Invalid average item time');
        
        console.log('✓ Performance metrics test passed');
    }

    // Test callback system
    async testCallbackSystem() {
        const tracker = new ProgressTracker();
        
        let progressCalled = false;
        let stepCalled = false;
        let etaCalled = false;
        let statisticsCalled = false;
        
        tracker.setCallbacks(
            (progress) => { progressCalled = true; },
            (step) => { stepCalled = true; },
            (eta) => { etaCalled = true; },
            (stats) => { statisticsCalled = true; }
        );
        
        tracker.startTracking(2, 2);
        tracker.startStep('test', 'Test Step', 1);
        tracker.updateStepProgress(1, 'test-item');
        
        if (!progressCalled) throw new Error('Progress callback not called');
        if (!stepCalled) throw new Error('Step callback not called');
        if (!etaCalled) throw new Error('ETA callback not called');
        if (!statisticsCalled) throw new Error('Statistics callback not called');
        
        console.log('✓ Callback system test passed');
    }

    // Test error handling
    async testErrorHandling() {
        const tracker = new ProgressTracker();
        
        // Test updating progress without active step
        tracker.updateStepProgress(1, 'test-item');  // Should not throw
        
        // Test completing step without active step
        tracker.completeStep();  // Should not throw
        
        // Test ETA calculation with no data
        const eta = tracker.calculateETA();
        if (eta.remaining !== null || eta.formatted !== 'Calculating...') {
            throw new Error('ETA should handle no-data case');
        }
        
        console.log('✓ Error handling test passed');
    }

    // Test reset functionality
    async testResetFunctionality() {
        const tracker = new ProgressTracker();
        
        // Set up some state
        tracker.startTracking(3, 6);
        tracker.startStep('test', 'Test', 2);
        tracker.updateStepProgress(1, 'item1');
        
        // Reset
        tracker.reset();
        
        if (tracker.startTime !== null) throw new Error('Start time not reset');
        if (tracker.currentStep !== null) throw new Error('Current step not reset');
        if (tracker.totalSteps !== 0) throw new Error('Total steps not reset');
        if (tracker.stepHistory.length !== 0) throw new Error('Step history not reset');
        
        console.log('✓ Reset functionality test passed');
    }

    // Test complex scenario with multiple steps and items
    async testComplexScenario() {
        const tracker = new ProgressTracker();
        
        // Define custom step definitions
        const stepDefinitions = [
            { id: 'load', name: 'Loading Images', estimatedDuration: 1000, weight: 0.2 },
            { id: 'process', name: 'Processing Images', estimatedDuration: 3000, weight: 0.5 },
            { id: 'encode', name: 'Encoding Video', estimatedDuration: 2000, weight: 0.3 }
        ];
        
        tracker.startTracking(3, 9, stepDefinitions);
        
        // Step 1: Loading
        tracker.startStep('load', null, 3);
        for (let i = 1; i <= 3; i++) {
            await this.simulateDelay(50);
            tracker.updateStepProgress(i, `image${i}.jpg`, `Loading image ${i}`);
        }
        tracker.completeStep();
        
        // Step 2: Processing
        tracker.startStep('process', null, 3);
        for (let i = 1; i <= 3; i++) {
            await this.simulateDelay(100);
            tracker.updateStepProgress(i, `image${i}.jpg`, `Processing image ${i}`);
        }
        tracker.completeStep();
        
        // Step 3: Encoding
        tracker.startStep('encode', null, 3);
        for (let i = 1; i <= 3; i++) {
            await this.simulateDelay(75);
            tracker.updateStepProgress(i, `frame${i}`, `Encoding frame ${i}`);
        }
        tracker.completeStep();
        
        // Complete tracking
        const finalStats = tracker.completeTracking();
        
        // Verify final state
        if (finalStats.progress.overall !== 100) throw new Error('Final progress should be 100%');
        if (finalStats.progress.steps.completed !== 3) throw new Error('All steps should be completed');
        if (finalStats.steps.length !== 3) throw new Error('Should have 3 steps in history');
        
        // Verify all steps are completed
        const allCompleted = finalStats.steps.every(step => step.status === 'completed');
        if (!allCompleted) throw new Error('All steps should be marked as completed');
        
        console.log('✓ Complex scenario test passed');
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
        
        console.log('Progress Tracker Test Report:');
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
window.ProgressTrackerTests = ProgressTrackerTests;

// Auto-run tests if this script is loaded directly
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', async () => {
        // Only auto-run if we're in a test environment
        if (window.location.pathname.includes('test') || window.location.search.includes('test=progress')) {
            const tests = new ProgressTrackerTests();
            await tests.runAllTests();
        }
    });
}
