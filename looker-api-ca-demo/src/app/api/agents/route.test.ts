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
import { listLookerAgents } from '@/lib/looker-agent';
import { NextResponse } from 'next/server';

vi.mock('@/lib/looker-agent');
vi.mock('next/server', () => ({
  NextResponse: {
    json: vi.fn((data, init) => ({
      json: async () => data,
      status: init?.status || 200,
    })),
  },
}));

describe('Agents API Route', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_LOOKER_BASE_URL = 'https://test.looker.com';
    process.env.LOOKER_CLIENT_ID = 'test-id';
    process.env.LOOKER_CLIENT_SECRET = 'test-secret';
  });

  it('should return a list of agents and defaultAgentId', async () => {
    const mockAgents = [{ id: '1', name: 'Agent 1' }];
    process.env.NEXT_PUBLIC_DEFAULT_AGENT_ID = 'test-agent-id';
    (listLookerAgents as any).mockResolvedValue(mockAgents);

    const response = await GET();
    const data = await response.json();

    expect(data).toEqual({
      agents: mockAgents,
      defaultAgentId: 'test-agent-id',
      lookerBaseUrl: 'https://test.looker.com'
    });
    expect(listLookerAgents).toHaveBeenCalled();
  });

  it('should return 500 if configuration is missing', async () => {
    delete process.env.NEXT_PUBLIC_LOOKER_BASE_URL;

    const response = await GET();
    expect(response.status).toBe(500);
    const data = await response.json();
    expect(data.error).toBe('Looker configuration missing');
  });

  it('should return 500 if Looker API fails', async () => {
    (listLookerAgents as any).mockRejectedValue(new Error('API failed'));

    const response = await GET();
    expect(response.status).toBe(500);
    const data = await response.json();
    expect(data.error).toBe('API failed');
  });
});
