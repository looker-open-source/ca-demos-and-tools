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
import { POST } from './route';
import { NextRequest } from 'next/server';

describe('Token Refresh API Route', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_LOOKER_BASE_URL = 'https://test.looker.com';
    process.env.NEXT_PUBLIC_LOOKER_OAUTH_CLIENT_ID = 'test-oauth-client-id';
    
    // Mock global fetch
    global.fetch = vi.fn();
  });

  it('should refresh the token using the refresh_token from request body', async () => {
    const mockTokenResponse = {
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
      expires_in: 3600,
      token_type: 'Bearer',
    };

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockTokenResponse,
    });

    const req = new NextRequest('http://localhost/api/token/refresh', {
      method: 'POST',
      body: JSON.stringify({
        refresh_token: 'old-refresh-token',
      }),
    });

    const response = await POST(req);
    const data = await response.json();

    expect(global.fetch).toHaveBeenCalledWith(
      'https://test.looker.com/api/token',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          grant_type: 'refresh_token',
          refresh_token: 'old-refresh-token',
          client_id: 'test-oauth-client-id',
        }),
      })
    );
    expect(data).toEqual(mockTokenResponse);
  });

  it('should return 400 if refresh_token is missing', async () => {
    const req = new NextRequest('http://localhost/api/token/refresh', {
      method: 'POST',
      body: JSON.stringify({}),
    });

    const response = await POST(req);
    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toBe('Missing refresh_token');
  });

  it('should return 500 if Looker token refresh fails', async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      text: async () => 'Invalid refresh token',
    });

    const req = new NextRequest('http://localhost/api/token/refresh', {
      method: 'POST',
      body: JSON.stringify({
        refresh_token: 'invalid-refresh-token',
      }),
    });

    const response = await POST(req);
    expect(response.status).toBe(500);
    const data = await response.json();
    expect(data.error).toBe('Failed to refresh token');
  });
});
