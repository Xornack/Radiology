// Video Reporter Module - Step 3.2 Support
// Generates comprehensive reports for video testing and validation
// Part of Phase 3: Output and Validation

class VideoReporter {
    constructor() {
        this.reportConfig = {
            includeMetadata: true,
            includeTestDetails: true,
            includeTimestamps: true,
            includeRecommendations: true,
            includeErrorDetails: true,
            formatStyle: 'detailed' // 'summary', 'detailed', 'technical'
        };
        
        console.log('VideoReporter initialized');
    }
    
    // Update report configuration
    updateConfig(newConfig) {
        this.reportConfig = { ...this.reportConfig, ...newConfig };
    }
    
    // Generate comprehensive video test report
    generateTestReport(testResults, videoBlob = null) {
        try {
            const report = {
                reportId: this.generateReportId(),
                timestamp: new Date().toISOString(),
                filename: testResults.filename,
                summary: this.generateSummary(testResults),
                details: this.generateDetailedReport(testResults),
                formatted: this.generateFormattedReport(testResults),
                exportable: this.generateExportableReport(testResults, videoBlob)
            };
            
            return report;
        } catch (error) {
            console.error('Failed to generate test report:', error);
            return {
                error: true,
                message: `Report generation failed: ${error.message}`,
                timestamp: new Date().toISOString()
            };
        }
    }
    
    // Generate summary of test results
    generateSummary(testResults) {
        const summary = {
            overall: testResults.success ? 'PASSED' : 'FAILED',
            filename: testResults.filename,
            testDuration: this.formatDuration(testResults.testDuration || 0),
            testsRun: Object.keys(testResults.tests).length,
            testsPassed: Object.values(testResults.tests).filter(t => t.status === 'passed').length,
            testsFailed: Object.values(testResults.tests).filter(t => t.status === 'failed').length,
            warnings: testResults.warnings ? testResults.warnings.length : 0,
            recommendations: testResults.recommendations ? testResults.recommendations.length : 0
        };
        
        // Add video properties summary
        if (testResults.videoProperties) {
            summary.videoInfo = {
                duration: this.formatDuration((testResults.videoProperties.duration || 0) * 1000),
                dimensions: testResults.videoProperties.finalDimensions || 'Unknown',
                fileSize: this.formatFileSize(testResults.videoProperties.fileSize || 0),
                aspectRatio: testResults.videoProperties.aspectRatio || 'Unknown'
            };
        }
        
        return summary;
    }
    
    // Generate detailed test report
    generateDetailedReport(testResults) {
        const details = {
            testExecution: {
                startTime: new Date(testResults.testStartTime).toISOString(),
                endTime: testResults.testEndTime ? new Date(testResults.testEndTime).toISOString() : null,
                duration: this.formatDuration(testResults.testDuration || 0),
                success: testResults.success
            },
            testResults: {},
            videoProperties: testResults.videoProperties || {},
            issues: {
                warnings: testResults.warnings || [],
                errors: [],
                recommendations: testResults.recommendations || []
            }
        };
        
        // Process individual test results
        for (const [testName, testResult] of Object.entries(testResults.tests || {})) {
            details.testResults[testName] = {
                status: testResult.status,
                details: testResult.details,
                description: this.getTestDescription(testName),
                importance: this.getTestImportance(testName)
            };
            
            // Collect errors from failed tests
            if (testResult.status === 'failed' && testResult.details?.error) {
                details.issues.errors.push({
                    test: testName,
                    error: testResult.details.error,
                    details: testResult.details
                });
            }
        }
        
        return details;
    }
    
    // Generate formatted report for display
    generateFormattedReport(testResults) {
        const summary = this.generateSummary(testResults);
        const details = this.generateDetailedReport(testResults);
        
        let formatted = '';
        
        // Header
        formatted += this.formatReportHeader(summary);
        
        // Summary section
        formatted += this.formatSummarySection(summary);
        
        // Test results section
        formatted += this.formatTestResultsSection(details.testResults);
        
        // Video properties section
        if (this.reportConfig.includeMetadata) {
            formatted += this.formatVideoPropertiesSection(details.videoProperties);
        }
        
        // Issues section
        formatted += this.formatIssuesSection(details.issues);
        
        // Footer
        formatted += this.formatReportFooter(details.testExecution);
        
        return formatted;
    }
    
