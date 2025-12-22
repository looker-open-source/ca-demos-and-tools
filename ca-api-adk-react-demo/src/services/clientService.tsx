/// <reference types="vite/client" />

/**
 * Architecture Note:
 * This file centralizes all API configuration.
 * It automatically selects the correct URL based on the environment/build mode.
 */

// 1. Read the base URL from the environment variables
const BASE_URL = import.meta.env.VITE_ADK_API_BASE_URL;

console.log(`API Service Initialized using Base URL: ${BASE_URL}`);

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

        for (const line of lines) {
            const trimmedLine = line.trim();
            if (trimmedLine.startsWith("data:")) {
                try {
                    const jsonStr = trimmedLine.replace("data:", "").trim();
                    const data = JSON.parse(jsonStr);

                    if (data?.content?.parts?.[0]?.text) {
                        fullBotText += data.content.parts[0].text + " ";
                    } 
                    else if (data?.parts?.[0]?.text) {
                        fullBotText += data.parts[0].text + " ";
                    }
                } catch (e) {
                    console.error("Error parsing SSE line:", e);
                }
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
    /**
     * Generic GET request
     */
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

    /**
     * Generic POST request
     */
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
     * Encapsulates the specific payload structure required by the backend.
     * * @param text The message text from the user
     * @param sessionId The current session ID
     */
    sendUserMessage: async (text: string, sessionId: string) => {
        const payload = {
            appName: "ca_api_agent", 
            userId: "user",          
            sessionId: sessionId,
            newMessage: {
                role: "user",
                parts: [{ text: text }]
            },
            streaming: false,
            stateDelta: null
        };

        return await apiClient.post('/run_sse', payload);
    }
};