// Enhanced Progress Tracker Module - Step 2.3
// Implements comprehensive progress tracking with ETA, step-by-step status, and statistics
// Part of Phase 2: Video Generation Engine

class ProgressTracker {
    constructor() {
        this.startTime = null;
        this.currentStep = null;
        this.totalSteps = 0;
        this.completedSteps = 0;
        this.stepTimestamps = [];
        this.estimatedStepDurations = {};
        this.currentStepStartTime = null;
        this.totalItems = 0;
        this.processedItems = 0;
        this.currentItem = '';
        this.stepHistory = [];
        this.performanceMetrics = {};
        
        // Callbacks for UI updates
        this.onProgressUpdate = null;
        this.onStepUpdate = null;
        this.onETAUpdate = null;
        this.onStatisticsUpdate = null;
        
        console.log('Enhanced ProgressTracker initialized');
    }

    // Initialize progress tracking for a new operation
    startTracking(totalSteps, totalItems = 0, stepDefinitions = []) {
        this.startTime = Date.now();
        this.totalSteps = totalSteps;
        this.totalItems = totalItems;
        this.completedSteps = 0;
        this.processedItems = 0;
        this.stepTimestamps = [];
        this.stepHistory = [];
        this.currentStep = null;
        this.currentStepStartTime = null;
        
        // Initialize step definitions and estimated durations
        this.initializeStepDefinitions(stepDefinitions);
        
        console.log(`Progress tracking started: ${totalSteps} steps, ${totalItems} items`);
        this.updateCallbacks();
    }

    // Initialize step definitions with estimated durations
    initializeStepDefinitions(stepDefinitions) {
        // Default step definitions for video conversion
        const defaultSteps = [
            { id: 'validation', name: 'Image Validation', estimatedDuration: 2000, weight: 0.1 },
            { id: 'processing', name: 'Image Processing', estimatedDuration: 3000, weight: 0.15 },
            { id: 'encoder-init', name: 'Video Encoder Initialization', estimatedDuration: 5000, weight: 0.2 },
            { id: 'encoding', name: 'Video Encoding', estimatedDuration: 15000, weight: 0.5 },
            { id: 'finalization', name: 'Output Finalization', estimatedDuration: 1000, weight: 0.05 }
        ];
        
        const steps = stepDefinitions.length > 0 ? stepDefinitions : defaultSteps;
        
        this.estimatedStepDurations = {};
        steps.forEach(step => {
            this.estimatedStepDurations[step.id] = {
                duration: step.estimatedDuration,
                weight: step.weight,
                name: step.name
            };
        });
    }

    // Start a new step
    startStep(stepId, stepName = null, itemCount = 0) {
        // Complete previous step if exists
        if (this.currentStep) {
            this.completeStep();
        }

        this.currentStep = stepId;
        this.currentStepStartTime = Date.now();
        this.currentStepItemCount = itemCount;
        this.currentStepProcessedItems = 0;
        
        const displayName = stepName || (this.estimatedStepDurations[stepId]?.name) || stepId;
        
        console.log(`Step started: ${displayName} (${stepId})`);
        
        // Add to step history
        this.stepHistory.push({
            id: stepId,
            name: displayName,
            startTime: this.currentStepStartTime,
            itemCount: itemCount,
            status: 'in-progress'
        });
        
        this.updateCallbacks();
    }

    // Update progress within current step
    updateStepProgress(processedItems = null, currentItem = '', message = '') {
        if (!this.currentStep) {
            console.warn('No active step to update');
            return;
        }

        if (processedItems !== null) {
            this.currentStepProcessedItems = processedItems;
            this.processedItems = Math.min(this.processedItems + 1, this.totalItems);
        }
        
        if (currentItem) {
            this.currentItem = currentItem;
        }

        const now = Date.now();
        const stepElapsed = now - this.currentStepStartTime;
        
        // Calculate step progress percentage
        let stepProgress = 0;
        if (this.currentStepItemCount > 0) {
            stepProgress = (this.currentStepProcessedItems / this.currentStepItemCount) * 100;
        }
        
        // Update performance metrics for current step
        this.updateStepPerformanceMetrics(stepElapsed, stepProgress);
        
        console.log(`Step progress: ${this.currentStep} - ${stepProgress.toFixed(1)}% (${currentItem})`);
        this.updateCallbacks(message, stepProgress);
    }

