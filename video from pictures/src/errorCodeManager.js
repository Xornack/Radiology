/**
 * Error Code Manager for Video from Pictures Application
 * 
 * Manages error reporting, tracking, and user notification using the ErrorCodeSystem.
 * Integrates with existing ErrorHandler and SuccessFailureReporter systems.
 */

class ErrorCodeManager {
    constructor(options = {}) {
        this.errorCodeSystem = new ErrorCodeSystem();
        this.errorHistory = [];
        this.maxHistorySize = options.maxHistorySize || 100;
        this.enableLogging = options.enableLogging !== false;
        this.enableUserNotification = options.enableUserNotification !== false;
        this.enableReporting = options.enableReporting !== false;
        
        // Integration with existing systems
        this.errorHandler = options.errorHandler || null;
        this.successFailureReporter = options.successFailureReporter || null;
        this.statusCallback = options.statusCallback || null;
        
        // Event callbacks
        this.onErrorReported = options.onErrorReported || null;
        this.onErrorResolved = options.onErrorResolved || null;
        
        // Error aggregation for pattern analysis
        this.errorCounts = {};
        this.sessionErrors = [];
        this.startTime = Date.now();
        
        this.initializeErrorManagement();
    }

    /**
     * Initialize error management system
     */
    initializeErrorManagement() {
        // Set up global error handler integration
        if (typeof window !== 'undefined') {
            this.setupGlobalErrorHandling();
        }
        
        // Initialize error tracking
        this.clearErrorHistory();
        
        if (this.enableLogging) {
            console.log('[ErrorCodeManager] Initialized with', this.errorCodeSystem.getErrorStatistics());
        }
    }

    /**
     * Set up global error handling integration
     */
    setupGlobalErrorHandling() {
        const originalErrorHandler = window.onerror;
        const originalUnhandledRejectionHandler = window.onunhandledrejection;
        
        window.onerror = (message, source, lineno, colno, error) => {
            this.reportUnhandledError(error || new Error(message), {
                source, lineno, colno, type: 'javascript'
            });
            
            if (originalErrorHandler) {
                return originalErrorHandler.call(window, message, source, lineno, colno, error);
            }
        };
        
        window.onunhandledrejection = (event) => {
            this.reportUnhandledError(event.reason, {
                type: 'promise_rejection',
                promise: event.promise
            });
            
            if (originalUnhandledRejectionHandler) {
                return originalUnhandledRejectionHandler.call(window, event);
            }
        };
    }

    /**
     * Report an error using error code
     * @param {string} errorCode - The standard error code
     * @param {Error} originalError - The original error object (optional)
     * @param {Object} context - Additional context information
     * @param {Object} options - Reporting options
     * @returns {Object} Error report object
     */
    reportError(errorCode, originalError = null, context = {}, options = {}) {
        // Validate error code
        if (!this.errorCodeSystem.isValidErrorCode(errorCode)) {
            console.warn(`[ErrorCodeManager] Invalid error code: ${errorCode}`);
            return this.reportUnhandledError(
                originalError || new Error(`Invalid error code: ${errorCode}`),
                context
            );
        }

        // Create standardized error
        const standardizedError = this.errorCodeSystem.createError(errorCode, originalError, context);
        
        // Add to history and session tracking
        this.addToHistory(standardizedError);
        this.sessionErrors.push(standardizedError);
        this.updateErrorCounts(errorCode);
        
        // Integrate with existing systems
        this.integrateWithExistingSystems(standardizedError, options);
        
        // User notification
        if (this.enableUserNotification && !options.silent) {
            this.notifyUser(standardizedError);
        }
        
        // Logging
        if (this.enableLogging) {
            this.logError(standardizedError);
        }
        
        // Trigger callback
        if (this.onErrorReported) {
            this.onErrorReported(standardizedError);
        }
        
        return standardizedError;
    }

