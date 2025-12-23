/// <reference types="vite/client" />

/**
 * Architecture Note:
 * This file centralizes all API configuration.
 * It automatically selects the correct URL based on the environment/build mode.
 */

// 1. Read the base URL from the environment variables
const BASE_URL = import.meta.env.VITE_ADK_API_BASE_URL;

console.log(`API Service Initialized using Base URL: ${BASE_URL}`);
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

// 2. Helper to handle HTTP headers
const getHeaders = () => {
    return {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream, application/json, text/plain, */*',
    };
};

// 3. Centralized Response & Error Handler
const handleResponse = async (response: Response) => {
    if (!response.ok) {
        if (response.status === 401) console.warn('Unauthorized access...');
        if (response.status === 404) throw new Error('Resource not found');
        throw new Error(`HTTP Error: ${response.status}`);
    }

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
                    console.warn("Skipping incomplete or invalid SSE JSON chunk");
                }
                currentDataBuffer = "";
            }
        }
        if (currentDataBuffer) {
            try {
                const data = JSON.parse(currentDataBuffer);
                if (data?.content?.parts?.[0]?.text) {
                    fullBotText += data.content.parts[0].text;
                } else if (data?.parts?.[0]?.text) {
                    fullBotText += data.parts[0].text;
                }
            } catch (e) {
                 console.warn("Failed to parse final buffer");
            }
        }
        return {
            parts: [{ text: fullBotText.trim() }]
        };
    }
    if (response.status !== 204) {
         return await response.json();
    }
    return {};
};

// 4. The API Client Object
export const apiClient = {
    get: async (endpoint: string): Promise<any> => {
        try {
            const response = await fetch(`/api${endpoint}`, { 
                method: 'GET',
                headers: getHeaders(),
            });
            return await handleResponse(response);
        } catch (error) {
            console.error(`GET ${endpoint} failed:`, error);
            throw error;
        }
    },

    post: async (endpoint: string, body: any = {}): Promise<any> => {
        try {
            const response = await fetch(`/api${endpoint}`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify(body),
            });
            return await handleResponse(response);
        } catch (error) {
            console.error(`POST ${endpoint} failed:`, error);
            throw error;
        }
    },

    delete: async (endpoint: string): Promise<any> => {
        try {
            const response = await fetch(`/api${endpoint}`, {
                method: 'DELETE',
                headers: getHeaders(),
            });
            return await handleResponse(response);
        } catch (error) {
            console.error(`DELETE ${endpoint} failed:`, error);
            throw error;
        }
    },

    download: async (endpoint: string): Promise<Blob> => {
        try {
            const response = await fetch(`/api${endpoint}`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json, text/plain, */*',
                },
            });

            if (!response.ok) throw new Error(`Download failed: ${response.status}`);
            
            return await response.blob();
        } catch (error) {
            console.error(`Download ${endpoint} failed:`, error);
            throw error;
        }
    },

    baseUrl: BASE_URL
};

export const chatService = {
    /**
     * Sends a message to the bot via the /run_sse endpoint.
     * Handles both text and file attachments.
     */
    sendUserMessage: async (text: string, sessionId: string, files: any[] = []) => {
        
        const parts: any[] = [];
        if (text && text.trim().length > 0) {
            parts.push({ text: text });
        }

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