    // Complete current step
    completeStep() {
        if (!this.currentStep) {
            return;
        }

        const completionTime = Date.now();
        const stepDuration = completionTime - this.currentStepStartTime;
        
        // Update step history
        const stepIndex = this.stepHistory.findIndex(step => 
            step.id === this.currentStep && step.status === 'in-progress'
        );
        
        if (stepIndex >= 0) {
            this.stepHistory[stepIndex].endTime = completionTime;
            this.stepHistory[stepIndex].duration = stepDuration;
            this.stepHistory[stepIndex].status = 'completed';
        }
        
        // Store actual duration for future ETA calculations
        this.stepTimestamps.push({
            stepId: this.currentStep,
            duration: stepDuration,
            timestamp: completionTime
        });
        
        this.completedSteps++;
        
        console.log(`Step completed: ${this.currentStep} in ${stepDuration}ms`);
        
        this.currentStep = null;
        this.currentStepStartTime = null;
        this.updateCallbacks();
    }

    // Calculate estimated time remaining
    calculateETA() {
        if (!this.startTime || this.completedSteps === 0) {
            return {
                total: null,
                formatted: 'Calculating...',
                remaining: null,
                confidence: 'low'
            };
        }

        const now = Date.now();
        const elapsed = now - this.startTime;
        
        // Method 1: Linear progression based on completed steps
        const linearETA = this.calculateLinearETA(elapsed);
        
        // Method 2: Weighted step-based ETA
        const weightedETA = this.calculateWeightedETA(elapsed);
        
        // Method 3: Historical performance ETA
        const historicalETA = this.calculateHistoricalETA();
        
        // Combine methods for better accuracy
        const combinedETA = this.combineETAMethods(linearETA, weightedETA, historicalETA);
        
        return combinedETA;
    }

    // Linear ETA calculation based on completed steps
    calculateLinearETA(elapsed) {
        const progress = this.completedSteps / this.totalSteps;
        const estimatedTotal = elapsed / progress;
        const remaining = estimatedTotal - elapsed;
        
        return {
            method: 'linear',
            total: estimatedTotal,
            remaining: Math.max(0, remaining),
            confidence: progress > 0.2 ? 'medium' : 'low'
        };
    }

    // Weighted ETA calculation based on step importance
    calculateWeightedETA(elapsed) {
        let completedWeight = 0;
        let totalWeight = 0;
        
        // Calculate weights
        Object.keys(this.estimatedStepDurations).forEach(stepId => {
            const stepInfo = this.estimatedStepDurations[stepId];
            totalWeight += stepInfo.weight;
            
            const completedStep = this.stepHistory.find(step => 
                step.id === stepId && step.status === 'completed'
            );
            
            if (completedStep) {
                completedWeight += stepInfo.weight;
            } else if (this.currentStep === stepId) {
                // Add partial weight for current step
                const stepProgress = this.getCurrentStepProgress();
                completedWeight += stepInfo.weight * (stepProgress / 100);
            }
        });
        
        if (completedWeight === 0) {
            return { method: 'weighted', total: null, remaining: null, confidence: 'low' };
        }
        
        const progress = completedWeight / totalWeight;
        const estimatedTotal = elapsed / progress;
        const remaining = estimatedTotal - elapsed;
        
        return {
            method: 'weighted',
            total: estimatedTotal,
            remaining: Math.max(0, remaining),
            confidence: progress > 0.3 ? 'high' : 'medium'
        };
    }

    // Historical performance ETA calculation
    calculateHistoricalETA() {
        if (this.stepTimestamps.length < 2) {
            return { method: 'historical', total: null, remaining: null, confidence: 'low' };
        }
        
        let estimatedRemaining = 0;
        const remainingSteps = this.totalSteps - this.completedSteps;
        
        // Use average duration of completed steps
        const averageDuration = this.stepTimestamps.reduce((sum, step) => sum + step.duration, 0) / this.stepTimestamps.length;
        estimatedRemaining = remainingSteps * averageDuration;
        
        // Add current step progress if active
        if (this.currentStep && this.currentStepStartTime) {
            const currentStepElapsed = Date.now() - this.currentStepStartTime;
            const estimatedCurrentStepDuration = this.estimatedStepDurations[this.currentStep]?.duration || averageDuration;
            estimatedRemaining += Math.max(0, estimatedCurrentStepDuration - currentStepElapsed);
        }
        
        return {
            method: 'historical',
            total: null,
            remaining: estimatedRemaining,
            confidence: this.stepTimestamps.length >= 3 ? 'high' : 'medium'
        };
    }

