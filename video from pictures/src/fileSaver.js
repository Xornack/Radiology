// File Saver Module - Step 3.1
// Enhanced MP4 file save functionality for Phase 3: Output and Validation
// Provides multiple save options and advanced file management

class FileSaver {
    constructor() {
        this.supportedMethods = {
            fileSystemAccess: false,
            download: true,
            showSaveFilePicker: false
        };
        
        this.defaultSettings = {
            defaultDirectory: null,
            autoSave: false,
            confirmOverwrite: true,
            generateUniqueNames: true,
            preserveTimestamp: true
        };
        
        this.settings = { ...this.defaultSettings };
        this.lastSaveLocation = null;
        
        // Detect available save methods
        this.detectSaveMethods();
        
        console.log('FileSaver initialized. Available methods:', this.supportedMethods);
    }
    
    // Detect available file saving methods
    detectSaveMethods() {
        // Check for File System Access API (showSaveFilePicker)
        if ('showSaveFilePicker' in window) {
            this.supportedMethods.showSaveFilePicker = true;
            console.log('File System Access API (showSaveFilePicker) available');
        }
        
        // File System Access API support check
        if ('showDirectoryPicker' in window) {
            this.supportedMethods.fileSystemAccess = true;
            console.log('File System Access API (directory) available');
        }
        
        console.log('FileSaver method detection complete:', this.supportedMethods);
    }
    
    // Update saver settings
    updateSettings(newSettings) {
        this.settings = { ...this.settings, ...newSettings };
        console.log('FileSaver settings updated:', this.settings);
    }
    
    // Get browser capabilities for file saving
    getBrowserCapabilities() {
        return {
            supportedMethods: this.supportedMethods,
            preferredMethod: this.getPreferredSaveMethod(),
            settings: this.settings,
            lastSaveLocation: this.lastSaveLocation
        };
    }
    
    // Determine the best available save method
    getPreferredSaveMethod() {
        if (this.supportedMethods.showSaveFilePicker) {
            return 'showSaveFilePicker';
        } else if (this.supportedMethods.fileSystemAccess) {
            return 'fileSystemAccess';
        } else {
            return 'download';
        }
    }
    
    // Main save function - automatically chooses best method
    async saveVideo(videoBlob, suggestedFilename, options = {}) {
        const saveOptions = { ...this.settings, ...options };
        
        try {
            console.log(`Saving video file: ${suggestedFilename} (${(videoBlob.size / 1024 / 1024).toFixed(2)} MB)`);
            
            // Generate final filename with uniqueness check if needed
            const finalFilename = saveOptions.generateUniqueNames ? 
                this.generateUniqueFilename(suggestedFilename) : 
                suggestedFilename;
            
            const preferredMethod = this.getPreferredSaveMethod();
            console.log(`Using save method: ${preferredMethod}`);
            
            let result;
            switch (preferredMethod) {
                case 'showSaveFilePicker':
                    result = await this.saveWithFilePicker(videoBlob, finalFilename, saveOptions);
                    break;
                case 'fileSystemAccess':
                    result = await this.saveWithFileSystemAccess(videoBlob, finalFilename, saveOptions);
                    break;
                default:
                    result = await this.saveWithDownload(videoBlob, finalFilename, saveOptions);
                    break;
            }
            
            // Record successful save location
            if (result.success) {
                this.lastSaveLocation = result.location;
                console.log('Video saved successfully:', result);
            }
            
            return result;
            
        } catch (error) {
            console.error('Failed to save video file:', error);
            return {
                success: false,
                error: error.message,
                method: 'unknown',
                filename: suggestedFilename
            };
        }
    }
    
