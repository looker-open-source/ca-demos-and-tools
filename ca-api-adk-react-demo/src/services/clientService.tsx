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
        'Accept': 'application/json, text/plain, */*',
    };
};

// 3. Centralized Response & Error Handler
const handleResponse = async (response: Response) => {
    if (!response.ok) {
        if (response.status === 401) {
            console.warn('Unauthorized access - redirecting to login...');
        }
        if (response.status === 404) {
            throw new Error('Resource not found');
        }
        throw new Error(`HTTP Error: ${response.status}`);
    }
    return await response.json();
};

// 4. The API Client Object
export const apiClient = {
    /**
     * Generic GET request
     * Used for fetching agents (/list-apps) and session history.
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
     * Used for creating new sessions.
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
            
            // Return the raw blob data
            return await response.blob();
        } catch (error) {
            console.error(`Download ${endpoint} failed:`, error);
            throw error;
        }
    },

    baseUrl: BASE_URL
};