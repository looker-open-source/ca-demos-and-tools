// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { useDevLogStore } from './store';
import { useAuthStore } from '@/store/useAuthStore';

// Promise to handle concurrent refresh requests
let refreshPromise: Promise<void> | null = null;

/**
 * standalone utility to log requests to the dev log store.
 * it wraps fetch or can be called manually.
 * Also injects Authorization header if a user token is found.
 */
export async function logRequest(input: RequestInfo | URL, init?: RequestInit): Promise<Response & { logId?: string }> {
  // Proactive token refresh
  // Always initialize/sync from localStorage to handle external modifications (e.g. manual testing)
  if (typeof window !== 'undefined') {
    useAuthStore.getState().initialize();
  }

  let authStore = useAuthStore.getState();
  
  // If we have a token and it's near expiry, try to refresh
  const isNearExpiry = authStore.isTokenNearExpiry();
  if (typeof window !== 'undefined' && authStore.token && isNearExpiry) {
    console.log('[Interceptor] Token near expiry, initiating refresh...', {
      token: !!authStore.token,
      expiryTime: authStore.expiryTime,
      now: Date.now(),
      isNearExpiry
    });
    
    if (!refreshPromise) {
      refreshPromise = (async () => {
        try {
          const refreshToken = authStore.refreshToken;
          if (!refreshToken) return;

          const response = await fetch('/api/token/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });

          if (response.ok) {
            const data = await response.json();
            useAuthStore.getState().setAuthToken(data);
          } else {
            console.error('Proactive token refresh failed');
            // Trigger session expired modal
            useAuthStore.getState().setSessionExpired(true);
          }
        } catch (error) {
          console.error('Error during proactive token refresh:', error);
        } finally {
          refreshPromise = null;
        }
      })();
    }
    
    // Wait for the refresh to complete before proceeding with the original request
    await refreshPromise;
    // Re-fetch state to get the new token
    authStore = useAuthStore.getState();
  }

  const id = Math.random().toString(36).substring(2, 9);
  let path = input.toString();
  
  // Clean up path - remove /api prefix
  path = path.replace(/^\/api/, '');

  const method = init?.method || 'GET';
  let payload = null;

  if (init?.body && typeof init.body === 'string') {
    try {
      payload = JSON.parse(init.body);
    } catch (e) {
      payload = init.body;
    }
  }

  // Inject Authorization header if we have a token
  // Use the token from the store as it might have been just refreshed
  const token = authStore.token;
  const modifiedInit = { ...init };
  if (token) {
    const headers = new Headers(modifiedInit.headers);
    if (!headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    modifiedInit.headers = headers;
  }

  useDevLogStore.getState().addLog({
    id,
    path,
    method,
    payload,
    status: 'pending',
    startTime: Date.now(),
    chunks: [],
  });

  try {
    const response = await fetch(input, modifiedInit);
    
    // If we get a 401, the token is invalid/expired
    if (response.status === 401) {
      console.warn('[Interceptor] 401 Unauthorized detected');
      useAuthStore.getState().setSessionExpired(true);
    }

    useDevLogStore.getState().updateLog(id, {
      status: response.status,
      endTime: Date.now(),
    });

    const interceptedResponse = response as Response & { logId?: string };
    interceptedResponse.logId = id;

    return interceptedResponse;
  } catch (error) {
    useDevLogStore.getState().updateLog(id, {
      status: 'error',
      endTime: Date.now(),
    });
    throw error;
  }
}
