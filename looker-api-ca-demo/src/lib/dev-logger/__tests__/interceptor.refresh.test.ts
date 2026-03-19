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

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { logRequest } from '../interceptor';
import { useAuthStore } from '@/store/useAuthStore';

// Mock the global fetch
global.fetch = vi.fn();

describe('logRequest interceptor proactive refresh', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().clearToken();
    (global.fetch as any).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true }),
      text: async () => JSON.stringify({ success: true }),
    });
  });

  it('should refresh the token if it is near expiry before making the original request', async () => {
    const oldToken = 'old-access-token';
    const refreshToken = 'refresh-token';
    const newToken = 'new-access-token';

    // Set up store with token near expiry
    useAuthStore.getState().setAuthToken({
      access_token: oldToken,
      refresh_token: refreshToken,
      expires_in: 300, // 5 minutes exactly -> near expiry
      token_type: 'Bearer'
    });

    // Mock the refresh API call
    (global.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/token/refresh') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            access_token: newToken,
            refresh_token: 'new-refresh-token',
            expires_in: 3600,
            token_type: 'Bearer'
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ data: 'success' }),
      });
    });

    // Perform a request
    await logRequest('/api/test-data');

    // Verify refresh was called first
    expect(global.fetch).toHaveBeenCalledWith('/api/token/refresh', expect.any(Object));

    // Verify original request used the NEW token
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/test-data',
      expect.objectContaining({
        headers: expect.any(Headers)
      })
    );

    const callArgs = vi.mocked(global.fetch).mock.calls.find(call => call[0] === '/api/test-data');
    const headers = callArgs?.[1]?.headers as Headers;
    expect(headers.get('Authorization')).toBe(`Bearer ${newToken}`);
  });

  it('should handle concurrent requests by only refreshing once', async () => {
    const oldToken = 'old-access-token';
    const refreshToken = 'refresh-token';
    const newToken = 'new-access-token';

    useAuthStore.getState().setAuthToken({
      access_token: oldToken,
      refresh_token: refreshToken,
      expires_in: 60, // 1 minute -> near expiry
      token_type: 'Bearer'
    });

    let refreshCallCount = 0;
    (global.fetch as any).mockImplementation(async (url: string) => {
      if (url === '/api/token/refresh') {
        refreshCallCount++;
        // Simulate network delay
        await new Promise(resolve => setTimeout(resolve, 50));
        return {
          ok: true,
          status: 200,
          json: async () => ({
            access_token: newToken,
            refresh_token: 'new-refresh-token',
            expires_in: 3600,
            token_type: 'Bearer'
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ data: 'success' }),
      };
    });

    // Trigger multiple concurrent requests
    await Promise.all([
      logRequest('/api/req1'),
      logRequest('/api/req2'),
      logRequest('/api/req3'),
    ]);

    // Verify refresh was called only ONCE
    expect(refreshCallCount).toBe(1);

    // Verify all requests used the NEW token
    const calls = vi.mocked(global.fetch).mock.calls.filter(call => call[0].toString().startsWith('/api/req'));
    expect(calls).toHaveLength(3);
    calls.forEach(call => {
      const headers = call[1]?.headers as Headers;
      expect(headers.get('Authorization')).toBe(`Bearer ${newToken}`);
    });
  });
});
