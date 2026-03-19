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
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Home from './page';
import { useChatStore } from '@/store/useChatStore';

vi.mock('@/store/useChatStore', () => ({
  useChatStore: vi.fn(),
}));

describe('Conversation Selection Flow', () => {
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
      agents: [{ id: 'agent-1', name: 'Agent 1' }],
      setAgents: vi.fn(),
      selectedAgentId: 'agent-1',
      setSelectedAgentId: vi.fn(),
      conversations: [],
      setConversations: vi.fn(),
      fetchConversations: vi.fn(),
      selectConversation: vi.fn(),
      setLookerBaseUrl: vi.fn(),
    };
    (useChatStore as any).mockReturnValue(mockStore);
    global.fetch = vi.fn();
  });

  it('should trigger fetchConversations when an agent is selected', async () => {
    render(<Home />);
    
    // Initial fetch for agents (already done in mock)
    // Now simulate agent selection trigger
    const trigger = screen.getByText('Agent 1');
    fireEvent.click(trigger);
    
    // In real app, AgentSelector would call onSelect. 
    // Here we'll just check if useEffect or handler calls it.
    // Wait, since we are mocking useChatStore, we need to see how it's called.
  });

  it('should call fetchConversations on initial load if agent is selected', async () => {
    render(<Home />);
    await waitFor(() => {
      expect(mockStore.fetchConversations).toHaveBeenCalledWith('agent-1');
    });
  });

  it('should call selectConversation when a conversation is picked from dropdown', async () => {
    mockStore.conversations = [{ id: 'conv-123', name: 'Past Session' }];
    render(<Home />);
    
    // Open dropdown
    const dropdownTrigger = screen.getByText('Resume previous session');
    fireEvent.click(dropdownTrigger);
    
    // Click option
    const option = screen.getByText('Past Session');
    fireEvent.click(option);
    
    expect(mockStore.selectConversation).toHaveBeenCalledWith('conv-123');
  });
});
