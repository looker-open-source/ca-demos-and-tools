/// <reference types="vite/client" />
/**
 * Architecture Note:
 * This file centralizes all API configuration.
 * It automatically selects the correct URL based on the environment/build mode.
 */
// 1. Read the base URL from the environment variables
// Ensure this is the only way you are accessing it
const BASE_URL = import.meta.env.VITE_ADK_API_BASE_URL;

console.log(`API Service Initialized using Base URL: ${BASE_URL}`);

// 2. Define common types for your API responses (optional but recommended)
export interface ApiResponse<T> {
    data: T;
    error?: string;
}

// 3. Helper to handle HTTP headers
const getHeaders = () => {
    const headers: HeadersInit = {
        'Content-Type': 'application/json',
    };
    return headers;
};

// 4. Centralized Error Handler
// MOVED UP: Must be defined before it is used in apiClient
const handleError = (status: number) => {
    if (status === 401) {
        console.warn('Unauthorized access - redirecting to login...');
    }
    if (status === 404) {
        throw new Error('Resource not found');
    }
    throw new Error(`HTTP Error: ${status}`);
};

// 5. The API Client Object
export const apiClient = {
    /**
     * Generic GET request
     * Usage: const data = await apiClient.get<User>('/users/1');
     */
    get: async (endpoint: any): Promise<any> => {
        try {
            // The browser sees: http://localhost:5173/api/list-apps
            // Vite forwards: http://localhost:8000/list-apps
            const response = await fetch(`/api${endpoint}`, { 
                method: 'GET',
                headers: getHeaders(),
            });

            // ... rest of the logic
        } catch (error) {
            console.error(`GET ${endpoint} failed:`, error);
            throw error;
        }
    },
    // ...
    baseUrl: BASE_URL // You can keep this exposed for non-proxy uses like images
};
function async<T>(endpoint: any, string: any) {
    throw new Error("Function not implemented.");
}
