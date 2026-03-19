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
import { createLookerConversation, persistLookerMessages } from '@/lib/looker-conversation';
import { listLookerAgents } from '@/lib/looker-agent';
import { NextRequest } from 'next/server';

vi.mock('@/lib/looker-chat', () => ({
  sendLookerChatMessageStreaming: vi.fn().mockImplementation(async function* () {
    yield { text: { parts: ['Hello'] } };
  }),
}));
vi.mock('@/lib/looker-conversation');
vi.mock('@/lib/looker-agent');
vi.mock('@/lib/log-utils');
vi.mock('@/lib/error-mapping');

describe('Chat API Route', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_LOOKER_BASE_URL = 'https://test.looker.com';
    process.env.LOOKER_CLIENT_ID = 'test-id';
    process.env.LOOKER_CLIENT_SECRET = 'test-secret';
  });

  it('should use agentId from request body when creating a new conversation', async () => {
    (createLookerConversation as any).mockResolvedValue({ id: 'new-conv-id' });

    const req = new NextRequest('http://localhost/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        userMessage: 'Hello',
        agentId: 'specific-agent-id',
      }),
    });

    const response = await POST(req);
    const reader = response.body?.getReader();
    while (!(await reader?.read())?.done);

    expect(createLookerConversation).toHaveBeenCalledWith('specific-agent-id', undefined);
  });

  it('should fallback to first agent if agentId is not provided', async () => {
    (listLookerAgents as any).mockResolvedValue([{ id: 'first-agent-id' }]);
    (createLookerConversation as any).mockResolvedValue({ id: 'new-conv-id' });

    const req = new NextRequest('http://localhost/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        userMessage: 'Hello',
      }),
    });

    const response = await POST(req);
    const reader = response.body?.getReader();
    while (!(await reader?.read())?.done);

    expect(listLookerAgents).toHaveBeenCalled();
    expect(createLookerConversation).toHaveBeenCalledWith('first-agent-id', undefined);
  });

  it('should extract and pass Authorization header token', async () => {
    (createLookerConversation as any).mockResolvedValue({ id: 'new-conv-id' });
    const { sendLookerChatMessageStreaming } = await import('@/lib/looker-chat');

    const req = new NextRequest('http://localhost/api/chat', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer test-user-token',
      },
      body: JSON.stringify({
        userMessage: 'Hello',
      }),
    });

    const response = await POST(req);
    const reader = response.body?.getReader();
    while (!(await reader?.read())?.done);

    expect(createLookerConversation).toHaveBeenCalledWith(expect.any(String), 'test-user-token');
    expect(sendLookerChatMessageStreaming).toHaveBeenCalledWith(expect.any(String), expect.any(String), 'test-user-token');
  });

  it('should pass the provided timestamp to persistLookerMessages', async () => {
    const testTimestamp = '2026-03-17T12:00:00.000Z';
    (createLookerConversation as any).mockResolvedValue({ id: 'conv-id' });

    const req = new NextRequest('http://localhost/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        userMessage: 'Test message',
        conversationId: 'conv-id',
        timestamp: testTimestamp,
      }),
    });

    const response = await POST(req);
    const reader = response.body?.getReader();
    while (!(await reader?.read())?.done);

    expect(persistLookerMessages).toHaveBeenCalledWith(
      'conv-id',
      'Test message',
      expect.any(Array),
      testTimestamp,
      undefined
    );
  });
});
