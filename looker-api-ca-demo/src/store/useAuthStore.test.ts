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

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useAuthStore } from './useAuthStore';

describe('useAuthStore', () => {
  beforeEach(() => {
    useAuthStore.getState().clearToken();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should calculate expiry_time correctly when setting token', () => {
    const now = Date.now();
    const expiresIn = 3600; // 1 hour
    
    useAuthStore.getState().setAuthToken({
      access_token: 'access',
      refresh_token: 'refresh',
      expires_in: expiresIn,
      token_type: 'Bearer'
    });

    const state = useAuthStore.getState();
    expect(state.token).toBe('access');
    expect(state.refreshToken).toBe('refresh');
    // Allow for small timing differences if not using fake timers perfectly, 
    // but here we expect exactly now + expiresIn * 1000
    expect(state.expiryTime).toBe(now + expiresIn * 1000);
  });

  it('should detect when token is near expiry', () => {
    const expiresIn = 600; // 10 minutes
    useAuthStore.getState().setAuthToken({
      access_token: 'access',
      refresh_token: 'refresh',
      expires_in: expiresIn,
      token_type: 'Bearer'
    });

    // 4 minutes later (6 minutes left) -> not near expiry (threshold is 5 mins)
    vi.advanceTimersByTime(4 * 60 * 1000);
    expect(useAuthStore.getState().isTokenNearExpiry()).toBe(false);

    // 2 more minutes later (4 minutes left) -> near expiry
    vi.advanceTimersByTime(2 * 60 * 1000);
    expect(useAuthStore.getState().isTokenNearExpiry()).toBe(true);
  });

  it('should return true for isTokenNearExpiry if no token is set', () => {
    expect(useAuthStore.getState().isTokenNearExpiry()).toBe(true);
  });

  it('should clear token and expiry_time', () => {
    useAuthStore.getState().setAuthToken({
      access_token: 'access',
      refresh_token: 'refresh',
      expires_in: 3600,
      token_type: 'Bearer'
    });

    useAuthStore.getState().clearToken();
    
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.expiryTime).toBeNull();
  });
});
