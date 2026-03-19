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
import { render, waitFor } from '@testing-library/react';
import Home from './page';
import { useChatStore } from '@/store/useChatStore';

vi.mock('@/store/useChatStore', () => ({
  useChatStore: vi.fn(),
}));

describe('Home Page - Agent Caching', () => {
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
      setAgents: (agents: any[]) => {
          mockStore.agents = agents;
      },
      selectedAgentId: null,
      setSelectedAgentId: (id: string) => {
          mockStore.selectedAgentId = id;
      },
      conversations: [],
      fetchConversations: vi.fn(),
      selectConversation: vi.fn(),
      setLookerBaseUrl: vi.fn(),
    };
    (useChatStore as any).mockReturnValue(mockStore);
    global.fetch = vi.fn();
  });

  it('should ONLY fetch agents once, even if selectedAgentId changes', async () => {
    const mockAgents = [{ id: 'agent-1', name: 'Agent 1' }, { id: 'agent-2', name: 'Agent 2' }];
    
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        agents: mockAgents,
        defaultAgentId: null,
        lookerBaseUrl: null
      })
    });

    const { rerender } = render(<Home />);

    // Initial fetch
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/agents');
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Simulate selecting a different agent
    mockStore.selectedAgentId = 'agent-1';
    rerender(<Home />);

    // Should NOT have called fetch again
    expect(global.fetch).toHaveBeenCalledTimes(1);
    
    // Simulate selecting another agent
    mockStore.selectedAgentId = 'agent-2';
    rerender(<Home />);

    // Should still be only 1 call
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
});
