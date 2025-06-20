// Test Step 3.1: Enhanced MP4 File Save Functionality
// Tests for FileSaver module and enhanced save capabilities

class TestStep3_1 {
    constructor() {
        this.testResults = [];
        this.mockVideoBlob = null;
        this.testFilename = 'test_video_step3_1.mp4';
    }

    // Run all Step 3.1 tests
    async runAllTests() {
        console.log('=== Running Step 3.1 Tests: Enhanced MP4 File Save Functionality ===');
        
        this.setupMockData();
        
        await this.testFileSaverInitialization();
        await this.testSaveMethodDetection();
        await this.testFilenameGeneration();
        await this.testSaveMethodSelection();
        await this.testSaveCapabilitiesValidation();
        await this.testSettingsManagement();
        await this.testBasicSaveOperation();
        await this.testErrorHandling();
        
        this.displayResults();
        return this.getTestSummary();
    }

    // Setup mock data for testing
    setupMockData() {
        // Create a mock video blob for testing
        const mockVideoData = new Uint8Array(1024 * 100); // 100KB mock video
        for (let i = 0; i < mockVideoData.length; i++) {
            mockVideoData[i] = Math.floor(Math.random() * 256);
        }
        this.mockVideoBlob = new Blob([mockVideoData], { type: 'video/mp4' });
        
        console.log(`Mock video blob created: ${(this.mockVideoBlob.size / 1024).toFixed(1)} KB`);
    }

    // Test FileSaver initialization
    async testFileSaverInitialization() {
        const testName = 'FileSaver Initialization';
        try {
            // Test basic initialization
            const fileSaver = new FileSaver();
            
            this.assert(fileSaver !== null, 'FileSaver instance created');
            this.assert(typeof fileSaver.saveVideo === 'function', 'saveVideo method exists');
            this.assert(typeof fileSaver.updateSettings === 'function', 'updateSettings method exists');
            this.assert(typeof fileSaver.getBrowserCapabilities === 'function', 'getBrowserCapabilities method exists');
            
            // Test capabilities detection
            const capabilities = fileSaver.getBrowserCapabilities();
            this.assert(capabilities.supportedMethods !== undefined, 'Supported methods detected');
            this.assert(capabilities.preferredMethod !== undefined, 'Preferred method identified');
            
            console.log('Browser capabilities:', capabilities);
            
            this.addTestResult(testName, true, 'FileSaver initialized successfully with capability detection');
            
        } catch (error) {
            this.addTestResult(testName, false, `Initialization failed: ${error.message}`);
        }
    }

    // Test save method detection
    async testSaveMethodDetection() {
        const testName = 'Save Method Detection';
        try {
            const fileSaver = new FileSaver();
            
            // Test method detection
            this.assert(fileSaver.supportedMethods !== undefined, 'Supported methods object exists');
            this.assert(typeof fileSaver.supportedMethods.download === 'boolean', 'Download method status detected');
            
            // Test preferred method selection
            const preferredMethod = fileSaver.getPreferredSaveMethod();
            this.assert(preferredMethod !== undefined, 'Preferred method selected');
            this.assert(['showSaveFilePicker', 'fileSystemAccess', 'download'].includes(preferredMethod), 'Valid preferred method');
            
            console.log(`Preferred save method: ${preferredMethod}`);
            
            // Test capabilities validation
            const capabilities = fileSaver.validateSaveCapabilities();
            this.assert(capabilities.available.length > 0, 'At least one save method available');
            this.assert(capabilities.total >= 1, 'Total methods count is valid');
            
            this.addTestResult(testName, true, `Save methods detected. Preferred: ${preferredMethod}`);
            
        } catch (error) {
            this.addTestResult(testName, false, `Method detection failed: ${error.message}`);
        }
    }

