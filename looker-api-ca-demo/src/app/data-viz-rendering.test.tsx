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
import { render, screen } from '@testing-library/react';
import Home from './page';
import { useChatStore } from '@/store/useChatStore';

vi.mock('@/store/useChatStore', () => ({
  useChatStore: vi.fn(),
}));

vi.mock("@/components/DataVisualization", () => ({
  DataVisualization: () => <div data-testid="data-visualization">DataVisualization</div>,
}));

// Mock other components that might interfere or are not needed for this test
vi.mock("@/components/ChatWindow", () => ({
  ChatWindow: () => <div data-testid="chat-window">ChatWindow</div>,
}));
vi.mock("@/components/AgentSelector", () => ({
  AgentSelector: () => <div data-testid="agent-selector">AgentSelector</div>,
}));
vi.mock("@/components/LoadingOverlay", () => ({
  __esModule: true,
  default: () => <div data-testid="loading-overlay">LoadingOverlay</div>,
}));

describe('DataVisualization Rendering in Home Page', () => {
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
  });

  it('should NOT render DataVisualization when payload has no data and is not a chart', () => {
    mockStore.messages = [
      {
        type: 'system',
        text: 'Query received',
        payload: {
          data: null,
          query: { model: 'test' },
          exploreUrl: 'http://test'
        }
      }
    ];

    render(<Home />);
    expect(screen.queryByTestId('data-visualization')).not.toBeInTheDocument();
  });

  it('should render DataVisualization when payload has data', () => {
    mockStore.messages = [
      {
        type: 'system',
        text: 'Data result',
        payload: {
          data: [{ a: 1 }],
          query: { model: 'test' },
          exploreUrl: 'http://test'
        }
      }
    ];

    render(<Home />);
    expect(screen.getByTestId('data-visualization')).toBeInTheDocument();
  });

  it('should render DataVisualization when it is a chart', () => {
    mockStore.messages = [
      {
        type: 'system',
        text: 'Chart result',
        payload: {
          vegaConfig: { mark: 'bar' },
          isChart: true
        }
      }
    ];

    render(<Home />);
    expect(screen.getByTestId('data-visualization')).toBeInTheDocument();
  });
});
