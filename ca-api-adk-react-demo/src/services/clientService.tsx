/// <reference types="vite/client" />
/**
 * Architecture Note:
 * This file centralizes all API configuration.
 * It automatically selects the correct URL based on the environment/build mode.
 */

// 1. Read the base URL from the environment variables
const BASE_URL = '';

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
            const response = await fetch(`${BASE_URL}${"/list-apps"}`, {
                method: 'GET',
                headers: getHeaders(),
            });

            if (!response.ok) {
                handleError(response.status);
            }

            const data = await response.json();
            console.log("--api adk res--", data);
            return data;
        } catch (error) {
            console.error(`GET ${endpoint} failed:`, error);
            throw error;
        }
    },

    /**
     * Generic POST request
     * Usage: await apiClient.post('/users', { name: 'Alice' });
     */
    //   post: async <T>(endpoint: string, body: any): Promise<T> => {
    //     try {
    //       const response = await fetch(`${BASE_URL}${endpoint}`, {
    //         method: 'POST',
    //         headers: getHeaders(),
    //         body: JSON.stringify(body),
    //       });

    //       if (!response.ok) {
    //         handleError(response.status);
    //       }

    //       return await response.json();
    //     } catch (error) {
    //       console.error(`POST ${endpoint} failed:`, error);
    //       throw error;
    //     }
    //   },

    // Expose the calculated URL if you need it for things like Images or Audio src
    baseUrl: BASE_URL
};

function async<T>(endpoint: any, string: any) {
    throw new Error("Function not implemented.");
}