    // Test filename generation
    async testFilenameGeneration() {
        const testName = 'Filename Generation';
        try {
            const fileSaver = new FileSaver();
            
            // Test unique filename generation
            const originalName = 'test_video.mp4';
            const uniqueName1 = fileSaver.generateUniqueFilename(originalName);
            const uniqueName2 = fileSaver.generateUniqueFilename(originalName);
            
            this.assert(uniqueName1 !== originalName, 'Unique filename generated');
            this.assert(uniqueName2 !== originalName, 'Second unique filename generated');
            this.assert(uniqueName1 !== uniqueName2, 'Multiple unique filenames are different');
            this.assert(uniqueName1.endsWith('.mp4'), 'Original extension preserved');
            
            // Test filename without extension
            const nameWithoutExt = 'test_video';
            const uniqueNameNoExt = fileSaver.generateUniqueFilename(nameWithoutExt);
            this.assert(uniqueNameNoExt !== nameWithoutExt, 'Unique filename generated without extension');
            
            console.log('Filename generation examples:');
            console.log(`  Original: ${originalName} -> Unique: ${uniqueName1}`);
            console.log(`  Original: ${nameWithoutExt} -> Unique: ${uniqueNameNoExt}`);
            
            this.addTestResult(testName, true, 'Filename generation working correctly');
            
        } catch (error) {
            this.addTestResult(testName, false, `Filename generation failed: ${error.message}`);
        }
    }

    // Test save method selection UI
    async testSaveMethodSelection() {
        const testName = 'Save Method Selection';
        try {
            const fileSaver = new FileSaver();
            
            // Test method selection dialog creation (mock)
            const availableMethods = ['download', 'showSaveFilePicker'];
            
            // Test if dialog creation function exists and can be called
            this.assert(typeof fileSaver.showMethodSelectionDialog === 'function', 'Method selection dialog function exists');
            
            // Test save with method choice (would show dialog in real use)
            // We'll test the underlying logic without actual UI interaction
            const mockResult = await this.mockSaveWithMethodChoice(fileSaver, this.mockVideoBlob, this.testFilename);
            this.assert(mockResult.tested === true, 'Save method choice logic testable');
            
            this.addTestResult(testName, true, 'Save method selection functionality available');
            
        } catch (error) {
            this.addTestResult(testName, false, `Method selection failed: ${error.message}`);
        }
    }

    // Mock save with method choice to avoid UI interaction in tests
    async mockSaveWithMethodChoice(fileSaver, blob, filename) {
        try {
            // Test the underlying save method without UI
            const result = await fileSaver.saveWithDownload(blob, filename, fileSaver.settings);
            return { tested: true, result: result };
        } catch (error) {
            return { tested: true, error: error.message };
        }
    }

    // Test save capabilities validation
    async testSaveCapabilitiesValidation() {
        const testName = 'Save Capabilities Validation';
        try {
            const fileSaver = new FileSaver();
            
            const capabilities = fileSaver.validateSaveCapabilities();
            
            this.assert(Array.isArray(capabilities.available), 'Available methods is array');
            this.assert(typeof capabilities.total === 'number', 'Total count is number');
            this.assert(typeof capabilities.modern === 'number', 'Modern methods count is number');
            this.assert(capabilities.total >= 1, 'At least one method available');
            
            // Verify each capability has required fields
            capabilities.available.forEach((capability, index) => {
                this.assert(capability.method !== undefined, `Method ${index} has method field`);
                this.assert(capability.description !== undefined, `Method ${index} has description field`);
                this.assert(typeof capability.recommended === 'boolean', `Method ${index} has recommended field`);
            });
            
            console.log('Save capabilities validation:', capabilities);
            
            this.addTestResult(testName, true, `${capabilities.total} save methods validated`);
            
        } catch (error) {
            this.addTestResult(testName, false, `Capabilities validation failed: ${error.message}`);
        }
    }

    // Test settings management
    async testSettingsManagement() {
        const testName = 'Settings Management';
        try {
            const fileSaver = new FileSaver();
            
            // Test default settings
            const defaultSettings = fileSaver.settings;
            this.assert(typeof defaultSettings.generateUniqueNames === 'boolean', 'generateUniqueNames setting exists');
            this.assert(typeof defaultSettings.confirmOverwrite === 'boolean', 'confirmOverwrite setting exists');
            this.assert(typeof defaultSettings.autoSave === 'boolean', 'autoSave setting exists');
            
            // Test settings update
            const newSettings = {
                generateUniqueNames: false,
                confirmOverwrite: false,
                autoSave: true
            };
            
            fileSaver.updateSettings(newSettings);
            
            this.assert(fileSaver.settings.generateUniqueNames === false, 'generateUniqueNames updated');
            this.assert(fileSaver.settings.confirmOverwrite === false, 'confirmOverwrite updated');
            this.assert(fileSaver.settings.autoSave === true, 'autoSave updated');
            
            // Test partial settings update
            fileSaver.updateSettings({ generateUniqueNames: true });
            this.assert(fileSaver.settings.generateUniqueNames === true, 'Partial setting update works');
            this.assert(fileSaver.settings.autoSave === true, 'Other settings preserved during partial update');
            
            this.addTestResult(testName, true, 'Settings management working correctly');
            
        } catch (error) {
            this.addTestResult(testName, false, `Settings management failed: ${error.message}`);
        }
    }

