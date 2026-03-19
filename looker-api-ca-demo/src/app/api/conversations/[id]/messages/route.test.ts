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
import { getLookerConversationMessages } from '@/lib/looker-conversation';
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

describe('Conversation Messages API Route', () => {
  const conversationId = 'conv-123';
  const mockParams = { params: Promise.resolve({ id: conversationId }) };

  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_LOOKER_BASE_URL = 'https://test.looker.com';
    process.env.LOOKER_CLIENT_ID = 'test-id';
    process.env.LOOKER_CLIENT_SECRET = 'test-secret';
  });

  it('should return conversation messages', async () => {
    const mockMessages = [{ type: 'user', message: { userMessage: { text: 'hello' } } }];
    (getLookerConversationMessages as any).mockResolvedValue(mockMessages);

    const response = await GET({} as Request, mockParams);
    const data = await response.json();

    expect(data).toEqual(mockMessages);
    expect(getLookerConversationMessages).toHaveBeenCalledWith(conversationId);
  });
});
