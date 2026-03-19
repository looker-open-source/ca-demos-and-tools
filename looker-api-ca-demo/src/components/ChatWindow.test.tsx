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

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatWindow } from './ChatWindow';

describe('ChatWindow', () => {
  it('should render the chat title', () => {
    render(<ChatWindow />);
    expect(screen.getByText(/Conversational Analytics/i)).toBeInTheDocument();
  });

  it('should allow typing a message', () => {
    render(<ChatWindow />);
    const input = screen.getByPlaceholderText(/Ask a question/i);
    fireEvent.change(input, { target: { value: 'What is the total revenue?' } });
    expect((input as HTMLInputElement).value).toBe('What is the total revenue?');
  });

  it('should call onSendMessage when the send button is clicked', () => {
    const onSendMessage = vi.fn();
    render(<ChatWindow onSendMessage={onSendMessage} />);
    const input = screen.getByPlaceholderText(/Ask a question/i);
    const button = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Tell me about sales' } });
    fireEvent.click(button);

    expect(onSendMessage).toHaveBeenCalledWith('Tell me about sales');
    expect((input as HTMLInputElement).value).toBe('');
  });

  it('should call onSendMessage when Enter key is pressed', () => {
    const onSendMessage = vi.fn();
    render(<ChatWindow onSendMessage={onSendMessage} />);
    const input = screen.getByPlaceholderText(/Ask a question/i);

    fireEvent.change(input, { target: { value: 'Revenue by month' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', charCode: 13 });

    expect(onSendMessage).toHaveBeenCalledWith('Revenue by month');
  });

  it('should render messages when provided', () => {
    const messages = [
      { type: 'user', text: 'Hello' },
      { type: 'system', text: 'Hi there!' },
    ];
    render(<ChatWindow messages={messages} />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('Hi there!')).toBeInTheDocument();
  });

  it('should show placeholder when no messages are provided', () => {
    render(<ChatWindow messages={[]} />);
    expect(screen.getByText(/Ask a question about your data to get started/i)).toBeInTheDocument();
  });

  it('should apply overflow-x-auto class to message containers to handle long words', () => {
    const messages = [{ type: 'user', text: 'https://gcplmaster.dev.looker.com/explore/airports/airport_locations_with_a_very_long_url_that_should_not_break_the_layout' }];
    render(<ChatWindow messages={messages} />);
    const messageContainer = screen.getByText(/https:\/\/gcplmaster/);
    expect(messageContainer.className).toContain('overflow-x-auto');
  });

  it('should render Stop button when isStreaming is true and call onStop when clicked', () => {
    const onStop = vi.fn();
    render(<ChatWindow isStreaming={true} onStop={onStop} />);
    
    const stopButton = screen.getByRole('button', { name: /stop/i });
    expect(stopButton).toBeInTheDocument();
    
    fireEvent.click(stopButton);
    expect(onStop).toHaveBeenCalled();
  });

  it('should disable input and send button when isLoading is true', () => {
    render(<ChatWindow isLoading={true} />);
    
    const input = screen.getByPlaceholderText(/Ask a question/i);
    const sendButton = screen.getByRole('button', { name: /send/i });
    
    expect(input).toBeDisabled();
    expect(sendButton).toBeDisabled();
    expect(screen.queryByRole('button', { name: /stop/i })).not.toBeInTheDocument();
  });
});
