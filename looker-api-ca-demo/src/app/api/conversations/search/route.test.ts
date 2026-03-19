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
import { GET } from './route';
import { searchLookerConversations } from '@/lib/looker-conversation';
import { NextResponse } from 'next/server';

vi.mock('@/lib/looker-conversation');
vi.mock('next/server', () => ({
  NextResponse: {
    json: vi.fn((data, init) => ({
      json: async () => data,
      status: init?.status || 200,
    })),
  },
}));

describe('Conversations Search API Route', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_LOOKER_BASE_URL = 'https://test.looker.com';
    process.env.LOOKER_CLIENT_ID = 'test-id';
    process.env.LOOKER_CLIENT_SECRET = 'test-secret';
  });

  it('should return a list of conversations for a given agent_id', async () => {
    const mockConversations = [{ id: 'conv-1', name: 'Conversation 1', agent_id: 'agent-1' }];
    const agentId = 'agent-1';
    
    (searchLookerConversations as any).mockResolvedValue(mockConversations);

    const mockRequest = {
      url: `http://localhost/api/conversations/search?agent_id=${agentId}`,
    } as any;

    const response = await GET(mockRequest);
    const data = await response.json();

    expect(data).toEqual(mockConversations);
    expect(searchLookerConversations).toHaveBeenCalledWith({ agent_id: agentId });
  });

  it('should return 400 if agent_id is missing', async () => {
    const mockRequest = {
      url: `http://localhost/api/conversations/search`,
    } as any;

    const response = await GET(mockRequest);
    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toBe('agent_id is required');
  });

  it('should return 500 if configuration is missing', async () => {
    delete process.env.NEXT_PUBLIC_LOOKER_BASE_URL;
    const mockRequest = {
      url: `http://localhost/api/conversations/search?agent_id=agent-1`,
    } as any;

    const response = await GET(mockRequest);
    expect(response.status).toBe(500);
    const data = await response.json();
    expect(data.error).toBe('Looker configuration missing');
  });

  it('should return 500 if Looker API fails', async () => {
    (searchLookerConversations as any).mockRejectedValue(new Error('API failed'));
    const mockRequest = {
      url: `http://localhost/api/conversations/search?agent_id=agent-1`,
    } as any;

    const response = await GET(mockRequest);
    expect(response.status).toBe(500);
    const data = await response.json();
    expect(data.error).toBe('API failed');
  });
});
