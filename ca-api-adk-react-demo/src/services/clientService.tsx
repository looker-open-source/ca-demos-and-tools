/// <reference types="vite/client" />
import { toastManager } from '../utils/ToastManager';

const BASE_URL = import.meta.env.VITE_ADK_API_BASE_URL;
console.log(`API Service Initialized using Base URL: ${BASE_URL}`);

// --- Helpers ---

const fileToBase64 = (file: Blob): Promise<string> => {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve((reader.result as string).split(',')[1]);
        reader.onerror = error => reject(error);
    });
};

const getHeaders = () => ({
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream, application/json, text/plain, */*',
});

const handleStreamingResponse = async (response: Response, onChunk?: (text: string) => void) => {
    if (!response.ok) {
        let errorMessage = `HTTP Error: ${response.status}`;
        try {
            const errorBody = await response.json();
            errorMessage = errorBody.message || errorBody.detail || errorMessage;
        } catch {
            const text = await response.text();
            if (text) errorMessage = text;
        }
        console.error(`API Error (${response.status}):`, errorMessage);
        toastManager.show(errorMessage, 'error');
        throw new Error(errorMessage);
    }

    const contentType = response.headers.get("content-type");

    if (!contentType || !contentType.includes("text/event-stream")) {
        if (response.status === 204) return {};
        return await response.json();
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    
    if (!reader) return {};

    let buffer = "";
    let fullText = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        
        const lines = buffer.split('\n');
        buffer = lines.pop() || "";

        for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data:")) {
                const jsonStr = trimmed.replace("data:", "").trim();
                if (!jsonStr) continue;

                try {
                    const data = JSON.parse(jsonStr);
                    let newText = "";

                    if (data?.content?.parts?.[0]?.text) {
                        newText = data.content.parts[0].text;
                    } else if (data?.parts?.[0]?.text) {
                        newText = data.parts[0].text;
                    }

                    if (newText) {
                        fullText += newText;
                        if (onChunk) onChunk(newText);
                    }
                } catch (e) {
                    console.warn("Stream parse error", e);
                }
            }
        }
    }
    
    return { parts: [{ text: fullText }] };
};

// --- API Client ---
export const apiClient = {
    get: async <T = any>(endpoint: string): Promise<T> => {
        try {
            const response = await fetch(`/api${endpoint}`, { 
                method: 'GET',
                headers: getHeaders(),
            });
            return await handleStreamingResponse(response);
        } catch (error: any) {
            const msg = error.message || "Network error.";
            if (!msg.includes("HTTP Error")) toastManager.show(msg, 'error');
            throw error;
        }
    },

    post: async <T = any>(endpoint: string, body: any = {}, onChunk?: (text: string) => void): Promise<T> => {
        try {
            const response = await fetch(`/api${endpoint}`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify(body),
            });
            return await handleStreamingResponse(response, onChunk);
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
            return await handleStreamingResponse(response);
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
            if (!response.ok) throw new Error(`Download failed: ${response.status}`);
            return await response.blob();
        } catch (error) {
            console.error(`Download ${endpoint} failed:`, error);
            toastManager.show("Failed to download file.", 'error');
            throw error;
        }
    },

    baseUrl: BASE_URL
};

export const chatService = {
    sendUserMessage: async (
        agentId: string,
        text: string, 
        sessionId: string, 
        files: any[] = [], 
        onChunk?: (text: string) => void
    ) => {
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
            appName: agentId,
            userId: "user",          
            sessionId: sessionId,
            newMessage: {
                role: "user",
                parts: parts 
            },
            streaming: false,
            stateDelta: null
        };

        return await apiClient.post('/run_sse', payload, onChunk);
    }
};