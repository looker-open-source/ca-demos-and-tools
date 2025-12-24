/// <reference types="vite/client" />
import { toastManager } from '../utils/ToastManager'; // Import the manager

/**
 * Architecture Note:
 * This file centralizes all API configuration.
 * It uses ToastManager to push errors to the UI layer.
 */

const BASE_URL = import.meta.env.VITE_ADK_API_BASE_URL;
console.log(`API Service Initialized using Base URL: ${BASE_URL}`);

// --- Universal Interfaces ---
export interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  status: number;
}

const fileToBase64 = (file: Blob): Promise<string> => {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => {
            const result = reader.result as string;
            const base64 = result.split(',')[1]; 
            resolve(base64);
        };
        reader.onerror = error => reject(error);
    });
};

const getHeaders = () => {
    return {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream, application/json, text/plain, */*',
    };
};

// --- Centralized Response & Error Handler ---
const handleResponse = async (response: Response) => {
    // 1. Handle Errors (4xx, 5xx)
    if (!response.ok) {
        let errorMessage = `HTTP Error: ${response.status}`;
        
        try {
            // Try to parse detailed error from server JSON
            const errorBody = await response.json();
            errorMessage = errorBody.message || errorBody.detail || errorMessage;
        } catch {
            // If strictly text or empty
            const text = await response.text();
            if (text) errorMessage = text;
        }

        // Specific handling
        if (response.status === 401) errorMessage = "Unauthorized session. Please login again.";
        if (response.status === 404) errorMessage = "Requested resource not found.";

        // TRIGGER TOAST
        console.error(`API Error (${response.status}):`, errorMessage);
        toastManager.show(errorMessage, 'error');
        
        throw new Error(errorMessage);
    }

    // 2. Handle SSE (Streaming)
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("text/event-stream")) {
        const text = await response.text();
        const lines = text.split('\n');
        let fullBotText = "";
        let currentDataBuffer = "";

        for (const line of lines) {
            const trimmedLine = line.trim();
            if (trimmedLine.startsWith("data:")) {
                const content = line.replace("data:", "").trim();
                currentDataBuffer += content;
            } else if (trimmedLine === "" && currentDataBuffer) {
                try {
                    const data = JSON.parse(currentDataBuffer);                  
                    if (data?.content?.parts?.[0]?.text) {
                        fullBotText += data.content.parts[0].text + " ";
                    } else if (data?.parts?.[0]?.text) {
                        fullBotText += data.parts[0].text + " ";
                    }
                } catch (e) {
                    console.warn("Skipping incomplete SSE chunk");
                }
                currentDataBuffer = "";
            }
        }
        
        // Handle trailing buffer
        if (currentDataBuffer) {
            try {
                const data = JSON.parse(currentDataBuffer);
                if (data?.content?.parts?.[0]?.text) fullBotText += data.content.parts[0].text;
                else if (data?.parts?.[0]?.text) fullBotText += data.parts[0].text;
            } catch (e) {}
        }

        return { parts: [{ text: fullBotText.trim() }] };
    }

    // 3. Handle JSON / Empty
    if (response.status !== 204) {
         try {
             return await response.json();
         } catch (e) {
             console.warn("Response was ok but not valid JSON", e);
             return {}; 
         }
    }
    return {};
};

// --- API Client ---
export const apiClient = {
    get: async <T = any>(endpoint: string): Promise<T> => {
        try {
            const response = await fetch(`/api${endpoint}`, { 
                method: 'GET',
                headers: getHeaders(),
            });
            return await handleResponse(response);
        } catch (error: any) {
            // Catch network errors (e.g. server offline)
            const msg = error.message || "Network error. Please check your connection.";
            if (!msg.includes("HTTP Error")) {
                 toastManager.show(msg, 'error');
            }
            throw error;
        }
    },

    post: async <T = any>(endpoint: string, body: any = {}): Promise<T> => {
        try {
            const response = await fetch(`/api${endpoint}`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify(body),
            });
            return await handleResponse(response);
        } catch (error: any) {
            const msg = error.message || "Network error.";
            if (!msg.includes("HTTP Error")) {
                 toastManager.show(msg, 'error');
            }
            throw error;
        }
    },

    delete: async <T = any>(endpoint: string): Promise<T> => {
        try {
            const response = await fetch(`/api${endpoint}`, {
                method: 'DELETE',
                headers: getHeaders(),
            });
            return await handleResponse(response);
        } catch (error: any) {
            const msg = error.message || "Delete failed.";
            if (!msg.includes("HTTP Error")) {
                 toastManager.show(msg, 'error');
            }
            throw error;
        }
    },

    download: async (endpoint: string): Promise<Blob> => {
        try {
            const response = await fetch(`/api${endpoint}`, {
                method: 'GET',
                headers: { 'Accept': 'application/json, text/plain, */*' },
            });

            if (!response.ok) {
                // If download fails, try to read error text
                const errText = await response.text();
                throw new Error(errText || `Download failed: ${response.status}`);
            }
            
            return await response.blob();
        } catch (error: any) {
            console.error(`Download ${endpoint} failed:`, error);
            toastManager.show("Failed to download file.", 'error');
            throw error;
        }
    },

    baseUrl: BASE_URL
};

export const chatService = {
    sendUserMessage: async (text: string, sessionId: string, files: any[] = []) => {
        const parts: any[] = [];
        if (text && text.trim().length > 0) parts.push({ text: text });

        if (files && files.length > 0) {
            for (const fileObj of files) {
                let actualFile: Blob | null = null;
                let displayName = "attachment";
                let mimeType = "application/octet-stream"; 

                if (fileObj instanceof Blob) {
                    actualFile = fileObj;
                    if ('name' in fileObj) displayName = (fileObj as File).name;
                    if (fileObj.type) mimeType = fileObj.type; 
                } else if (fileObj.file instanceof Blob) {
                    actualFile = fileObj.file;
                    displayName = fileObj.name || "attachment";
                    if (fileObj.file.type) mimeType = fileObj.file.type;
                }

                if (!actualFile) {
                    console.error("Skipping invalid file object:", fileObj);
                    continue;
                }

                try {
                    const base64Data = await fileToBase64(actualFile);
                    parts.push({
                        inlineData: {
                            displayName: displayName,
                            data: base64Data,
                            mimeType: mimeType 
                        }
                    });
                } catch (err) {
                    console.error("Failed to process file:", displayName, err);
                    toastManager.show(`Failed to attach file: ${displayName}`, 'warning');
                }
            }
        }

        const payload = {
            appName: "ca_api_agent", 
            userId: "user",          
            sessionId: sessionId,
            newMessage: {
                role: "user",
                parts: parts 
            },
            streaming: false,
            stateDelta: null
        };

        return await apiClient.post('/run_sse', payload);
    }
};