    // Combine different ETA methods for better accuracy
    combineETAMethods(linear, weighted, historical) {
        const methods = [linear, weighted, historical].filter(method => method.remaining !== null);
        
        if (methods.length === 0) {
            return {
                total: null,
                remaining: null,
                formatted: 'Calculating...',
                confidence: 'low',
                methods: []
            };
        }
        
        // Weight methods by confidence
        const confidenceWeights = { low: 1, medium: 2, high: 3 };
        let totalWeight = 0;
        let weightedRemaining = 0;
        
        methods.forEach(method => {
            const weight = confidenceWeights[method.confidence];
            totalWeight += weight;
            weightedRemaining += method.remaining * weight;
        });
        
        const finalRemaining = weightedRemaining / totalWeight;
        const overallConfidence = this.determineOverallConfidence(methods);
        
        return {
            total: linear.total,
            remaining: finalRemaining,
            formatted: this.formatDuration(finalRemaining / 1000),
            confidence: overallConfidence,
            methods: methods.map(m => m.method)
        };
    }

    // Determine overall confidence based on individual method confidences
    determineOverallConfidence(methods) {
        const confidenceLevels = methods.map(m => m.confidence);
        const highCount = confidenceLevels.filter(c => c === 'high').length;
        const mediumCount = confidenceLevels.filter(c => c === 'medium').length;
        
        if (highCount >= 2) return 'high';
        if (highCount >= 1 || mediumCount >= 2) return 'medium';
        return 'low';
    }

    // Get current step progress percentage
    getCurrentStepProgress() {
        if (!this.currentStep || this.currentStepItemCount === 0) {
            return 0;
        }
        return (this.currentStepProcessedItems / this.currentStepItemCount) * 100;
    }

    // Calculate overall progress percentage
    calculateOverallProgress() {
        let progress = 0;
        
        // Add completed steps weight
        Object.keys(this.estimatedStepDurations).forEach(stepId => {
            const stepInfo = this.estimatedStepDurations[stepId];
            const completedStep = this.stepHistory.find(step => 
                step.id === stepId && step.status === 'completed'
            );
            
            if (completedStep) {
                progress += stepInfo.weight * 100;
            } else if (this.currentStep === stepId) {
                const stepProgress = this.getCurrentStepProgress();
                progress += stepInfo.weight * stepProgress;
            }
        });
        
        return Math.min(100, Math.max(0, progress));
    }

    // Update performance metrics for current step
    updateStepPerformanceMetrics(stepElapsed, stepProgress) {
        if (!this.currentStep) return;
        
        const stepId = this.currentStep;
        if (!this.performanceMetrics[stepId]) {
            this.performanceMetrics[stepId] = {
                itemsPerSecond: 0,
                averageItemTime: 0,
                estimatedCompletion: null
            };
        }
        
        const metrics = this.performanceMetrics[stepId];
        
        // Calculate items per second
        if (this.currentStepProcessedItems > 0 && stepElapsed > 0) {
            metrics.itemsPerSecond = (this.currentStepProcessedItems / stepElapsed) * 1000;
            metrics.averageItemTime = stepElapsed / this.currentStepProcessedItems;
        }
        
        // Estimate step completion time
        if (this.currentStepItemCount > 0 && metrics.itemsPerSecond > 0) {
            const remainingItems = this.currentStepItemCount - this.currentStepProcessedItems;
            const remainingTime = remainingItems / metrics.itemsPerSecond * 1000;
            metrics.estimatedCompletion = Date.now() + remainingTime;
        }
    }