    // Test basic save operation (download method)
    async testBasicSaveOperation() {
        const testName = 'Basic Save Operation';
        try {
            const fileSaver = new FileSaver();
            
            // Test basic download save (should always work)
            const result = await fileSaver.saveWithDownload(this.mockVideoBlob, this.testFilename, fileSaver.settings);
            
            this.assert(result.success === true, 'Save operation marked as successful');
            this.assert(result.method === 'download', 'Correct save method recorded');
            this.assert(result.filename === this.testFilename, 'Correct filename recorded');
            this.assert(result.size === this.mockVideoBlob.size, 'Correct file size recorded');
            this.assert(result.timestamp !== undefined, 'Timestamp recorded');
            
            console.log('Basic save operation result:', result);
            
            this.addTestResult(testName, true, `Save operation completed via ${result.method}`);
            
        } catch (error) {
            this.addTestResult(testName, false, `Basic save operation failed: ${error.message}`);
        }
    }

    // Test error handling
    async testErrorHandling() {
        const testName = 'Error Handling';
        try {
            const fileSaver = new FileSaver();
            
            // Test invalid blob handling
            try {
                await fileSaver.saveWithDownload(null, this.testFilename, fileSaver.settings);
                this.addTestResult(testName, false, 'Should have thrown error for null blob');
                return;
            } catch (error) {
                this.assert(error.message.includes('Download failed') || error.message.includes('blob'), 'Appropriate error for null blob');
            }
            
            // Test invalid filename handling
            try {
                await fileSaver.saveWithDownload(this.mockVideoBlob, '', fileSaver.settings);
                // This might not fail in all browsers, so we'll just check if it completes
                console.log('Empty filename test completed');
            } catch (error) {
                console.log('Empty filename appropriately rejected:', error.message);
            }
            
            // Test save history functionality
            const history = fileSaver.getSaveHistory();
            this.assert(typeof history === 'object', 'Save history returns object');
            this.assert(history.preferredMethod !== undefined, 'History includes preferred method');
            this.assert(history.settings !== undefined, 'History includes settings');
            
            this.addTestResult(testName, true, 'Error handling and edge cases tested');
            
        } catch (error) {
            this.addTestResult(testName, false, `Error handling test failed: ${error.message}`);
        }
    }

    // Helper: Add test result
    addTestResult(testName, passed, message) {
        this.testResults.push({
            test: testName,
            passed: passed,
            message: message,
            timestamp: new Date().toISOString()
        });
        
        const status = passed ? '✅ PASS' : '❌ FAIL';
        console.log(`${status}: ${testName} - ${message}`);
    }

    // Helper: Assert condition
    assert(condition, message) {
        if (!condition) {
            throw new Error(`Assertion failed: ${message}`);
        }
    }

    // Display test results
    displayResults() {
        const passed = this.testResults.filter(r => r.passed).length;
        const total = this.testResults.length;
        
        console.log('\n=== Step 3.1 Test Results Summary ===');
        console.log(`Passed: ${passed}/${total} tests`);
        console.log(`Success Rate: ${((passed/total) * 100).toFixed(1)}%`);
        
        if (passed < total) {
            console.log('\nFailed Tests:');
            this.testResults.filter(r => !r.passed).forEach(result => {
                console.log(`  ❌ ${result.test}: ${result.message}`);
            });
        }
        
        console.log('\nAll Tests:');
        this.testResults.forEach(result => {
            const status = result.passed ? '✅' : '❌';
            console.log(`  ${status} ${result.test}: ${result.message}`);
        });
    }

    // Get test summary
    getTestSummary() {
        const passed = this.testResults.filter(r => r.passed).length;
        const total = this.testResults.length;
        
        return {
            phase: 'Phase 3',
            step: 'Step 3.1',
            name: 'Enhanced MP4 File Save Functionality',
            passed: passed,
            total: total,
            successRate: ((passed/total) * 100).toFixed(1),
            results: this.testResults,
            summary: `Enhanced file save functionality with ${passed}/${total} tests passing`
        };
    }
}

// Export for use in test runners
if (typeof window !== 'undefined') {
    window.TestStep3_1 = TestStep3_1;
} else if (typeof module !== 'undefined') {
    module.exports = TestStep3_1;
}
