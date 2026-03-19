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
import { sendLookerChatMessageStreaming } from './looker-chat';
import { getLookerSDK } from './looker-sdk';

vi.mock('./looker-sdk', () => ({
  getLookerSDK: vi.fn(),
}));

describe('sendLookerChatMessageStreaming', () => {
  const mockConversationId = 'test-conv-id';
  const mockUserMessage = 'Test query';

  beforeEach(() => {
    vi.clearAllMocks();
    (getLookerSDK as any).mockReturnValue({
      authSession: {
        isAuthenticated: vi.fn().mockReturnValue(true),
        login: vi.fn().mockResolvedValue(undefined),
        settings: {
            agentTag: 'test-agent-tag',
        },
      },
      stream: {
        conversational_analytics_chat: vi.fn(),
      },
      ok: vi.fn((p) => p),
    });
  });

  it('should stream chat messages from Looker SDK', async () => {
    const mockMessages = [
      { systemMessage: { text: { parts: ['Hello'] } } },
      { systemMessage: { text: { parts: ['World'] } } }
    ];

    const sdk = getLookerSDK();
    (sdk as any).stream.conversational_analytics_chat.mockImplementation((callback: any) => {
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(JSON.stringify(mockMessages[0]) + '\n'));
          controller.enqueue(new TextEncoder().encode(JSON.stringify(mockMessages[1]) + '\n'));
          controller.close();
        }
      });
      callback({ body: stream } as any);
    });

    const received: any[] = [];
    for await (const msg of sendLookerChatMessageStreaming(mockConversationId, mockUserMessage)) {
      received.push(msg);
    }

    expect(received).toEqual(mockMessages);
    expect((sdk as any).stream.conversational_analytics_chat).toHaveBeenCalled();
  });

  it('should handle partial JSON chunks in stream', async () => {
    const mockMsg = { systemMessage: { text: { parts: ['Complete'] } } };
    const jsonStr = JSON.stringify(mockMsg) + '\n';
    const part1 = jsonStr.substring(0, 10);
    const part2 = jsonStr.substring(10);

    const sdk = getLookerSDK();
    (sdk as any).stream.conversational_analytics_chat.mockImplementation((callback: any) => {
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(part1));
          controller.enqueue(new TextEncoder().encode(part2));
          controller.close();
        }
      });
      callback({ body: stream } as any);
    });

    const received: any[] = [];
    for await (const msg of sendLookerChatMessageStreaming(mockConversationId, mockUserMessage)) {
      received.push(msg);
    }

    expect(received).toEqual([mockMsg]);
  });
});
