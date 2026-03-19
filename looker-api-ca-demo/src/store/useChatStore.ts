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

import { create } from 'zustand';
import { parseLookerMessage } from '@/lib/message-utils';
import { logRequest as fetch } from '@/lib/dev-logger/interceptor';

interface Message {
  type: 'user' | 'system';
  text: string;
  payload?: any;
  isThought?: boolean;
  parts?: string[];
}

export interface Agent {
  id: string;
  name: string;
  description?: string;
  created_by_name?: string;
  created_at?: string;
  updated_at?: string;
  sources?: { model: string; explore: string }[];
  context?: { instructions: string };
  code_interpreter?: boolean;
  studio_agent_id?: string | null;
}

export interface Conversation {
  id: string;
  name: string;
  agent_id?: string;
  created_at?: string;
}

interface ChatState {
  messages: Message[];
  conversationId: string | null;
  currentConversationName: string | null;
  isLoading: boolean;
  error: string | null;
  agents: Agent[];
  selectedAgentId: string | null;
  conversations: Conversation[];
  lookerBaseUrl: string | null;
  
  // Actions
  addMessage: (message: Message) => void;
  setConversationId: (id: string | null) => void;
  setCurrentConversationName: (name: string | null) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  clearMessages: () => void;
  setAgents: (agents: Agent[]) => void;
  setSelectedAgentId: (id: string | null) => void;
  setConversations: (conversations: Conversation[]) => void;
  setLookerBaseUrl: (url: string | null) => void;
  resetTitle: () => void;
  
  // Async Actions
  fetchConversations: (agentId: string) => Promise<void>;
  selectConversation: (conversationId: string) => Promise<void>;
  deleteConversation: (conversationId: string) => Promise<void>;
  updateConversationName: (conversationId: string, name: string) => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  conversationId: null,
  currentConversationName: null,
  isLoading: false,
  error: null,
  agents: [],
  selectedAgentId: null,
  conversations: [],
  lookerBaseUrl: null,

  addMessage: (message) => 
    set((state) => ({ messages: [...state.messages, message] })),

  setConversationId: (id) => 
    set({ conversationId: id }),

  setCurrentConversationName: (name) =>
    set({ currentConversationName: name }),

  setLoading: (isLoading) => 
    set({ isLoading }),

  setError: (error) => 
    set({ error }),

  clearMessages: () => 
    set({ messages: [] }),

  setAgents: (agents) =>
    set({ agents }),

  setSelectedAgentId: (id) =>
    set({ selectedAgentId: id }),

  setConversations: (conversations) =>
    set({ conversations }),

  setLookerBaseUrl: (url) =>
    set({ lookerBaseUrl: url }),

  resetTitle: () =>
    set({ currentConversationName: null }),

  fetchConversations: async (agentId) => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch(`/api/conversations/search?agent_id=${agentId}`);
      if (!response.ok) throw new Error('Failed to fetch conversations');
      const conversations: Conversation[] = await response.json();
      
      // Sort by updated_at desc (if available) or created_at desc
      const sortedConversations = [...conversations].sort((a, b) => {
        const dateA = new Date(a.created_at || 0).getTime();
        const dateB = new Date(b.created_at || 0).getTime();
        return dateB - dateA;
      });

      set({ conversations: sortedConversations });
    } catch (err: any) {
      set({ error: err.message });
    } finally {
      set({ isLoading: false });
    }
  },

  selectConversation: async (conversationId) => {
    set({ isLoading: true, error: null, messages: [] });
    try {
      const { lookerBaseUrl } = get();
      // 1. Fetch conversation details (to get name)
      const convResponse = await fetch(`/api/conversations/${conversationId}`);
      if (!convResponse.ok) throw new Error('Failed to fetch conversation details');
      const conversation = await convResponse.json();
      
      // 2. Fetch conversation messages
      const msgResponse = await fetch(`/api/conversations/${conversationId}/messages`);
      if (!msgResponse.ok) throw new Error('Failed to fetch conversation messages');
      const lookerMessages = await msgResponse.json();
      
      // 3. Map Looker messages to store Message format
      const messages: Message[] = lookerMessages.map((lm: any) => 
        parseLookerMessage(lm, lookerBaseUrl || undefined)
      );

      set({ 
        conversationId, 
        currentConversationName: conversation.name,
        messages 
      });
    } catch (err: any) {
      set({ error: err.message });
    } finally {
      set({ isLoading: false });
    }
  },

  deleteConversation: async (conversationId) => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch(`/api/conversations/${conversationId}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete conversation');
      
      set((state) => ({
        conversations: state.conversations.filter((c) => c.id !== conversationId),
        conversationId: state.conversationId === conversationId ? null : state.conversationId,
        currentConversationName: state.conversationId === conversationId ? null : state.currentConversationName,
        messages: state.conversationId === conversationId ? [] : state.messages,
      }));
    } catch (err: any) {
      set({ error: err.message });
    } finally {
      set({ isLoading: false });
    }
  },

  updateConversationName: async (conversationId, name) => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch(`/api/conversations/${conversationId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (!response.ok) throw new Error('Failed to update conversation name');
      const updatedConversation = await response.json();
      
      set((state) => ({
        conversations: state.conversations.map((c) => 
          c.id === conversationId ? { ...c, name: updatedConversation.name } : c
        ),
        currentConversationName: state.conversationId === conversationId ? updatedConversation.name : state.currentConversationName,
      }));
    } catch (err: any) {
      set({ error: err.message });
    } finally {
      set({ isLoading: false });
    }
  },
}));