    // Save using File System Access API (showSaveFilePicker)
    async saveWithFilePicker(videoBlob, filename, options) {
        try {
            const fileHandle = await window.showSaveFilePicker({
                suggestedName: filename,
                types: [{
                    description: 'MP4 Video files',
                    accept: {
                        'video/mp4': ['.mp4']
                    }
                }],
                excludeAcceptAllOption: true
            });
            
            const writable = await fileHandle.createWritable();
            await writable.write(videoBlob);
            await writable.close();
            
            return {
                success: true,
                method: 'showSaveFilePicker',
                filename: fileHandle.name,
                location: fileHandle.name,
                size: videoBlob.size,
                timestamp: new Date().toISOString()
            };
            
        } catch (error) {
            if (error.name === 'AbortError') {
                return {
                    success: false,
                    error: 'Save operation was cancelled by user',
                    method: 'showSaveFilePicker',
                    cancelled: true
                };
            }
            throw error;
        }
    }
    
    // Save using File System Access API (directory-based)
    async saveWithFileSystemAccess(videoBlob, filename, options) {
        try {
            let directoryHandle;
            
            // Use previously selected directory or prompt for new one
            if (options.useLastDirectory && this.lastSaveLocation) {
                // This would require storing directory handle, but it's not persistent
                // Fall back to prompting for directory
            }
            
            directoryHandle = await window.showDirectoryPicker({
                mode: 'readwrite'
            });
            
            // Check if file already exists and handle accordingly
            let fileHandle;
            const fileExists = await this.checkFileExists(directoryHandle, filename);
            
            if (fileExists && options.confirmOverwrite) {
                const shouldOverwrite = confirm(`File "${filename}" already exists. Do you want to overwrite it?`);
                if (!shouldOverwrite) {
                    return {
                        success: false,
                        error: 'Save operation cancelled - file exists',
                        method: 'fileSystemAccess',
                        cancelled: true
                    };
                }
            }
            
            fileHandle = await directoryHandle.getFileHandle(filename, { create: true });
            const writable = await fileHandle.createWritable();
            await writable.write(videoBlob);
            await writable.close();
            
            return {
                success: true,
                method: 'fileSystemAccess',
                filename: filename,
                location: directoryHandle.name + '/' + filename,
                size: videoBlob.size,
                timestamp: new Date().toISOString()
            };
            
        } catch (error) {
            if (error.name === 'AbortError') {
                return {
                    success: false,
                    error: 'Save operation was cancelled by user',
                    method: 'fileSystemAccess',
                    cancelled: true
                };
            }
            throw error;
        }
    }
    
