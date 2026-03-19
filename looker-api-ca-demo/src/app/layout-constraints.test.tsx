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

import { render, screen } from "@testing-library/react";
import Home from "./page";
import { useChatStore } from "@/store/useChatStore";
import { vi, describe, it, expect, beforeEach } from "vitest";

// Mock the components used in Home
vi.mock("@/components/ChatWindow", () => ({
  ChatWindow: () => <div data-testid="chat-window">ChatWindow</div>,
}));
vi.mock("@/components/DataVisualization", () => ({
  DataVisualization: () => <div data-testid="data-visualization">DataVisualization</div>,
}));
vi.mock("@/components/AgentSelector", () => ({
  AgentSelector: () => <div data-testid="agent-selector">AgentSelector</div>,
}));

// Mock the chat store
vi.mock("@/store/useChatStore");

describe("Home Layout Constraints", () => {
  beforeEach(() => {
    vi.mocked(useChatStore).mockReturnValue({
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
    } as any);
  });

  it("Chat Window container should have height constraints and scroll", () => {
    render(<Home />);
    
    // The sidebar container for ChatWindow
    const chatSidebar = screen.getByTestId("chat-window").parentElement?.parentElement;
    expect(chatSidebar).toHaveClass("h-[70vh]");
    expect(chatSidebar).toHaveClass("lg:h-full");
    expect(chatSidebar).toHaveClass("min-h-0");
  });

  it("Insight Workspace container should have height constraints and scroll", () => {
    render(<Home />);
    
    const insightWorkspace = screen.getByText(/Insight Workspace/i).parentElement;
    expect(insightWorkspace).toHaveClass("overflow-y-auto");
    expect(insightWorkspace).toHaveClass("flex-1");
  });

  it("Main container should be locked to screen height", () => {
    render(<Home />);
    
    const main = screen.getByRole("main");
    expect(main).toHaveClass("h-screen");
    expect(main).not.toHaveClass("min-h-screen");
  });
});