    /**
     * Report an unhandled error (fallback for unknown error codes)
     * @param {Error} error - The error object
     * @param {Object} context - Additional context information
     * @returns {Object} Error report object
     */
    reportUnhandledError(error, context = {}) {
        // Try to categorize the error based on message/type
        const errorCode = this.categorizeUnhandledError(error);
        
        if (errorCode) {
            return this.reportError(errorCode, error, context);
        }
        
        // Create generic error report
        const genericError = {
            success: true,
            code: 'UNKNOWN',
            title: 'Unexpected Error',
            message: error.message || 'An unexpected error occurred',
            userAction: 'Please try again or contact support if the problem persists',
            technicalDetails: error.stack || error.toString(),
            category: {
                name: 'Unknown',
                icon: '❓'
            },
            severity: {
                name: 'High',
                color: '#dc3545',
                icon: '🚨'
            },
            timestamp: new Date().toISOString(),
            context: context,
            originalError: {
                name: error.name,
                message: error.message,
                stack: error.stack
            },
            id: this.errorCodeSystem.generateErrorId()
        };
        
        this.addToHistory(genericError);
        this.sessionErrors.push(genericError);
        
        if (this.enableLogging) {
            console.error('[ErrorCodeManager] Unhandled error:', genericError);
        }
        
        return genericError;
    }

    /**
     * Try to categorize an unhandled error based on its properties
     * @param {Error} error - The error to categorize
     * @returns {string|null} Error code or null if cannot categorize
     */
    categorizeUnhandledError(error) {
        const message = (error.message || '').toLowerCase();
        const name = (error.name || '').toLowerCase();
        
        // File system errors
        if (message.includes('permission') || message.includes('access denied')) {
            return 'FSA_001';
        }
        if (message.includes('not supported') || message.includes('undefined')) {
            return 'FSA_002';
        }
        
        // Memory errors
        if (message.includes('memory') || message.includes('out of memory')) {
            return 'SYS_002';
        }
        
        // Network errors
        if (message.includes('network') || message.includes('fetch')) {
            return 'NET_001';
        }
        
        // Video encoding errors
        if (message.includes('encoding') || message.includes('codec')) {
            return 'VID_002';
        }
        
        return null; // Cannot categorize
    }

    /**
     * Integrate with existing error handling systems
     * @param {Object} standardizedError - The standardized error object
     * @param {Object} options - Integration options
     */
    integrateWithExistingSystems(standardizedError, options = {}) {
        // Integrate with ErrorHandler
        if (this.errorHandler && !options.skipErrorHandler) {
            try {
                // Convert to format expected by ErrorHandler
                const errorForHandler = new Error(standardizedError.message);
                errorForHandler.name = standardizedError.code;
                this.errorHandler.handleError(errorForHandler, standardizedError.context);
            } catch (integrationError) {
                console.warn('[ErrorCodeManager] ErrorHandler integration failed:', integrationError);
            }
        }
        
        // Integrate with SuccessFailureReporter
        if (this.successFailureReporter && this.enableReporting && !options.skipReporting) {
            try {
                // Report as operation failure if operation ID provided
                if (standardizedError.context.operationId) {
                    this.successFailureReporter.reportOperationFailure(
                        standardizedError.context.operationId,
                        {
                            category: standardizedError.category.name.toLowerCase(),
                            severity: standardizedError.severity.name.toLowerCase(),
                            message: standardizedError.message,
                            code: standardizedError.code,
                            technicalDetails: standardizedError.technicalDetails
                        }
                    );
                }
            } catch (integrationError) {
                console.warn('[ErrorCodeManager] SuccessFailureReporter integration failed:', integrationError);
            }
        }
        
        // Integrate with status callback
        if (this.statusCallback && !options.skipStatusCallback) {
            try {
                this.statusCallback('error', standardizedError.message, {
                    errorCode: standardizedError.code,
                    severity: standardizedError.severity.name
                });
            } catch (integrationError) {
                console.warn('[ErrorCodeManager] Status callback integration failed:', integrationError);
            }
        }
    }

    /**
     * Notify user about the error
     * @param {Object} standardizedError - The standardized error object
     */
    notifyUser(standardizedError) {
        // Create user-friendly notification
        const notification = {
            type: 'error',
            title: standardizedError.title,
            message: standardizedError.message,
            action: standardizedError.userAction,
            severity: standardizedError.severity.name,
            icon: standardizedError.severity.icon,
            timestamp: standardizedError.timestamp
        };
        
        // Try to show notification using existing UI systems
        this.showUserNotification(notification);
    }

    /**
     * Show notification to user using available UI methods
     * @param {Object} notification - The notification object
     */
    showUserNotification(notification) {
        // Try showStatus function (from existing codebase)
        if (typeof showStatus === 'function') {
            showStatus('error', `${notification.icon} ${notification.title}: ${notification.message}`);
            return;
        }
        
        // Try browser notification API
        if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            new Notification(notification.title, {
                body: notification.message,
                icon: '🚨'
            });
            return;
        }
        
