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
import { useDevLogStore } from '../store';

describe('logRequest interceptor', () => {
  beforeEach(() => {
    useDevLogStore.getState().clearLogs();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      clone: () => ({
        json: async () => ({ success: true }),
        text: async () => JSON.stringify({ success: true }),
      }),
    });
    // Clear localStorage
    window.localStorage.clear();
  });

  it('should log a request and response', async () => {
    const response = await logRequest('/api/test', { 
      method: 'POST', 
      body: JSON.stringify({ hello: 'world' }) 
    });

    const state = useDevLogStore.getState();
    expect(state.logs).toHaveLength(1);
    expect(state.logs[0].path).toBe('/test');
    expect(state.logs[0].status).toBe(200);
    expect(state.logs[0].payload).toEqual({ hello: 'world' });
    expect(state.logs[0].endTime).toBeDefined();
  });

  it('should log an error status', async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 500,
      clone: () => ({
        text: async () => 'Internal Server Error',
      }),
    });

    await logRequest('/api/fail');

    const state = useDevLogStore.getState();
    expect(state.logs[0].status).toBe(500);
  });

  it('should inject Authorization header when token exists in localStorage', async () => {
    const mockToken = 'test-access-token';
    window.localStorage.setItem('looker_sdk_40_token', JSON.stringify({ access_token: mockToken }));

    await logRequest('/api/test');

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/test',
      expect.objectContaining({
        headers: expect.any(Headers)
      })
    );

    const callArgs = vi.mocked(global.fetch).mock.calls[0];
    const headers = callArgs[1]?.headers as Headers;
    expect(headers.get('Authorization')).toBe(`Bearer ${mockToken}`);
  });

  it('should not overwrite existing Authorization header', async () => {
    const mockToken = 'test-access-token';
    window.localStorage.setItem('looker_sdk_40_token', JSON.stringify({ access_token: mockToken }));

    const existingToken = 'existing-token';
    await logRequest('/api/test', {
      headers: {
        'Authorization': `Bearer ${existingToken}`
      }
    });

    const callArgs = vi.mocked(global.fetch).mock.calls[0];
    const headers = callArgs[1]?.headers as Headers;
    expect(headers.get('Authorization')).toBe(`Bearer ${existingToken}`);
  });
});
