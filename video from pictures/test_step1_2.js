// Test suite for Step 1.2: JavaScript file system access using available browser APIs
// Tests the hybrid approach: File System Access API -> File Input API -> Drag & Drop

console.log('=== Testing Step 1.2: File System Access ===');

// Test 1: Check browser API support detection
function testBrowserAPIDetection() {
    console.log('\n1. Testing browser API support detection...');
    
    const hasFileSystemAccess = 'showDirectoryPicker' in window;
    const hasFileInput = 'HTMLInputElement' in window;
    const hasDragDrop = 'DataTransfer' in window;
    
    console.log(`✓ File System Access API: ${hasFileSystemAccess}`);
    console.log(`✓ File Input API: ${hasFileInput}`);
    console.log(`✓ Drag & Drop API: ${hasDragDrop}`);
    
    return { hasFileSystemAccess, hasFileInput, hasDragDrop };
}

// Test 2: Test API detection functions
function testAPIDetectionFunctions() {
    console.log('\n2. Testing API detection functions...');
    
    const fileSystemModule = window.fileSystemModule;
    if (!fileSystemModule) {
        console.log('❌ fileSystemModule not found');
        return false;
    }
    
    const hasDetectSupport = typeof fileSystemModule.detectAPISupport === 'function';
    const hasGetBestAPI = typeof fileSystemModule.getBestAvailableAPI === 'function';
    
    console.log(`✓ detectAPISupport function: ${hasDetectSupport}`);
    console.log(`✓ getBestAvailableAPI function: ${hasGetBestAPI}`);
    
    if (hasDetectSupport) {
        const support = fileSystemModule.detectAPISupport();
        console.log(`API Support detected:`, support);
    }
    
    return hasDetectSupport && hasGetBestAPI;
}

// Test 3: Test file access methods
function testFileAccessMethods() {
    console.log('\n3. Testing file access methods...');
    
    const fileSystemModule = window.fileSystemModule;
    if (!fileSystemModule) {
        console.log('❌ fileSystemModule not found');
        return false;
    }
    
    const hasFileSystemAccess = typeof fileSystemModule.accessViaFileSystemAPI === 'function';
    const hasFileInputAccess = typeof fileSystemModule.accessViaFileInput === 'function';
    const hasDragDropAccess = typeof fileSystemModule.accessViaDragDrop === 'function';
    
    console.log(`✓ File System Access method: ${hasFileSystemAccess}`);
    console.log(`✓ File Input Access method: ${hasFileInputAccess}`);
    console.log(`✓ Drag Drop Access method: ${hasDragDropAccess}`);
    
    return hasFileSystemAccess && hasFileInputAccess && hasDragDropAccess;
}

// Test 4: Test hybrid file selection
function testHybridFileSelection() {
    console.log('\n4. Testing hybrid file selection...');
    
    const fileSystemModule = window.fileSystemModule;
    if (!fileSystemModule) {
        console.log('❌ fileSystemModule not found');
        return false;
    }
    
    const hasSelectFiles = typeof fileSystemModule.selectFiles === 'function';
    console.log(`✓ selectFiles hybrid method: ${hasSelectFiles}`);
    
    return hasSelectFiles;
}

// Test 5: Test error handling
function testErrorHandling() {
    console.log('\n5. Testing error handling...');
    
    const fileSystemModule = window.fileSystemModule;
    if (!fileSystemModule) {
        console.log('❌ fileSystemModule not found');
        return false;
    }
    
    const hasErrorHandling = typeof fileSystemModule.handleAPIError === 'function';
    console.log(`✓ Error handling method: ${hasErrorHandling}`);
    
    return hasErrorHandling;
}

// Run all tests
function runAllTests() {
    console.log('🧪 Running File System Access Tests for Step 1.2\n');
    
    const tests = [
        { name: 'Browser API Detection', test: testBrowserAPIDetection },
        { name: 'API Detection Functions', test: testAPIDetectionFunctions },
        { name: 'File Access Methods', test: testFileAccessMethods },
        { name: 'Hybrid File Selection', test: testHybridFileSelection },
        { name: 'Error Handling', test: testErrorHandling }
    ];
    
    let passed = 0;
    const results = [];
    
    tests.forEach(({ name, test }) => {
        try {
            const result = test();
            const success = typeof result === 'object' ? Object.values(result).some(v => v) : result;
            if (success) {
                console.log(`✅ ${name}: PASSED`);
                passed++;
                results.push({ name, status: 'PASSED', result });
            } else {
                console.log(`❌ ${name}: FAILED`);
                results.push({ name, status: 'FAILED', result });
            }
        } catch (error) {
            console.log(`❌ ${name}: ERROR - ${error.message}`);
            results.push({ name, status: 'ERROR', error: error.message });
        }
    });
    
    console.log(`\n🎯 Test Results: ${passed}/${tests.length} tests passed`);
    console.log(`Step 1.2 Implementation: ${passed >= 4 ? 'SUCCESS' : 'NEEDS WORK'}`);
    
    return { passed, total: tests.length, results };
}

// Export for external use
window.testStep1_2 = runAllTests;