        // Fallback to console
        console.error(`[Error] ${notification.title}: ${notification.message}`);
        if (notification.action) {
            console.info(`[Action] ${notification.action}`);
        }
    }

    /**
     * Add error to history with rotation
     * @param {Object} error - The error object to add
     */
    addToHistory(error) {
        this.errorHistory.push(error);
        
        // Rotate history if too large
        if (this.errorHistory.length > this.maxHistorySize) {
            this.errorHistory = this.errorHistory.slice(-this.maxHistorySize);
        }
    }

    /**
     * Update error count statistics
     * @param {string} errorCode - The error code to count
     */
    updateErrorCounts(errorCode) {
        this.errorCounts[errorCode] = (this.errorCounts[errorCode] || 0) + 1;
    }

    /**
     * Log error information
     * @param {Object} error - The error to log
     */
    logError(error) {
        const logLevel = error.severity.name === 'High' ? 'error' : 
                        error.severity.name === 'Medium' ? 'warn' : 'info';
        
        console[logLevel](`[${error.code}] ${error.title}:`, {
            message: error.message,
            category: error.category.name,
            severity: error.severity.name,
            context: error.context,
            technicalDetails: error.technicalDetails
        });
    }

    /**
     * Mark an error as resolved
     * @param {string} errorId - The error ID to resolve
     * @param {string} resolution - Description of how it was resolved
     */
    resolveError(errorId, resolution = '') {
        const error = this.errorHistory.find(e => e.id === errorId);
        if (error) {
            error.resolved = true;
            error.resolution = resolution;
            error.resolvedAt = new Date().toISOString();
            
            if (this.onErrorResolved) {
                this.onErrorResolved(error);
            }
            
            if (this.enableLogging) {
                console.info(`[ErrorCodeManager] Resolved error ${errorId}:`, resolution);
            }
        }
    }

    /**
     * Get error history
     * @param {Object} filters - Optional filters (category, severity, resolved)
     * @returns {Array} Filtered error history
     */
    getErrorHistory(filters = {}) {
        let history = [...this.errorHistory];
        
        if (filters.category) {
            history = history.filter(e => e.category && e.category.name === filters.category);
        }
        
        if (filters.severity) {
            history = history.filter(e => e.severity && e.severity.name === filters.severity);
        }
        
        if (filters.resolved !== undefined) {
            history = history.filter(e => !!e.resolved === filters.resolved);
        }
        
        return history;
    }

    /**
     * Get session error statistics
     * @returns {Object} Session statistics
     */
    getSessionStatistics() {
        const totalErrors = this.sessionErrors.length;
        const errorsByCategory = {};
        const errorsBySeverity = {};
        const unresolvedErrors = this.sessionErrors.filter(e => !e.resolved);
        
        this.sessionErrors.forEach(error => {
            const category = error.category?.name || 'Unknown';
            const severity = error.severity?.name || 'Unknown';
            
            errorsByCategory[category] = (errorsByCategory[category] || 0) + 1;
            errorsBySeverity[severity] = (errorsBySeverity[severity] || 0) + 1;
        });
        
        return {
            totalErrors,
            unresolvedErrors: unresolvedErrors.length,
            sessionDuration: Date.now() - this.startTime,
            errorsByCategory,
            errorsBySeverity,
            mostCommonError: this.getMostCommonError(),
            errorRate: totalErrors / ((Date.now() - this.startTime) / 60000) // errors per minute
        };
    }

    /**
     * Get the most common error in this session
     * @returns {Object|null} Most common error info
     */
    getMostCommonError() {
        if (Object.keys(this.errorCounts).length === 0) {
            return null;
        }
        
        const mostCommon = Object.entries(this.errorCounts)
            .sort(([,a], [,b]) => b - a)[0];
            
        return {
            code: mostCommon[0],
            count: mostCommon[1],
            info: this.errorCodeSystem.getError(mostCommon[0])
        };
    }

    /**
     * Generate error report
     * @param {string} format - Report format ('json', 'csv', 'html')
     * @returns {string} Formatted report
     */
    generateErrorReport(format = 'json') {
        const statistics = this.getSessionStatistics();
        const history = this.getErrorHistory();
        
        const reportData = {
            generated: new Date().toISOString(),
            session: {
                startTime: new Date(this.startTime).toISOString(),
                duration: statistics.sessionDuration,
                totalErrors: statistics.totalErrors
            },
            statistics,
            errors: history.map(error => ({
                id: error.id,
                code: error.code,
                title: error.title,
                message: error.message,
                category: error.category?.name,
                severity: error.severity?.name,
                timestamp: error.timestamp,
                resolved: !!error.resolved,
                resolution: error.resolution || null
            }))
        };
        
        switch (format.toLowerCase()) {
            case 'csv':
                return this.generateCSVReport(reportData);
            case 'html':
                return this.generateHTMLReport(reportData);
            case 'json':
            default:
                return JSON.stringify(reportData, null, 2);
        }
    }

    /**
     * Generate CSV format report
     * @param {Object} reportData - The report data
     * @returns {string} CSV formatted report
     */
    generateCSVReport(reportData) {
        const headers = ['ID', 'Code', 'Title', 'Category', 'Severity', 'Timestamp', 'Resolved', 'Message'];
        const csvRows = [headers.join(',')];
        
        reportData.errors.forEach(error => {
            const row = [
                error.id,
                error.code,
                `"${error.title}"`,
                error.category || '',
                error.severity || '',
                error.timestamp,
                error.resolved ? 'Yes' : 'No',
                `"${error.message}"`
            ];
            csvRows.push(row.join(','));
        });
        
        return csvRows.join('\n');
    }

    /**
     * Generate HTML format report
     * @param {Object} reportData - The report data
     * @returns {string} HTML formatted report
     */
    generateHTMLReport(reportData) {
        return `
<!DOCTYPE html>
<html>
<head>
    <title>Error Report - ${reportData.generated}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: #fff; border: 1px solid #dee2e6; border-radius: 5px; padding: 15px; }
        .error-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .error-table th, .error-table td { border: 1px solid #dee2e6; padding: 8px; text-align: left; }
        .error-table th { background: #f8f9fa; }
        .severity-high { color: #dc3545; font-weight: bold; }
        .severity-medium { color: #fd7e14; font-weight: bold; }
        .severity-low { color: #28a745; }
        .resolved { color: #28a745; }
        .unresolved { color: #dc3545; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Error Report</h1>
        <p>Generated: ${reportData.generated}</p>
        <p>Session Duration: ${Math.round(reportData.session.duration / 60000)} minutes</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <h3>Total Errors</h3>
            <p>${reportData.statistics.totalErrors}</p>
        </div>
        <div class="stat-card">
            <h3>Unresolved</h3>
            <p>${reportData.statistics.unresolvedErrors}</p>
        </div>
        <div class="stat-card">
            <h3>Error Rate</h3>
            <p>${reportData.statistics.errorRate.toFixed(2)} per minute</p>
        </div>
    </div>
    
    <table class="error-table">
        <thead>
            <tr>
                <th>Code</th>
                <th>Title</th>
                <th>Category</th>
                <th>Severity</th>
                <th>Time</th>
                <th>Status</th>
                <th>Message</th>
            </tr>
        </thead>
        <tbody>
            ${reportData.errors.map(error => `
                <tr>
                    <td>${error.code}</td>
                    <td>${error.title}</td>
                    <td>${error.category || 'Unknown'}</td>
                    <td class="severity-${error.severity?.toLowerCase() || 'unknown'}">${error.severity || 'Unknown'}</td>
                    <td>${new Date(error.timestamp).toLocaleString()}</td>
                    <td class="${error.resolved ? 'resolved' : 'unresolved'}">${error.resolved ? 'Resolved' : 'Open'}</td>
                    <td>${error.message}</td>
                </tr>
            `).join('')}
        </tbody>
    </table>
</body>
</html>`;
    }

    /**
     * Clear error history
     */
    clearErrorHistory() {
        this.errorHistory = [];
        this.sessionErrors = [];
        this.errorCounts = {};
        this.startTime = Date.now();
    }

    /**
     * Export error data
     * @param {string} format - Export format ('json', 'csv', 'html')
     * @returns {Object} Export result with data and metadata
     */
    exportErrorData(format = 'json') {
        const report = this.generateErrorReport(format);
        const filename = `error_report_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.${format}`;
        
        return {
            data: report,
            filename,
            mimeType: this.getMimeType(format),
            size: new Blob([report]).size
        };
    }

    /**
     * Get MIME type for format
     * @param {string} format - The format
     * @returns {string} MIME type
     */
    getMimeType(format) {
        const mimeTypes = {
            'json': 'application/json',
            'csv': 'text/csv',
            'html': 'text/html'
        };
        return mimeTypes[format] || 'text/plain';
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorCodeManager;
} else if (typeof window !== 'undefined') {
    window.ErrorCodeManager = ErrorCodeManager;
}
