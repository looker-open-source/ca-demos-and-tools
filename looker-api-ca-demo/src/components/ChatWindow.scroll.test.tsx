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

import { render, fireEvent } from "@testing-library/react";
import { ChatWindow } from "@/components/ChatWindow";
import { vi, describe, it, expect } from "vitest";

describe("ChatWindow Auto-scroll", () => {
  it("should scroll to bottom when new messages are added IF already at bottom", () => {
    const initialMessages = [{ type: "user", text: "Hello" }];
    const { rerender, container } = render(<ChatWindow messages={initialMessages} />);

    const scrollContainer = container.querySelector(".flex-1.overflow-y-auto");
    if (!scrollContainer) throw new Error("Scroll container not found");
    
    // Simulate being at bottom
    Object.defineProperty(scrollContainer, 'scrollHeight', { configurable: true, value: 1000 });
    Object.defineProperty(scrollContainer, 'clientHeight', { configurable: true, value: 500 });
    Object.defineProperty(scrollContainer, 'scrollTop', { configurable: true, value: 500 });
    
    fireEvent.scroll(scrollContainer);

    const scrollToMock = vi.mocked(Element.prototype.scrollTo);
    scrollToMock.mockClear();

    const newMessages = [...initialMessages, { type: "system", text: "Hi there!" }];
    rerender(<ChatWindow messages={newMessages} />);

    expect(scrollToMock).toHaveBeenCalled();
  });

  it("should NOT scroll to bottom when new messages are added IF NOT at bottom", () => {
    const initialMessages = [{ type: "user", text: "Hello" }];
    const { rerender, container } = render(<ChatWindow messages={initialMessages} />);

    const scrollContainer = container.querySelector(".flex-1.overflow-y-auto");
    if (!scrollContainer) throw new Error("Scroll container not found");
    
    // Simulate being NOT at bottom
    Object.defineProperty(scrollContainer, 'scrollHeight', { configurable: true, value: 1000 });
    Object.defineProperty(scrollContainer, 'clientHeight', { configurable: true, value: 500 });
    Object.defineProperty(scrollContainer, 'scrollTop', { configurable: true, value: 100 });
    
    fireEvent.scroll(scrollContainer);

    const scrollToMock = vi.mocked(Element.prototype.scrollTo);
    scrollToMock.mockClear();

    const newMessages = [...initialMessages, { type: "system", text: "Hi there!" }];
    rerender(<ChatWindow messages={newMessages} />);

    expect(scrollToMock).not.toHaveBeenCalled();
  });

  it("should ALWAYS scroll to bottom when user sends a message", () => {
    const initialMessages = [{ type: "user", text: "Hello" }];
    const { rerender, container } = render(<ChatWindow messages={initialMessages} />);

    const scrollContainer = container.querySelector(".flex-1.overflow-y-auto");
    if (!scrollContainer) throw new Error("Scroll container not found");
    
    // Simulate being NOT at bottom
    Object.defineProperty(scrollContainer, 'scrollHeight', { configurable: true, value: 1000 });
    Object.defineProperty(scrollContainer, 'clientHeight', { configurable: true, value: 500 });
    Object.defineProperty(scrollContainer, 'scrollTop', { configurable: true, value: 100 });
    
    fireEvent.scroll(scrollContainer);

    const scrollToMock = vi.mocked(Element.prototype.scrollTo);
    scrollToMock.mockClear();

    // Add a NEW USER message
    const newMessages = [...initialMessages, { type: "user", text: "New user prompt" }];
    rerender(<ChatWindow messages={newMessages} />);

    expect(scrollToMock).toHaveBeenCalled();
  });
});