    // Generate exportable report (JSON format)
    generateExportableReport(testResults, videoBlob) {
        const exportData = {
            reportMetadata: {
                reportId: this.generateReportId(),
                generatedAt: new Date().toISOString(),
                reporterVersion: '1.0.0',
                reportType: 'video-validation'
            },
            testResults: testResults,
            summary: this.generateSummary(testResults),
            configuration: this.reportConfig
        };
        
        // Add blob information if provided
        if (videoBlob) {
            exportData.blobInfo = {
                size: videoBlob.size,
                type: videoBlob.type,
                sizeFormatted: this.formatFileSize(videoBlob.size)
            };
        }
        
        return exportData;
    }
    
    // Format report header
    formatReportHeader(summary) {
        const status = summary.overall === 'PASSED' ? '✅' : '❌';
        
        return `
════════════════════════════════════════════════════════════════
${status} VIDEO VALIDATION REPORT
════════════════════════════════════════════════════════════════
File: ${summary.filename}
Overall Status: ${summary.overall}
Generated: ${new Date().toLocaleString()}
════════════════════════════════════════════════════════════════

`;
    }
    
    // Format summary section
    formatSummarySection(summary) {
        return `
📋 SUMMARY
──────────────────────────────────────────────────────────────────
Test Duration: ${summary.testDuration}
Tests Run: ${summary.testsRun}
Tests Passed: ${summary.testsPassed} ✅
Tests Failed: ${summary.testsFailed} ${summary.testsFailed > 0 ? '❌' : ''}
Warnings: ${summary.warnings} ${summary.warnings > 0 ? '⚠️' : ''}
Recommendations: ${summary.recommendations}

🎬 VIDEO INFORMATION
──────────────────────────────────────────────────────────────────
Duration: ${summary.videoInfo?.duration || 'Unknown'}
Dimensions: ${summary.videoInfo?.dimensions || 'Unknown'}
File Size: ${summary.videoInfo?.fileSize || 'Unknown'}
Aspect Ratio: ${summary.videoInfo?.aspectRatio || 'Unknown'}

`;
    }
    
    // Format test results section
    formatTestResultsSection(testResults) {
        let section = `
🔬 TEST RESULTS
──────────────────────────────────────────────────────────────────
`;
        
        for (const [testName, result] of Object.entries(testResults)) {
            const statusIcon = this.getStatusIcon(result.status);
            const testTitle = this.formatTestName(testName);
            
            section += `${statusIcon} ${testTitle} - ${result.status.toUpperCase()}\n`;
            
            if (result.details && typeof result.details === 'object') {
                section += this.formatTestDetails(result.details, '   ');
            }
            
            section += `   Importance: ${result.importance}\n`;
            section += `   Description: ${result.description}\n\n`;
        }
        
        return section;
    }
    
    // Format video properties section
    formatVideoPropertiesSection(properties) {
        let section = `
📊 VIDEO PROPERTIES
──────────────────────────────────────────────────────────────────
`;
        
        for (const [key, value] of Object.entries(properties)) {
            const formattedKey = this.formatPropertyName(key);
            const formattedValue = this.formatPropertyValue(key, value);
            section += `${formattedKey}: ${formattedValue}\n`;
        }
        
        return section + '\n';
    }
    
    // Format issues section
    formatIssuesSection(issues) {
        let section = '';
        
        // Errors
        if (issues.errors.length > 0) {
            section += `
❌ ERRORS
──────────────────────────────────────────────────────────────────
`;
            issues.errors.forEach((error, index) => {
                section += `${index + 1}. Test: ${this.formatTestName(error.test)}\n`;
                section += `   Error: ${error.error}\n\n`;
            });
        }
        
        // Warnings
        if (issues.warnings.length > 0) {
            section += `
⚠️  WARNINGS
──────────────────────────────────────────────────────────────────
`;
            issues.warnings.forEach((warning, index) => {
                section += `${index + 1}. ${warning}\n`;
            });
            section += '\n';
        }
        
        // Recommendations
        if (issues.recommendations.length > 0) {
            section += `
💡 RECOMMENDATIONS
──────────────────────────────────────────────────────────────────
`;
            issues.recommendations.forEach((rec, index) => {
                section += `${index + 1}. ${rec}\n`;
            });
            section += '\n';
        }
        
        return section;
    }
    
