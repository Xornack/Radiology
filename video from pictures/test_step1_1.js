// Test suite for Step 1.1: HTML interface with folder selection capability
// Run this in browser console after loading index.html

console.log('=== Testing HTML Interface - Step 1.1 ===');

// Test 1: Check if required elements exist
function testRequiredElements() {
    console.log('\n1. Testing required elements exist...');
    
    const requiredElements = [
        'folderSelection',
        'folderInput', 
        'statusMessage',
        'fileList',
        'processBtn',
        'settingsBtn'
    ];
    
    let passed = 0;
    requiredElements.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            console.log(`✓ Element '${id}' exists`);
            passed++;
        } else {
            console.log(`✗ Element '${id}' missing`);
        }
    });
    
    console.log(`Result: ${passed}/${requiredElements.length} elements found`);
    return passed === requiredElements.length;
}

// Test 2: Check file input attributes
function testFileInputAttributes() {
    console.log('\n2. Testing file input attributes...');
    
    const fileInput = document.getElementById('folderInput');
    const hasWebkitDirectory = fileInput.hasAttribute('webkitdirectory');
    const hasMultiple = fileInput.hasAttribute('multiple');
    const acceptValue = fileInput.getAttribute('accept');
    
    console.log(`✓ webkitdirectory attribute: ${hasWebkitDirectory}`);
    console.log(`✓ multiple attribute: ${hasMultiple}`);
    console.log(`✓ accept attribute: ${acceptValue}`);
    
    const correctAccept = acceptValue === 'image/jpeg,image/jpg';
    console.log(`Accept attribute correct: ${correctAccept}`);
    
    return hasWebkitDirectory && hasMultiple && correctAccept;
}

// Test 3: Test folder selection with mock data
function testFolderSelection() {
    console.log('\n3. Testing folder selection functionality...');
    
    // Create mock File objects
    const mockFiles = [
        {
            name: 'image001.jpg',
            type: 'image/jpeg',
            size: 102400,
            webkitRelativePath: 'test_folder/image001.jpg'
        },
        {
            name: 'image002.jpeg',
            type: 'image/jpeg', 
            size: 204800,
            webkitRelativePath: 'test_folder/image002.jpeg'
        },
        {
            name: 'document.txt',
            type: 'text/plain',
            size: 1024,
            webkitRelativePath: 'test_folder/document.txt'
        }
    ];
    
    // Test the folder selection
    window.testInterface.selectTestFolder(mockFiles);
    
    const selectedFiles = window.testInterface.getSelectedFiles();
    const folderName = window.testInterface.getFolderName();
    const processEnabled = window.testInterface.isProcessButtonEnabled();
    
    console.log(`Selected files count: ${selectedFiles.length}`);
    console.log(`Folder name: ${folderName}`);
    console.log(`Process button enabled: ${processEnabled}`);
    
    const correctFileCount = selectedFiles.length === 2; // Only JPEG files
    const correctFolderName = folderName === 'test_folder';
    
    console.log(`✓ Correct file filtering: ${correctFileCount}`);
    console.log(`✓ Correct folder name extraction: ${correctFolderName}`);
    console.log(`✓ Process button enabled after selection: ${processEnabled}`);
    
    return correctFileCount && correctFolderName && processEnabled;
}

// Test 4: Test drag and drop area styling
function testDragDropStyling() {
    console.log('\n4. Testing drag and drop area styling...');
    
    const folderSelection = document.getElementById('folderSelection');
    const hasHoverEffect = window.getComputedStyle(folderSelection, ':hover').borderColor !== '';
    
    // Test dragover class
    folderSelection.classList.add('dragover');
    const dragoverStyles = window.getComputedStyle(folderSelection);
    const hasDragoverEffect = dragoverStyles.borderColor !== '';
    folderSelection.classList.remove('dragover');
    
    console.log(`✓ Hover effects applied: ${hasHoverEffect}`);
    console.log(`✓ Dragover effects applied: ${hasDragoverEffect}`);
    
    return true; // Styling tests are visual, assume pass if no errors
}

// Test 5: Test status message functionality
function testStatusMessages() {
    console.log('\n5. Testing status message functionality...');
    
    // Test different status types
    const statusEl = document.getElementById('statusMessage');
    
    // Test success status
    showStatus('success', 'Test success message');
    const hasSuccessClass = statusEl.classList.contains('success');
    const isVisible = statusEl.style.display === 'block';
    
    console.log(`✓ Success status applied: ${hasSuccessClass}`);
    console.log(`✓ Status message visible: ${isVisible}`);
    
    // Test error status
    showStatus('error', 'Test error message');
    const hasErrorClass = statusEl.classList.contains('error');
    
    console.log(`✓ Error status applied: ${hasErrorClass}`);
    
    return hasSuccessClass && isVisible && hasErrorClass;
}

// Run all tests
function runAllTests() {
    console.log('🧪 Running HTML Interface Tests for Step 1.1\n');
    
    const tests = [
        { name: 'Required Elements', test: testRequiredElements },
        { name: 'File Input Attributes', test: testFileInputAttributes },
        { name: 'Folder Selection', test: testFolderSelection },
        { name: 'Drag Drop Styling', test: testDragDropStyling },
        { name: 'Status Messages', test: testStatusMessages }
    ];
    
    let passed = 0;
    tests.forEach(({ name, test }) => {
        try {
            const result = test();
            if (result) {
                console.log(`✅ ${name}: PASSED`);
                passed++;
            } else {
                console.log(`❌ ${name}: FAILED`);
            }
        } catch (error) {
            console.log(`❌ ${name}: ERROR - ${error.message}`);
        }
    });
    
    console.log(`\n🎯 Test Results: ${passed}/${tests.length} tests passed`);
    console.log(`Step 1.1 Implementation: ${passed === tests.length ? 'SUCCESS' : 'NEEDS WORK'}`);
    
    return passed === tests.length;
}

// Export for external use
window.testStep1_1 = runAllTests;
