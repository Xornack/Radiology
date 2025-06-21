// Success/Failure Reporter Module - Step 3.3
// Implements comprehensive success/failure reporting system
// Part of Phase 3: Output and Validation

class SuccessFailureReporter {
    constructor() {
        this.reportHistory = [];
        this.currentSession = null;
        this.sessionId = null;
        this.onReportGenerated = null;
        this.onReportExported = null;
        
        this.reportTypes = {
            SESSION: 'session',
            OPERATION: 'operation',
            ERROR: 'error',
            SUCCESS: 'success',
            WARNING: 'warning'
        };
        
        this.operationTypes = {
            FILE_SELECTION: 'file_selection',
            IMAGE_PROCESSING: 'image_processing',
            VIDEO_CONVERSION: 'video_conversion',
            VIDEO_SAVE: 'video_save',
            VIDEO_VALIDATION: 'video_validation',
            SYSTEM_CHECK: 'system_check'
        };
        
        this.initializeSession();
        console.log('SuccessFailureReporter initialized');
    }
    
    // Initialize new session
    initializeSession() {
        this.sessionId = this.generateSessionId();
        this.currentSession = {
            sessionId: this.sessionId,
            startTime: new Date().toISOString(),
            endTime: null,
            operations: [],
            summary: {
                totalOperations: 0,
                successfulOperations: 0,
                failedOperations: 0,
                warningOperations: 0,
                successRate: 0
            },
            systemInfo: this.collectSystemInfo()
        };
    }
    