    // Format report footer
    formatReportFooter(testExecution) {
        return `
════════════════════════════════════════════════════════════════
Report generated by Video from Pictures - Video Tester Module
Test execution: ${testExecution.startTime} to ${testExecution.endTime || 'incomplete'}
Duration: ${this.formatDuration(testExecution.duration || 0)}
════════════════════════════════════════════════════════════════
`;
    }
    
    // Helper functions for formatting
    getStatusIcon(status) {
        const icons = {
            'passed': '✅',
            'failed': '❌',
            'warning': '⚠️',
            'pending': '⏳',
            'skipped': '⏭️'
        };
        return icons[status] || '❓';
    }
    
    formatTestName(testName) {
        return testName
            .replace(/([A-Z])/g, ' $1')
            .replace(/^./, str => str.toUpperCase())
            .trim();
    }
    
    formatPropertyName(propName) {
        return propName
            .replace(/([A-Z])/g, ' $1')
            .replace(/^./, str => str.toUpperCase())
            .trim();
    }
    
    formatPropertyValue(key, value) {
        if (typeof value === 'number') {
            if (key.includes('size') || key.includes('Size')) {
                return this.formatFileSize(value);
            }
            if (key.includes('duration') || key.includes('Duration')) {
                return this.formatDuration(value * 1000);
            }
            return value.toString();
        }
        
        if (typeof value === 'object') {
            return JSON.stringify(value, null, 2);
        }
        
        return String(value);
    }
    
    formatTestDetails(details, indent = '') {
        let formatted = '';
        
        for (const [key, value] of Object.entries(details)) {
            if (key === 'error') continue; // Errors are handled separately
            
            const formattedKey = this.formatPropertyName(key);
            let formattedValue;
            
            if (typeof value === 'object') {
                formattedValue = JSON.stringify(value);
            } else {
                formattedValue = String(value);
            }
            
            formatted += `${indent}${formattedKey}: ${formattedValue}\n`;
        }
        
        return formatted;
    }
    
    getTestDescription(testName) {
        const descriptions = {
            'blobValidation': 'Validates the video blob integrity and basic properties',
            'videoCreation': 'Tests video element creation and metadata loading',
            'metadataValidation': 'Compares detected video properties with expected values',
            'playbackValidation': 'Tests actual video playback and progress tracking',
            'frameValidation': 'Analyzes individual video frames for quality and uniqueness'
        };
        
        return descriptions[testName] || 'No description available';
    }
    
    getTestImportance(testName) {
        const importance = {
            'blobValidation': 'Critical',
            'videoCreation': 'Critical',
            'metadataValidation': 'High',
            'playbackValidation': 'High',
            'frameValidation': 'Medium'
        };
        
        return importance[testName] || 'Low';
    }
    
