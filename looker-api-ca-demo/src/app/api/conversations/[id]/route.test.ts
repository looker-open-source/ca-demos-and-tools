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
import { GET, DELETE, PATCH } from './route';
import {
  getLookerConversation,
  deleteLookerConversation,
  patchLookerConversation,
} from '@/lib/looker-conversation';
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

describe('Conversation ID API Route', () => {
  const conversationId = 'conv-123';
  const mockParams = { params: Promise.resolve({ id: conversationId }) };

  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_LOOKER_BASE_URL = 'https://test.looker.com';
    process.env.LOOKER_CLIENT_ID = 'test-id';
    process.env.LOOKER_CLIENT_SECRET = 'test-secret';
  });

  describe('GET', () => {
    it('should return conversation details', async () => {
      const mockConversation = { id: conversationId, name: 'Test' };
      (getLookerConversation as any).mockResolvedValue(mockConversation);

      const response = await GET({} as Request, mockParams);
      const data = await response.json();

      expect(data).toEqual(mockConversation);
      expect(getLookerConversation).toHaveBeenCalledWith(conversationId);
    });
  });

  describe('DELETE', () => {
    it('should delete a conversation', async () => {
      (deleteLookerConversation as any).mockResolvedValue(undefined);

      const response = await DELETE({} as Request, mockParams);
      const data = await response.json();

      expect(data).toEqual({ success: true });
      expect(deleteLookerConversation).toHaveBeenCalledWith(conversationId);
    });
  });

  describe('PATCH', () => {
    it('should rename a conversation', async () => {
      const newName = 'Updated Name';
      const mockUpdatedConversation = { id: conversationId, name: newName };
      (patchLookerConversation as any).mockResolvedValue(mockUpdatedConversation);

      const mockRequest = {
        json: async () => ({ name: newName }),
      } as any;

      const response = await PATCH(mockRequest, mockParams);
      const data = await response.json();

      expect(data).toEqual(mockUpdatedConversation);
      expect(patchLookerConversation).toHaveBeenCalledWith(
        conversationId,
        { name: newName }
      );
    });

    it('should return 400 if name is missing', async () => {
      const mockRequest = {
        json: async () => ({}),
      } as any;

      const response = await PATCH(mockRequest, mockParams);
      expect(response.status).toBe(400);
      const data = await response.json();
      expect(data.error).toBe('name is required');
    });
  });
});