    // Get comprehensive statistics
    getStatistics() {
        const now = Date.now();
        const totalElapsed = this.startTime ? now - this.startTime : 0;
        const eta = this.calculateETA();
        const overallProgress = this.calculateOverallProgress();
        
        return {
            timing: {
                startTime: this.startTime,
                totalElapsed: totalElapsed,
                totalElapsedFormatted: this.formatDuration(totalElapsed / 1000),
                eta: eta,
                estimatedTotal: eta.total ? this.formatDuration(eta.total / 1000) : null
            },
            progress: {
                overall: overallProgress,
                steps: {
                    completed: this.completedSteps,
                    total: this.totalSteps,
                    current: this.currentStep
                },
                items: {
                    processed: this.processedItems,
                    total: this.totalItems,
                    current: this.currentItem
                }
            },
            performance: {
                averageStepDuration: this.calculateAverageStepDuration(),
                currentStepMetrics: this.currentStep ? this.performanceMetrics[this.currentStep] : null,
                overallItemsPerSecond: this.calculateOverallItemsPerSecond(totalElapsed)
            },
            steps: this.stepHistory,
            confidence: eta.confidence
        };
    }

    // Calculate average step duration
    calculateAverageStepDuration() {
        if (this.stepTimestamps.length === 0) return 0;
        
        const totalDuration = this.stepTimestamps.reduce((sum, step) => sum + step.duration, 0);
        return totalDuration / this.stepTimestamps.length;
    }

    // Calculate overall items per second
    calculateOverallItemsPerSecond(totalElapsed) {
        if (this.processedItems === 0 || totalElapsed === 0) return 0;
        return (this.processedItems / totalElapsed) * 1000;
    }

    // Format duration in human-readable format
    formatDuration(seconds) {
        if (seconds < 60) {
            return `${seconds.toFixed(1)}s`;
        } else if (seconds < 3600) {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = seconds % 60;
            return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return `${hours}h ${minutes}m`;
        }
    }

    // Set callback functions
    setCallbacks(onProgressUpdate, onStepUpdate, onETAUpdate, onStatisticsUpdate) {
        this.onProgressUpdate = onProgressUpdate;
        this.onStepUpdate = onStepUpdate;
        this.onETAUpdate = onETAUpdate;
        this.onStatisticsUpdate = onStatisticsUpdate;
    }

    // Update all callbacks with current state
    updateCallbacks(message = '', stepProgress = null) {
        const statistics = this.getStatistics();
        
        if (this.onProgressUpdate) {
            this.onProgressUpdate({
                overall: statistics.progress.overall,
                step: stepProgress,
                message: message || this.generateProgressMessage(),
                currentItem: this.currentItem
            });
        }
        
        if (this.onStepUpdate) {
            this.onStepUpdate({
                currentStep: this.currentStep,
                stepName: this.currentStep ? this.estimatedStepDurations[this.currentStep]?.name || this.currentStep : null,
                completedSteps: this.completedSteps,
                totalSteps: this.totalSteps,
                stepHistory: this.stepHistory
            });
        }
        
        if (this.onETAUpdate) {
            this.onETAUpdate(statistics.timing.eta);
        }
        
        if (this.onStatisticsUpdate) {
            this.onStatisticsUpdate(statistics);
        }
    }

    // Generate progress message based on current state
    generateProgressMessage() {
        if (!this.currentStep) {
            return 'Initializing...';
        }
        
        const stepName = this.estimatedStepDurations[this.currentStep]?.name || this.currentStep;
        
        if (this.currentItem) {
            return `${stepName}: ${this.currentItem}`;
        } else if (this.currentStepItemCount > 0) {
            return `${stepName}: ${this.currentStepProcessedItems}/${this.currentStepItemCount}`;
        } else {
            return stepName;
        }
    }

    // Complete tracking
    completeTracking() {
        if (this.currentStep) {
            this.completeStep();
        }
        
        const totalDuration = Date.now() - this.startTime;
        console.log(`Progress tracking completed in ${this.formatDuration(totalDuration / 1000)}`);
        
        // Final statistics update
        this.updateCallbacks('Conversion completed successfully');
        
        return this.getStatistics();
    }

    // Reset tracker for new operation
    reset() {
        this.startTime = null;
        this.currentStep = null;
        this.totalSteps = 0;
        this.completedSteps = 0;
        this.stepTimestamps = [];
        this.currentStepStartTime = null;
        this.totalItems = 0;
        this.processedItems = 0;
        this.currentItem = '';
        this.stepHistory = [];
        this.performanceMetrics = {};
        
        console.log('ProgressTracker reset');
    }
}

// Export for use in other modules
window.ProgressTracker = ProgressTracker;
