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

import { create } from 'zustand';

const TOKEN_STORAGE_KEY = 'looker_sdk_40_token';
const REFRESH_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes

interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  expiryTime: number | null; // Timestamp in ms
  sessionExpired: boolean;
  
  setAuthToken: (data: AuthTokenResponse) => void;
  clearToken: () => void;
  isTokenNearExpiry: () => boolean;
  initialize: () => void;
  setSessionExpired: (expired: boolean) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  refreshToken: null,
  expiryTime: null,
  sessionExpired: false,

  setAuthToken: (data) => {
    const expiryTime = Date.now() + data.expires_in * 1000;
    
    // Preserve old refresh token if new one is missing
    const currentRefreshToken = get().refreshToken;
    const refreshToken = data.refresh_token || currentRefreshToken;

    const updatedData = {
      ...data,
      refresh_token: refreshToken,
      expiry_at: expiryTime, // Store absolute timestamp
    };

    // Save to localStorage for persistence
    if (typeof window !== 'undefined') {
      localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(updatedData));
    }

    set({
      token: data.access_token,
      refreshToken: refreshToken,
      expiryTime: expiryTime,
      sessionExpired: false, // Reset expired state on success
    });
  },

  clearToken: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
    set({
      token: null,
      refreshToken: null,
      expiryTime: null,
      sessionExpired: false,
    });
  },

  isTokenNearExpiry: () => {
    const { expiryTime, token } = get();
    if (!token || !expiryTime) return true;
    
    const now = Date.now();
    return (expiryTime - now) <= REFRESH_THRESHOLD_MS;
  },

  initialize: () => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(TOKEN_STORAGE_KEY);
      if (stored) {
        try {
          const data: any = JSON.parse(stored);
          
          // Use stored absolute timestamp, or fallback to relative if it's an old record
          const expiryTime = data.expiry_at || (Date.now() + data.expires_in * 1000);

          set({
            token: data.access_token,
            refreshToken: data.refresh_token,
            expiryTime: expiryTime,
          });
        } catch (e) {
          console.error('Failed to parse stored token', e);
        }
      }
    }
  },

  setSessionExpired: (expired) => {
    set({ sessionExpired: expired });
  }
}));