    // Save using traditional download method (fallback)
    async saveWithDownload(videoBlob, filename, options) {
        try {
            const url = URL.createObjectURL(videoBlob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.style.display = 'none';
            
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            // Clean up URL object after a delay
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            
            return {
                success: true,
                method: 'download',
                filename: filename,
                location: 'Downloads folder (default browser location)',
                size: videoBlob.size,
                timestamp: new Date().toISOString(),
                note: 'File downloaded to browser\'s default download location'
            };
            
        } catch (error) {
            throw new Error(`Download failed: ${error.message}`);
        }
    }
    
    // Check if a file exists in a directory handle
    async checkFileExists(directoryHandle, filename) {
        try {
            await directoryHandle.getFileHandle(filename);
            return true;
        } catch (error) {
            if (error.name === 'NotFoundError') {
                return false;
            }
            throw error;
        }
    }
    
    // Generate unique filename with timestamp
    generateUniqueFilename(originalFilename) {
        const timestamp = new Date().toISOString()
            .replace(/[:.]/g, '-')
            .replace('T', '_')
            .substring(0, 19);
        
        const lastDotIndex = originalFilename.lastIndexOf('.');
        if (lastDotIndex === -1) {
            return `${originalFilename}_${timestamp}`;
        }
        
        const name = originalFilename.substring(0, lastDotIndex);
        const extension = originalFilename.substring(lastDotIndex);
        
        return `${name}_${timestamp}${extension}`;
    }
    
    // Save with user-chosen method
    async saveWithMethodChoice(videoBlob, filename, allowedMethods = null) {
        const availableMethods = allowedMethods || Object.keys(this.supportedMethods).filter(
            method => this.supportedMethods[method]
        );
        
        if (availableMethods.length === 1) {
            // Only one method available, use it directly
            return await this.saveVideo(videoBlob, filename);
        }
        
        // Create method selection UI
        return new Promise((resolve) => {
            this.showMethodSelectionDialog(availableMethods, async (selectedMethod) => {
                try {
                    let result;
                    switch (selectedMethod) {
                        case 'showSaveFilePicker':
                            result = await this.saveWithFilePicker(videoBlob, filename, this.settings);
                            break;
                        case 'fileSystemAccess':
                            result = await this.saveWithFileSystemAccess(videoBlob, filename, this.settings);
                            break;
                        case 'download':
                            result = await this.saveWithDownload(videoBlob, filename, this.settings);
                            break;
                        default:
                            result = await this.saveVideo(videoBlob, filename);
                    }
                    resolve(result);
                } catch (error) {
                    resolve({
                        success: false,
                        error: error.message,
                        method: selectedMethod
                    });
                }
            });
        });
    }
    
    // Show method selection dialog
    showMethodSelectionDialog(availableMethods, callback) {
        const dialog = document.createElement('div');
        dialog.id = 'saveMethodDialog';
        dialog.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
        `;
        
        const dialogContent = document.createElement('div');
        dialogContent.style.cssText = `
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        `;
        
        const methodDescriptions = {
            showSaveFilePicker: 'Save File Dialog - Choose exact location and filename',
            fileSystemAccess: 'Directory Access - Choose folder and save with current filename',
            download: 'Browser Download - Save to default downloads folder'
        };
        
        let html = `
            <h3>Choose Save Method</h3>
            <p>Select how you'd like to save the video file:</p>
        `;
        
        availableMethods.forEach(method => {
            if (this.supportedMethods[method]) {
                html += `
                    <div style="margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer;" 
                         onclick="selectSaveMethod('${method}')">
                        <strong>${method.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}</strong><br>
                        <small style="color: #666;">${methodDescriptions[method]}</small>
                    </div>
                `;
            }
        });
        
        html += `
            <div style="text-align: center; margin-top: 20px;">
                <button onclick="cancelSaveMethod()" style="padding: 8px 16px; background-color: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">Cancel</button>
            </div>
        `;
        
        dialogContent.innerHTML = html;
        dialog.appendChild(dialogContent);
        document.body.appendChild(dialog);
        
        // Add global functions for dialog interaction
        window.selectSaveMethod = (method) => {
            document.body.removeChild(dialog);
            delete window.selectSaveMethod;
            delete window.cancelSaveMethod;
            callback(method);
        };
        
        window.cancelSaveMethod = () => {
            document.body.removeChild(dialog);
            delete window.selectSaveMethod;
            delete window.cancelSaveMethod;
            callback(null);
        };
    }
    
    // Get save history/statistics
    getSaveHistory() {
        // This would be enhanced with localStorage persistence in a full implementation
        return {
            lastSaveLocation: this.lastSaveLocation,
            preferredMethod: this.getPreferredSaveMethod(),
            settings: this.settings
        };
    }
    
    // Validate save capabilities
    validateSaveCapabilities() {
        const capabilities = [];
        
        if (this.supportedMethods.showSaveFilePicker) {
            capabilities.push({
                method: 'showSaveFilePicker',
                description: 'Modern save dialog with precise file location control',
                recommended: true
            });
        }
        
        if (this.supportedMethods.fileSystemAccess) {
            capabilities.push({
                method: 'fileSystemAccess',
                description: 'Directory-based saving with folder selection',
                recommended: true
            });
        }
        
        capabilities.push({
            method: 'download',
            description: 'Standard browser download (fallback method)',
            recommended: false
        });
        
        return {
            available: capabilities,
            total: capabilities.length,
            modern: capabilities.filter(c => c.recommended).length
        };
    }
}

// Export for use in main application
if (typeof window !== 'undefined') {
    window.FileSaver = FileSaver;
}
