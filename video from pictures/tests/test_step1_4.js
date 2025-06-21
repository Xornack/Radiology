// Test Step 1.4: File Sorting Algorithm
// Comprehensive test suite for natural/numerical sorting functionality

describe('Step 1.4: File Sorting Algorithm Tests', function() {
    let testInterface;
    let fileSystemModule;

    before(function() {
        // Wait for modules to load
        return new Promise(resolve => {
            const checkModules = () => {
                if (window.testInterface && window.fileSystemModule) {
                    testInterface = window.testInterface;
                    fileSystemModule = window.fileSystemModule;
                    resolve();
                } else {
                    setTimeout(checkModules, 100);
                }
            };
            checkModules();
        });
    });

    describe('Natural/Numerical Sorting Algorithm', function() {
        it('should sort simple numerical sequences correctly', function() {
            const mockFiles = [
                createMockFile('img10.jpg'),
                createMockFile('img1.jpg'),
                createMockFile('img2.jpg'),
                createMockFile('img20.jpg')
            ];

            const sorted = testInterface.sortFilesNatural(mockFiles);
            const sortedNames = sorted.map(f => f.name);
            
            chai.expect(sortedNames).to.deep.equal([
                'img1.jpg',
                'img2.jpg', 
                'img10.jpg',
                'img20.jpg'
            ]);
        });

        it('should handle zero-padded numbers correctly', function() {
            const mockFiles = [
                createMockFile('scan010.jpg'),
                createMockFile('scan001.jpg'),
                createMockFile('scan002.jpg'),
                createMockFile('scan100.jpg')
            ];

            const sorted = testInterface.sortFilesNatural(mockFiles);
            const sortedNames = sorted.map(f => f.name);
            
            chai.expect(sortedNames).to.deep.equal([
                'scan001.jpg',
                'scan002.jpg',
                'scan010.jpg',
                'scan100.jpg'
            ]);
        });

        it('should handle mixed text and numbers', function() {
            const mockFiles = [
                createMockFile('slice_10_axial.jpg'),
                createMockFile('slice_2_axial.jpg'),
                createMockFile('slice_1_axial.jpg'),
                createMockFile('slice_20_axial.jpg')
            ];

            const sorted = testInterface.sortFilesNatural(mockFiles);
            const sortedNames = sorted.map(f => f.name);
            
            chai.expect(sortedNames).to.deep.equal([
                'slice_1_axial.jpg',
                'slice_2_axial.jpg',
                'slice_10_axial.jpg',
                'slice_20_axial.jpg'
            ]);
        });

        it('should handle case-insensitive sorting', function() {
            const mockFiles = [
                createMockFile('IMG10.JPG'),
                createMockFile('img1.jpg'),
                createMockFile('Img2.Jpg'),
                createMockFile('IMG20.JPG')
            ];

            const sorted = testInterface.sortFilesNatural(mockFiles);
            const sortedNames = sorted.map(f => f.name);
            
            chai.expect(sortedNames).to.deep.equal([
                'img1.jpg',
                'Img2.Jpg',
                'IMG10.JPG',
                'IMG20.JPG'
            ]);
        });

        it('should handle medical imaging filename patterns', function() {
            const mockFiles = [
                createMockFile('CT_Head_Slice_100.jpg'),
                createMockFile('CT_Head_Slice_1.jpg'),
                createMockFile('CT_Head_Slice_50.jpg'),
                createMockFile('CT_Head_Slice_2.jpg')
            ];

            const sorted = testInterface.sortFilesNatural(mockFiles);
            const sortedNames = sorted.map(f => f.name);
            
            chai.expect(sortedNames).to.deep.equal([
                'CT_Head_Slice_1.jpg',
                'CT_Head_Slice_2.jpg',
                'CT_Head_Slice_50.jpg',
                'CT_Head_Slice_100.jpg'
            ]);
        });

        it('should handle files with no numbers alphabetically', function() {
            const mockFiles = [
                createMockFile('zebra.jpg'),
                createMockFile('apple.jpg'),
                createMockFile('banana.jpg')
            ];

            const sorted = testInterface.sortFilesNatural(mockFiles);
            const sortedNames = sorted.map(f => f.name);
            
            chai.expect(sortedNames).to.deep.equal([
                'apple.jpg',
                'banana.jpg',
                'zebra.jpg'
            ]);
        });
    });

    describe('Date-based Sorting', function() {
        it('should sort files by modification date', function() {
            const mockFiles = [
                createMockFile('newest.jpg', 1000, Date.now()),
                createMockFile('oldest.jpg', 1000, Date.now() - 3000),
                createMockFile('middle.jpg', 1000, Date.now() - 1000)
            ];

            const sorted = testInterface.sortFilesByDate(mockFiles);
            const sortedNames = sorted.map(f => f.name);
            
            chai.expect(sortedNames).to.deep.equal([
                'oldest.jpg',
                'middle.jpg',
                'newest.jpg'
            ]);
        });

        it('should handle files with missing dates', function() {
            const mockFiles = [
                createMockFile('with_date.jpg', 1000, Date.now()),
                createMockFile('no_date.jpg', 1000, 0),
                createMockFile('also_no_date.jpg', 1000, undefined)
            ];

            const sorted = testInterface.sortFilesByDate(mockFiles);
            const sortedNames = sorted.map(f => f.name);
            
            // Files with missing dates (0 or undefined) should come first
            chai.expect(sortedNames).to.deep.equal([
                'no_date.jpg',
                'also_no_date.jpg',
                'with_date.jpg'
            ]);
        });
    });

    describe('Sorting Method Selection', function() {
        it('should use correct sorting method with sortFiles() function', function() {
            const mockFiles = [
                createMockFile('img10.jpg'),
                createMockFile('img1.jpg'),
                createMockFile('img2.jpg')
            ];

            // Test natural sorting
            const naturalSorted = testInterface.sortFiles(mockFiles, 'natural');
            const naturalNames = naturalSorted.map(f => f.name);
            chai.expect(naturalNames).to.deep.equal(['img1.jpg', 'img2.jpg', 'img10.jpg']);

            // Test date sorting
            const dateSorted = testInterface.sortFiles(mockFiles, 'dateModified');
            chai.expect(dateSorted).to.be.an('array');
            chai.expect(dateSorted.length).to.equal(3);
        });

        it('should default to natural sorting for unknown methods', function() {
            const mockFiles = [
                createMockFile('img10.jpg'),
                createMockFile('img1.jpg')
            ];

            const sorted = testInterface.sortFiles(mockFiles, 'unknownMethod');
            const sortedNames = sorted.map(f => f.name);
            
            chai.expect(sortedNames).to.deep.equal(['img1.jpg', 'img10.jpg']);
        });
    });

    describe('Sorting Pattern Analysis', function() {
        it('should recommend natural sorting for numeric filenames', function() {
            const mockFiles = [
                createMockFile('img001.jpg'),
                createMockFile('img002.jpg'),
                createMockFile('img003.jpg'),
                createMockFile('img004.jpg'),
                createMockFile('img005.jpg')
            ];

            const analysis = testInterface.analyzeSortingPattern(mockFiles);
            
            chai.expect(analysis.recommended).to.equal('natural');
            chai.expect(analysis.confidence).to.be.above(0.6);
            chai.expect(analysis.reason).to.include('numeric pattern');
        });

        it('should recommend date sorting for non-numeric filenames', function() {
            const mockFiles = [
                createMockFile('random_name_a.jpg'),
                createMockFile('another_file.jpg'),
                createMockFile('some_image.jpg')
            ];

            const analysis = testInterface.analyzeSortingPattern(mockFiles);
            
            // With low numeric pattern, should recommend date sorting
            chai.expect(analysis.recommended).to.equal('dateModified');
            chai.expect(analysis.reason).to.include('Low numeric pattern');
        });

        it('should handle empty file arrays', function() {
            const analysis = testInterface.analyzeSortingPattern([]);
            
            chai.expect(analysis.confidence).to.equal(0);
            chai.expect(analysis.reason).to.include('No files to analyze');
        });
    });

    describe('Edge Cases and Error Handling', function() {
        it('should handle empty file arrays gracefully', function() {
            const naturalSorted = testInterface.sortFilesNatural([]);
            const dateSorted = testInterface.sortFilesByDate([]);
            
            chai.expect(naturalSorted).to.be.an('array');
            chai.expect(naturalSorted.length).to.equal(0);
            chai.expect(dateSorted).to.be.an('array');
            chai.expect(dateSorted.length).to.equal(0);
        });

        it('should handle single file arrays', function() {
            const mockFiles = [createMockFile('single.jpg')];
            
            const naturalSorted = testInterface.sortFilesNatural(mockFiles);
            const dateSorted = testInterface.sortFilesByDate(mockFiles);
            
            chai.expect(naturalSorted.length).to.equal(1);
            chai.expect(naturalSorted[0].name).to.equal('single.jpg');
            chai.expect(dateSorted.length).to.equal(1);
            chai.expect(dateSorted[0].name).to.equal('single.jpg');
        });

        it('should not modify original array', function() {
            const mockFiles = [
                createMockFile('img10.jpg'),
                createMockFile('img1.jpg')
            ];
            const originalNames = mockFiles.map(f => f.name);
            
            const sorted = testInterface.sortFilesNatural(mockFiles);
            const currentNames = mockFiles.map(f => f.name);
            
            // Original array should be unchanged
            chai.expect(currentNames).to.deep.equal(originalNames);
            
            // Sorted array should be different
            const sortedNames = sorted.map(f => f.name);
            chai.expect(sortedNames).to.not.deep.equal(originalNames);
        });
    });

    describe('Integration with UI', function() {
        it('should expose sorting functions in testInterface', function() {
            chai.expect(testInterface.sortFiles).to.be.a('function');
            chai.expect(testInterface.sortFilesNatural).to.be.a('function');
            chai.expect(testInterface.sortFilesByDate).to.be.a('function');
            chai.expect(testInterface.analyzeSortingPattern).to.be.a('function');
            chai.expect(testInterface.changeSortingMethod).to.be.a('function');
            chai.expect(testInterface.displaySortingInfo).to.be.a('function');
        });

        it('should handle changeSortingMethod with no files', function() {
            // Clear any existing files
            if (window.selectedFiles) {
                window.selectedFiles = [];
            }
            
            // This should not throw an error
            chai.expect(() => {
                testInterface.changeSortingMethod('natural');
            }).to.not.throw();
        });
    });

    // Helper function to create mock File objects
    function createMockFile(name, size = 1024, lastModified = Date.now()) {
        const file = {
            name: name,
            size: size,
            type: 'image/jpeg',
            lastModified: lastModified
        };
        
        // Add additional File-like properties
        Object.defineProperty(file, 'webkitRelativePath', {
            value: '',
            writable: true
        });
        
        return file;
    }
});

// Export for external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        testSuite: 'Step 1.4: File Sorting Algorithm Tests',
        description: 'Tests natural/numerical sorting, date sorting, and pattern analysis for medical image sequences'
    };
}

console.log('✅ Step 1.4 tests loaded: File Sorting Algorithm');