    formatDuration(milliseconds) {
        if (milliseconds < 1000) {
            return `${milliseconds}ms`;
        }
        
        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    generateReportId() {
        return `vtr_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    // Export report in different formats
    exportReport(report, format = 'txt') {
        switch (format.toLowerCase()) {
            case 'txt':
                return this.exportAsText(report);
            case 'json':
                return this.exportAsJSON(report);
            case 'html':
                return this.exportAsHTML(report);
            default:
                throw new Error(`Unsupported export format: ${format}`);
        }
    }
    
    exportAsText(report) {
        return report.formatted;
    }
    
    exportAsJSON(report) {
        return JSON.stringify(report.exportable, null, 2);
    }
    
    exportAsHTML(report) {
        const summary = report.summary;
        const details = report.details;
        
        return `
<!DOCTYPE html>
<html>
<head>
    <title>Video Validation Report - ${summary.filename}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; padding: 20px; background-color: ${summary.overall === 'PASSED' ? '#d4edda' : '#f8d7da'}; border-radius: 8px; margin-bottom: 20px; }
        .status { font-size: 24px; font-weight: bold; color: ${summary.overall === 'PASSED' ? '#155724' : '#721c24'}; }
        .section { margin: 20px 0; }
        .section-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; border-bottom: 2px solid #007bff; padding-bottom: 5px; }
        .test-result { margin: 10px 0; padding: 10px; border-radius: 4px; }
        .test-passed { background-color: #d4edda; border-left: 4px solid #28a745; }
        .test-failed { background-color: #f8d7da; border-left: 4px solid #dc3545; }
        .test-warning { background-color: #fff3cd; border-left: 4px solid #ffc107; }
        .property { margin: 5px 0; }
        .property-name { font-weight: bold; display: inline-block; width: 150px; }
        .warning { color: #856404; }
        .error { color: #721c24; }
        .recommendation { color: #004085; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="status">${summary.overall === 'PASSED' ? '✅' : '❌'} ${summary.overall}</div>
            <h1>Video Validation Report</h1>
            <p><strong>File:</strong> ${summary.filename}</p>
            <p><strong>Generated:</strong> ${new Date().toLocaleString()}</p>
        </div>
        
        <div class="section">
            <div class="section-title">Summary</div>
            <div class="property"><span class="property-name">Test Duration:</span> ${summary.testDuration}</div>
            <div class="property"><span class="property-name">Tests Passed:</span> ${summary.testsPassed}/${summary.testsRun}</div>
            <div class="property"><span class="property-name">Warnings:</span> ${summary.warnings}</div>
            <div class="property"><span class="property-name">Recommendations:</span> ${summary.recommendations}</div>
        </div>
        
        <div class="section">
            <div class="section-title">Video Information</div>
            <div class="property"><span class="property-name">Duration:</span> ${summary.videoInfo?.duration || 'Unknown'}</div>
            <div class="property"><span class="property-name">Dimensions:</span> ${summary.videoInfo?.dimensions || 'Unknown'}</div>
            <div class="property"><span class="property-name">File Size:</span> ${summary.videoInfo?.fileSize || 'Unknown'}</div>
            <div class="property"><span class="property-name">Aspect Ratio:</span> ${summary.videoInfo?.aspectRatio || 'Unknown'}</div>
        </div>
        
        <div class="section">
            <div class="section-title">Test Results</div>
            ${Object.entries(details.testResults).map(([testName, result]) => `
                <div class="test-result test-${result.status}">
                    <strong>${this.formatTestName(testName)}</strong> - ${result.status.toUpperCase()}
                    <br><small>${result.description}</small>
                </div>
            `).join('')}
        </div>
        
        ${details.issues.warnings.length > 0 ? `
        <div class="section">
            <div class="section-title">Warnings</div>
            ${details.issues.warnings.map(warning => `<div class="warning">⚠️ ${warning}</div>`).join('')}
        </div>
        ` : ''}
        
        ${details.issues.recommendations.length > 0 ? `
        <div class="section">
            <div class="section-title">Recommendations</div>
            ${details.issues.recommendations.map(rec => `<div class="recommendation">💡 ${rec}</div>`).join('')}
        </div>
        ` : ''}
    </div>
</body>
</html>
        `;
    }
    
    // Save report to file (using existing FileSaver if available)
    async saveReport(report, filename, format = 'txt') {
        try {
            const content = this.exportReport(report, format);
            const mimeTypes = {
                'txt': 'text/plain',
                'json': 'application/json',
                'html': 'text/html'
            };
            
            const blob = new Blob([content], { type: mimeTypes[format] || 'text/plain' });
            const reportFilename = `${filename}_report_${Date.now()}.${format}`;
            
            // Try to use existing FileSaver if available
            if (typeof window !== 'undefined' && window.FileSaver) {
                const fileSaver = new window.FileSaver();
                return await fileSaver.saveFile(blob, reportFilename);
            } else {
                // Fallback to basic download
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = reportFilename;
                a.click();
                URL.revokeObjectURL(url);
                
                return {
                    success: true,
                    filename: reportFilename,
                    method: 'download',
                    size: blob.size
                };
            }
        } catch (error) {
            console.error('Failed to save report:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }
    
    // Get report configuration
    getConfig() {
        return { ...this.reportConfig };
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.VideoReporter = VideoReporter;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = VideoReporter;
}
