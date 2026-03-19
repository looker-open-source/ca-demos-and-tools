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

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Home from './page';
import { useChatStore } from '@/store/useChatStore';
import { useLookerAuth } from '@/components/LookerAuthProvider';
import { useRouter } from 'next/navigation';

vi.mock('@/store/useChatStore', () => ({
  useChatStore: vi.fn(),
}));

vi.mock('@/components/LookerAuthProvider', () => ({
  useLookerAuth: vi.fn(),
  LookerAuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
}));

describe('Home Page', () => {
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
      resetTitle: vi.fn(),
    };
    (useChatStore as any).mockReturnValue(mockStore);
    (useLookerAuth as any).mockReturnValue({
      isAuthenticated: true,
      logout: vi.fn(),
      checkAuth: vi.fn(),
      isInitialized: true,
    });
    (useRouter as any).mockReturnValue({
      push: vi.fn(),
    });
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ agents: [], defaultAgentId: null, lookerBaseUrl: null })
    });
    
    // Polyfill AbortController for tests if needed, but Vitest should have it
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_DEFAULT_AGENT_ID;
  });

  it('should abort the fetch request when stop button is clicked', async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, 'abort');

    // First, agents load successfully
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ agents: [{ id: 'agent-1', name: 'Agent 1' }], defaultAgentId: null, lookerBaseUrl: null })
    });
    
    // Then, chat starts and hangs
    (global.fetch as any).mockImplementationOnce(() => new Promise(() => {}));
    
    const { rerender } = render(<Home />);
    
    const input = screen.getByPlaceholderText(/Ask a question/i);
    
    // Wait for agents to load (input becomes enabled)
    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });

    const sendButton = screen.getByRole('button', { name: /send/i });
    
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);

    mockStore.isLoading = true;
    mockStore.addMessage.mockClear();

    rerender(<Home />);

    const stopButton = screen.getByRole('button', { name: /stop/i });
    fireEvent.click(stopButton);

    expect(abortSpy).toHaveBeenCalled();
  });

  it('should use default agent ID from .env if available even if not first', async () => {
    process.env.NEXT_PUBLIC_DEFAULT_AGENT_ID = 'default-agent-123';
    
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        agents: [
          { id: 'other-agent', name: 'Other Agent' },
          { id: 'default-agent-123', name: 'Default Agent' }
        ],
        defaultAgentId: null,
        lookerBaseUrl: null
      })
    });

    render(<Home />);

    await waitFor(() => {
      expect(mockStore.setSelectedAgentId).toHaveBeenCalledWith('default-agent-123');
    });
  });

  it('should clear conversation state with confirmation when agent is changed', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm');
    confirmSpy.mockReturnValue(true);

    const mockAgents = [
      { id: 'agent-1', name: 'Agent 1' },
      { id: 'agent-2', name: 'Agent 2' }
    ];

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        agents: mockAgents,
        defaultAgentId: null,
        lookerBaseUrl: null
      })
    });

    mockStore.messages = [{ type: 'user', text: 'Existing message' }];
    mockStore.conversationId = 'existing-conv';
    mockStore.agents = mockAgents;
    mockStore.selectedAgentId = 'agent-1';

    render(<Home />);

    // Wait for agents to load and component to render
    await waitFor(() => {
      expect(screen.getByText('Agent 1')).toBeInTheDocument();
    });

    // Trigger agent change
    const trigger = screen.getByText('Agent 1');
    fireEvent.click(trigger);
    const agent2Option = screen.getByText('Agent 2');
    fireEvent.click(agent2Option);

    expect(confirmSpy).toHaveBeenCalled();
    expect(mockStore.clearMessages).toHaveBeenCalled();
    expect(mockStore.setConversationId).toHaveBeenCalledWith(null);
    expect(mockStore.setError).toHaveBeenCalledWith(null);
    expect(mockStore.setSelectedAgentId).toHaveBeenCalledWith('agent-2');
  });

  it('should abort active fetch request when agent is changed', async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, 'abort');
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    const mockAgents = [{ id: 'agent-1', name: 'Agent 1' }, { id: 'agent-2', name: 'Agent 2' }];
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        agents: mockAgents,
        defaultAgentId: null,
        lookerBaseUrl: null
      })
    });

    mockStore.agents = mockAgents;
    mockStore.selectedAgentId = 'agent-1';
    mockStore.messages = [{ type: 'user', text: 'Stuck request' }];

    const { rerender } = render(<Home />);

    // Trigger a message to set up the abort controller
    const input = screen.getByPlaceholderText(/Ask a question/i);
    // Wait for agents to load (input becomes enabled)
    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });
    
    const sendButton = screen.getByRole('button', { name: /send/i });
    
    // Mock the chat fetch to hang
    (global.fetch as any).mockImplementationOnce(() => new Promise(() => {}));
    
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);

    // Now change agent
    const trigger = screen.getByText('Agent 1');
    fireEvent.click(trigger);
    const agent2Option = screen.getByText('Agent 2');
    fireEvent.click(agent2Option);

    expect(abortSpy).toHaveBeenCalled();
    // Verify it was a silent abort (no "cancelled" message added)
    expect(mockStore.addMessage).not.toHaveBeenCalledWith(expect.objectContaining({
        text: "The query was cancelled"
    }));
  });

  it('should parse Vega chart messages correctly', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ agents: [{ id: 'agent-1', name: 'Agent 1' }], defaultAgentId: null, lookerBaseUrl: null })
    });

    const vegaMsg = {
      type: 'message',
      data: {
        systemMessage: {
          chart: {
            result: {
              vegaConfig: { mark: 'bar' }
            }
          }
        }
      }
    };

    (global.fetch as any).mockImplementationOnce(() => Promise.resolve({
      ok: true,
      body: {
        getReader: () => {
          let sent = false;
          return {
            read: async () => {
              if (!sent) {
                sent = true;
                return { done: false, value: new TextEncoder().encode(JSON.stringify(vegaMsg) + '\n') };
              }
              return { done: true };
            }
          };
        }
      }
    }));

    render(<Home />);

    const input = screen.getByPlaceholderText(/Ask a question/i);
    await waitFor(() => expect(input).not.toBeDisabled());
    
    const sendButton = screen.getByRole('button', { name: /send/i });
    fireEvent.change(input, { target: { value: 'Show me a chart' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(mockStore.addMessage).toHaveBeenCalledWith(expect.objectContaining({
        payload: expect.objectContaining({
          vegaConfig: { mark: 'bar' },
          isChart: true
        })
      }));
    });
  });

  it('should display the current conversation name in the header', () => {
    mockStore.currentConversationName = 'Awesome Chat';
    render(<Home />);
    expect(screen.getByText('Awesome Chat')).toBeInTheDocument();
  });

  it('should enter edit mode when conversation name is clicked', () => {
    mockStore.conversationId = 'conv-1';
    mockStore.currentConversationName = 'Old Name';
    render(<Home />);
    
    const nameDisplay = screen.getByText('Old Name');
    fireEvent.click(nameDisplay);
    
    expect(screen.getByDisplayValue('Old Name')).toBeInTheDocument();
  });

  it('should call updateConversationName when rename is saved', async () => {
    mockStore.conversationId = 'conv-1';
    mockStore.currentConversationName = 'Old Name';
    mockStore.updateConversationName = vi.fn().mockResolvedValue(undefined);
    
    render(<Home />);
    
    const nameDisplay = screen.getByText('Old Name');
    fireEvent.click(nameDisplay);
    
    const input = screen.getByDisplayValue('Old Name');
    fireEvent.change(input, { target: { value: 'New Name' } });
    
    fireEvent.blur(input);
    
    expect(mockStore.updateConversationName).toHaveBeenCalledWith('conv-1', 'New Name');
  });

  it('should call deleteConversation when delete button is clicked and confirmed', async () => {
    mockStore.conversationId = 'conv-1';
    mockStore.currentConversationName = 'Some Session';
    mockStore.deleteConversation = vi.fn().mockResolvedValue(undefined);
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    
    render(<Home />);
    
    const deleteButton = screen.getByLabelText(/delete session/i);
    fireEvent.click(deleteButton);
    
    expect(confirmSpy).toHaveBeenCalled();
    expect(mockStore.deleteConversation).toHaveBeenCalledWith('conv-1');
  });

  it('should reset title when agent is changed', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const mockAgents = [{ id: 'agent-1', name: 'Agent 1' }, { id: 'agent-2', name: 'Agent 2' }];
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ agents: mockAgents, defaultAgentId: null, lookerBaseUrl: null })
    });
    mockStore.agents = mockAgents;
    mockStore.selectedAgentId = 'agent-1';
    render(<Home />);
    await waitFor(() => expect(screen.getByText('Agent 1')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Agent 1'));
    fireEvent.click(screen.getByText('Agent 2'));

    expect(mockStore.resetTitle).toHaveBeenCalled();
  });

  it('should reset title when new session is clicked', async () => {
    mockStore.conversationId = 'conv-1';
    mockStore.currentConversationName = 'Some Session';
    render(<Home />);

    const newSessionButton = screen.getByRole('button', { name: /new session/i });
    fireEvent.click(newSessionButton);

    expect(mockStore.resetTitle).toHaveBeenCalled();
  });
});