    // Generate unique session ID
    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    // Collect system information
    collectSystemInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            cookieEnabled: navigator.cookieEnabled,
            onLine: navigator.onLine,
            timestamp: new Date().toISOString(),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            screen: {
                width: screen.width,
                height: screen.height,
                colorDepth: screen.colorDepth
            },
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight
            }
        };
    }
    
    // Report operation start
    reportOperationStart(operationType, operationData = {}) {
        const operation = {
            operationId: this.generateOperationId(),
            type: operationType,
            status: 'in_progress',
            startTime: new Date().toISOString(),
            endTime: null,
            duration: null,
            data: operationData,
            result: null,
            errors: [],
            warnings: [],
            metrics: {}
        };
        
        this.currentSession.operations.push(operation);
        this.currentSession.summary.totalOperations++;
        
        // Trigger callback if set
        if (this.onReportGenerated) {
            this.onReportGenerated({
                type: this.reportTypes.OPERATION,
                operation: operation,
                status: 'started'
            });
        }
        
        return operation.operationId;
    }
    
    // Report operation success
    reportOperationSuccess(operationId, resultData = {}, metrics = {}) {
        const operation = this.findOperation(operationId);
        if (!operation) return;
        
        operation.status = 'success';
        operation.endTime = new Date().toISOString();
        operation.duration = new Date(operation.endTime) - new Date(operation.startTime);
        operation.result = resultData;
        operation.metrics = metrics;
        
        this.currentSession.summary.successfulOperations++;
        this.updateSuccessRate();
        
        // Trigger callback if set
        if (this.onReportGenerated) {
            this.onReportGenerated({
                type: this.reportTypes.SUCCESS,
                operation: operation,
                status: 'completed'
            });
        }
        
        return operation;
    }
    
    // Report operation failure
    reportOperationFailure(operationId, errorData = {}, metrics = {}) {
        const operation = this.findOperation(operationId);
        if (!operation) return;
        
        operation.status = 'failed';
        operation.endTime = new Date().toISOString();
        operation.duration = new Date(operation.endTime) - new Date(operation.startTime);
        operation.errors.push({
            timestamp: new Date().toISOString(),
            ...errorData
        });
        operation.metrics = metrics;
        
        this.currentSession.summary.failedOperations++;
        this.updateSuccessRate();
        
        // Trigger callback if set
        if (this.onReportGenerated) {
            this.onReportGenerated({
                type: this.reportTypes.ERROR,
                operation: operation,
                status: 'failed'
            });
        }
        
        return operation;
    }
    
    // Report operation warning
    reportOperationWarning(operationId, warningData = {}) {
        const operation = this.findOperation(operationId);
        if (!operation) return;
        
        operation.warnings.push({
            timestamp: new Date().toISOString(),
            ...warningData
        });
        
        this.currentSession.summary.warningOperations++;
        
        // Trigger callback if set
        if (this.onReportGenerated) {
            this.onReportGenerated({
                type: this.reportTypes.WARNING,
                operation: operation,
                status: 'warning'
            });
        }
        
        return operation;
    }
    
    // Find operation by ID
    findOperation(operationId) {
        return this.currentSession.operations.find(op => op.operationId === operationId);
    }
    
    // Generate operation ID
    generateOperationId() {
        return 'op_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
    }
    
    // Update success rate
    updateSuccessRate() {
        const total = this.currentSession.summary.totalOperations;
        const successful = this.currentSession.summary.successfulOperations;
        this.currentSession.summary.successRate = total > 0 ? Math.round((successful / total) * 100) : 0;
    }
    
    // End current session
    endSession() {
        if (this.currentSession) {
            this.currentSession.endTime = new Date().toISOString();
            this.reportHistory.push(this.currentSession);
            
            // Trigger callback if set
            if (this.onReportGenerated) {
                this.onReportGenerated({
                    type: this.reportTypes.SESSION,
                    session: this.currentSession,
                    status: 'ended'
                });
            }
        }
    }
    
    // Generate comprehensive session report
    generateSessionReport(format = 'detailed') {
        if (!this.currentSession) {
            return null;
        }
        
        const report = {
            reportId: 'report_' + Date.now(),
            generatedAt: new Date().toISOString(),
            format: format,
            session: this.currentSession,
            analysis: this.analyzeSession(),
            recommendations: this.generateRecommendations()
        };
        
        return report;
    }
    
    // Analyze session performance
    analyzeSession() {
        const session = this.currentSession;
        const operations = session.operations;
        
        const analysis = {
            performance: {
                averageOperationTime: 0,
                slowestOperation: null,
                fastestOperation: null,
                totalSessionTime: null
            },
            errorAnalysis: {
                mostCommonErrors: [],
                errorPatterns: [],
                criticalErrors: []
            },
            successPatterns: {
                quickestSuccesses: [],
                mostReliableOperations: []
            }
        };
        
        // Calculate performance metrics
        const completedOps = operations.filter(op => op.endTime);
        if (completedOps.length > 0) {
            const durations = completedOps.map(op => op.duration).filter(d => d);
            analysis.performance.averageOperationTime = durations.reduce((a, b) => a + b, 0) / durations.length;
            analysis.performance.slowestOperation = completedOps.reduce((prev, current) => 
                (prev.duration > current.duration) ? prev : current);
            analysis.performance.fastestOperation = completedOps.reduce((prev, current) => 
                (prev.duration < current.duration) ? prev : current);
        }
        
        if (session.startTime && session.endTime) {
            analysis.performance.totalSessionTime = new Date(session.endTime) - new Date(session.startTime);
        }
        
        // Analyze errors
        const errorOps = operations.filter(op => op.errors.length > 0);
        const allErrors = errorOps.flatMap(op => op.errors);
        analysis.errorAnalysis.mostCommonErrors = this.categorizeErrors(allErrors);
        analysis.errorAnalysis.criticalErrors = allErrors.filter(err => err.severity === 'critical');
        
        return analysis;
    }
    
    // Categorize errors for analysis
    categorizeErrors(errors) {
        const categories = {};
        errors.forEach(error => {
            const category = error.category || 'unknown';
            if (!categories[category]) {
                categories[category] = [];
            }
            categories[category].push(error);
        });
        
        return Object.entries(categories)
            .map(([category, errs]) => ({
                category,
                count: errs.length,
                examples: errs.slice(0, 3)
            }))
            .sort((a, b) => b.count - a.count);
    }
    
    // Generate recommendations based on session analysis
    generateRecommendations() {
        const session = this.currentSession;
        const recommendations = [];
        
        // Success rate recommendations
        if (session.summary.successRate < 50) {
            recommendations.push({
                type: 'performance',
                priority: 'high',
                message: 'Low success rate detected. Review error patterns and system requirements.',
                action: 'Check browser compatibility and file selection methods.'
            });
        } else if (session.summary.successRate < 80) {
            recommendations.push({
                type: 'performance',
                priority: 'medium',
                message: 'Moderate success rate. Some operations may need attention.',
                action: 'Review failed operations for common patterns.'
            });
        }
        
        // Error-based recommendations
        const errorOps = session.operations.filter(op => op.errors.length > 0);
        if (errorOps.length > 0) {
            recommendations.push({
                type: 'error_handling',
                priority: 'medium',
                message: `${errorOps.length} operations encountered errors.`,
                action: 'Review error details and implement additional validation.'
            });
        }
        
        // Performance recommendations
        const slowOps = session.operations.filter(op => op.duration > 30000); // > 30 seconds
        if (slowOps.length > 0) {
            recommendations.push({
                type: 'performance',
                priority: 'low',
                message: 'Some operations took longer than expected.',
                action: 'Consider optimizing file processing or reducing image count.'
            });
        }
        
        return recommendations;
    }
    
    // Export report in various formats
    exportReport(format = 'json') {
        const report = this.generateSessionReport();
        if (!report) return null;
        
        let exportData;
        let filename;
        let mimeType;
        
        switch (format.toLowerCase()) {
            case 'json':
                exportData = JSON.stringify(report, null, 2);
                filename = `session_report_${this.sessionId}.json`;
                mimeType = 'application/json';
                break;
                
            case 'csv':
                exportData = this.convertToCSV(report);
                filename = `session_report_${this.sessionId}.csv`;
                mimeType = 'text/csv';
                break;
                
            case 'txt':
                exportData = this.convertToText(report);
                filename = `session_report_${this.sessionId}.txt`;
                mimeType = 'text/plain';
                break;
                
            case 'html':
                exportData = this.convertToHTML(report);
                filename = `session_report_${this.sessionId}.html`;
                mimeType = 'text/html';
                break;
                
            default:
                throw new Error(`Unsupported export format: ${format}`);
        }
        
        // Trigger callback if set
        if (this.onReportExported) {
            this.onReportExported({
                format,
                filename,
                data: exportData,
                report
            });
        }
        
        return {
            data: exportData,
            filename,
            mimeType,
            blob: new Blob([exportData], { type: mimeType })
        };
    }
    
    // Convert report to CSV format
    convertToCSV(report) {
        const lines = [];
        lines.push('Operation Type,Status,Start Time,End Time,Duration (ms),Errors,Warnings');
        
        report.session.operations.forEach(op => {
            lines.push([
                op.type,
                op.status,
                op.startTime,
                op.endTime || '',
                op.duration || '',
                op.errors.length,
                op.warnings.length
            ].join(','));
        });
        
        return lines.join('\n');
    }
    
    // Convert report to plain text format
    convertToText(report) {
        const lines = [];
        lines.push('=== Video Processing Session Report ===');
        lines.push(`Session ID: ${report.session.sessionId}`);
        lines.push(`Generated: ${report.generatedAt}`);
        lines.push(`Duration: ${report.session.startTime} to ${report.session.endTime || 'Ongoing'}`);
        lines.push('');
        
        lines.push('=== Summary ===');
        lines.push(`Total Operations: ${report.session.summary.totalOperations}`);
        lines.push(`Successful: ${report.session.summary.successfulOperations}`);
        lines.push(`Failed: ${report.session.summary.failedOperations}`);
        lines.push(`With Warnings: ${report.session.summary.warningOperations}`);
        lines.push(`Success Rate: ${report.session.summary.successRate}%`);
        lines.push('');
        
        lines.push('=== Operations ===');
        report.session.operations.forEach((op, index) => {
            lines.push(`${index + 1}. ${op.type} - ${op.status}`);
            lines.push(`   Started: ${op.startTime}`);
            if (op.endTime) {
                lines.push(`   Completed: ${op.endTime} (${op.duration}ms)`);
            }
            if (op.errors.length > 0) {
                lines.push(`   Errors: ${op.errors.length}`);
            }
            if (op.warnings.length > 0) {
                lines.push(`   Warnings: ${op.warnings.length}`);
            }
            lines.push('');
        });
        
        return lines.join('\n');
    }
    
    // Convert report to HTML format
    convertToHTML(report) {
        return `
<!DOCTYPE html>
<html>
<head>
    <title>Video Processing Session Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .summary { background: #e8f5e8; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .operation { border: 1px solid #ddd; margin: 10px 0; padding: 10px; border-radius: 5px; }
        .success { border-left: 4px solid #28a745; }
        .failed { border-left: 4px solid #dc3545; }
        .in_progress { border-left: 4px solid #ffc107; }
        .recommendations { background: #fff3cd; padding: 15px; border-radius: 5px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Video Processing Session Report</h1>
        <p><strong>Session ID:</strong> ${report.session.sessionId}</p>
        <p><strong>Generated:</strong> ${report.generatedAt}</p>
        <p><strong>Duration:</strong> ${report.session.startTime} to ${report.session.endTime || 'Ongoing'}</p>
    </div>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Operations:</strong> ${report.session.summary.totalOperations}</p>
        <p><strong>Successful:</strong> ${report.session.summary.successfulOperations}</p>
        <p><strong>Failed:</strong> ${report.session.summary.failedOperations}</p>
        <p><strong>With Warnings:</strong> ${report.session.summary.warningOperations}</p>
        <p><strong>Success Rate:</strong> ${report.session.summary.successRate}%</p>
    </div>
    
    <h2>Operations</h2>
    ${report.session.operations.map((op, index) => `
        <div class="operation ${op.status}">
            <h3>${index + 1}. ${op.type} - ${op.status.toUpperCase()}</h3>
            <p><strong>Started:</strong> ${op.startTime}</p>
            ${op.endTime ? `<p><strong>Completed:</strong> ${op.endTime} (${op.duration}ms)</p>` : ''}
            ${op.errors.length > 0 ? `<p><strong>Errors:</strong> ${op.errors.length}</p>` : ''}
            ${op.warnings.length > 0 ? `<p><strong>Warnings:</strong> ${op.warnings.length}</p>` : ''}
        </div>
    `).join('')}
    
    ${report.recommendations.length > 0 ? `
        <div class="recommendations">
            <h2>Recommendations</h2>
            ${report.recommendations.map(rec => `
                <p><strong>${rec.priority.toUpperCase()}:</strong> ${rec.message}</p>
                <p><em>Action:</em> ${rec.action}</p>
            `).join('')}
        </div>
    ` : ''}
</body>
</html>`;
    }
    
    // Get session history
    getReportHistory() {
        return this.reportHistory;
    }
    
    // Clear session history
    clearHistory() {
        this.reportHistory = [];
    }
    
    // Get current session status
    getCurrentSessionStatus() {
        return {
            sessionId: this.sessionId,
            isActive: this.currentSession !== null,
            operationCount: this.currentSession ? this.currentSession.operations.length : 0,
            successRate: this.currentSession ? this.currentSession.summary.successRate : 0
        };
    }
}

// Auto-initialize if in browser environment
if (typeof window !== 'undefined') {
    window.SuccessFailureReporter = SuccessFailureReporter;
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SuccessFailureReporter;
}
