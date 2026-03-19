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
import { useChatStore, Conversation } from './useChatStore';

describe('useChatStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useChatStore.setState({
      messages: [],
      conversationId: null,
      currentConversationName: null,
      isLoading: false,
      error: null,
      agents: [],
      selectedAgentId: null,
      conversations: [],
    });
  });

  it('should initialize with default state', () => {
    const state = useChatStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.conversationId).toBeNull();
    expect(state.isLoading).toBeFalsy();
    expect(state.error).toBeNull();
    expect(state.conversations).toEqual([]);
    expect(state.currentConversationName).toBeNull();
  });

  it('should set conversations', () => {
    const { setConversations } = useChatStore.getState();
    const conversations: Conversation[] = [{ id: 'conv-1', name: 'Conversation 1' }];
    setConversations(conversations);
    
    expect(useChatStore.getState().conversations).toEqual(conversations);
  });

  it('should set current conversation name', () => {
    const { setCurrentConversationName } = useChatStore.getState();
    setCurrentConversationName('New Name');
    
    expect(useChatStore.getState().currentConversationName).toBe('New Name');
  });

  it('should add a message', () => {
    const { addMessage } = useChatStore.getState();
    addMessage({ type: 'user', text: 'Hello' });
    
    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useChatStore.getState().messages[0]).toEqual({ type: 'user', text: 'Hello' });
  });

  it('should set conversation ID', () => {
    const { setConversationId } = useChatStore.getState();
    setConversationId('test-id');
    
    expect(useChatStore.getState().conversationId).toBe('test-id');
  });

  it('should set loading state', () => {
    const { setLoading } = useChatStore.getState();
    setLoading(true);
    
    expect(useChatStore.getState().isLoading).toBeTruthy();
  });

  it('should set error message', () => {
    const { setError } = useChatStore.getState();
    setError('Something went wrong');
    
    expect(useChatStore.getState().error).toBe('Something went wrong');
  });

  it('should clear messages', () => {
    const { addMessage, clearMessages } = useChatStore.getState();
    addMessage({ type: 'user', text: 'Hello' });
    clearMessages();
    
    expect(useChatStore.getState().messages).toHaveLength(0);
  });

  it('should set agents and selected agent ID', () => {
    const { setAgents, setSelectedAgentId } = useChatStore.getState();
    const agents = [{ id: '1', name: 'Agent 1' }];
    setAgents(agents);
    setSelectedAgentId('1');
    
    expect(useChatStore.getState().agents).toEqual(agents);
    expect(useChatStore.getState().selectedAgentId).toBe('1');
  });

  it('should set agents with metadata', () => {
    const { setAgents } = useChatStore.getState();
    const agents = [{ 
      id: '1', 
      name: 'Agent 1',
      description: 'Test agent',
      created_by_name: 'David',
      created_at: '2025-09-09',
      updated_at: '2025-09-10',
      sources: [{ model: 'm1', explore: 'e1' }],
      context: { instructions: 'instr' },
      code_interpreter: true,
      studio_agent_id: 'studio-1'
    }];
    setAgents(agents);
    
    expect(useChatStore.getState().agents).toEqual(agents);
  });

  describe('async actions', () => {
    beforeEach(() => {
      global.fetch = vi.fn();
    });

    it('should fetch conversations', async () => {
      const mockConversations = [{ id: 'conv-1', name: 'Conv 1' }];
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => mockConversations,
      });

      await useChatStore.getState().fetchConversations('agent-1');

      expect(useChatStore.getState().conversations).toEqual(mockConversations);
      expect(global.fetch).toHaveBeenCalledWith('/api/conversations/search?agent_id=agent-1');
    });

    it('should select a conversation and load messages', async () => {
      const mockConversation = { id: 'conv-1', name: 'Conv 1' };
      const mockMessages = [{ type: 'user', message: { userMessage: { text: 'hi' } } }];
      
      (global.fetch as any).mockImplementation((url: string) => {
        if (url.endsWith('/messages')) {
          return Promise.resolve({ ok: true, json: async () => mockMessages });
        }
        return Promise.resolve({ ok: true, json: async () => mockConversation });
      });

      await useChatStore.getState().selectConversation('conv-1');

      const state = useChatStore.getState();
      expect(state.conversationId).toBe('conv-1');
      expect(state.currentConversationName).toBe('Conv 1');
      expect(state.messages).toHaveLength(1);
      expect(state.messages[0]).toEqual({ 
        type: 'user', 
        text: 'hi', 
        payload: null,
        isThought: false,
        parts: [],
      });
    });

    it('should update conversation name', async () => {
      const updatedConversation = { id: 'conv-1', name: 'Updated' };
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => updatedConversation,
      });

      useChatStore.setState({ conversationId: 'conv-1' });

      await useChatStore.getState().updateConversationName('conv-1', 'Updated');

      expect(useChatStore.getState().currentConversationName).toBe('Updated');
      expect(global.fetch).toHaveBeenCalledWith('/api/conversations/conv-1', expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ name: 'Updated' }),
      }));
    });

    it('should delete a conversation', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      });

      useChatStore.setState({ conversationId: 'conv-1', conversations: [{ id: 'conv-1', name: 'C1' }] });

      await useChatStore.getState().deleteConversation('conv-1');

      const state = useChatStore.getState();
      expect(state.conversationId).toBeNull();
      expect(state.conversations).toHaveLength(0);
      expect(global.fetch).toHaveBeenCalledWith('/api/conversations/conv-1', expect.objectContaining({
        method: 'DELETE',
      }));
    });
  });
});
