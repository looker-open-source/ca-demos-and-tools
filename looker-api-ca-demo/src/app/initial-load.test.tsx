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
import { render, screen, waitFor } from '@testing-library/react';
import Home from './page';
import { useChatStore } from '@/store/useChatStore';

vi.mock('@/store/useChatStore', () => ({
  useChatStore: vi.fn(),
}));

describe('Home Page - Initial Load Disabling', () => {
  let mockStore: any;

  beforeEach(() => {
    mockStore = {
      messages: [],
      addMessage: vi.fn(),
      isLoading: false,
      setLoading: vi.fn(),
      conversationId: null,
      setConversationId: vi.fn(),
      error: null,
      setError: vi.fn(),
      clearMessages: vi.fn(),
      agents: [],
      setAgents: vi.fn(),
      selectedAgentId: null,
      setSelectedAgentId: vi.fn(),
      conversations: [],
      fetchConversations: vi.fn(),
      selectConversation: vi.fn(),
      setLookerBaseUrl: vi.fn(),
    };
    (useChatStore as any).mockReturnValue(mockStore);
    global.fetch = vi.fn();
  });

  it('should disable message input while agents are initially loading', async () => {
    // Mock fetch to be stuck in pending state for agents
    let resolveAgents: any;
    const agentsPromise = new Promise((resolve) => {
      resolveAgents = resolve;
    });
    
    (global.fetch as any).mockImplementation((url: string) => {
      if (url === '/api/agents') return agentsPromise;
      return Promise.resolve({ ok: true, json: async () => [] });
    });

    render(<Home />);

    // Input should be disabled
    const input = screen.getByPlaceholderText(/Ask a question/i);
    expect(input).toBeDisabled();

    // After agents load, input should be enabled (if there are agents)
    resolveAgents({
      ok: true,
      json: async () => ({
        agents: [{ id: 'agent-1', name: 'Agent 1' }],
        defaultAgentId: null,
        lookerBaseUrl: null
      })
    });

    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });
  });
});
