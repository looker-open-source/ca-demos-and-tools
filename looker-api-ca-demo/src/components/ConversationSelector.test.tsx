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

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ConversationSelector } from './ConversationSelector';

describe('ConversationSelector', () => {
  const mockConversations = [
    { id: '1', name: 'Conv 1' },
    { id: '2', name: 'Conv 2' },
  ];

  it('should render "No previous sessions" when empty and enabled', () => {
    render(
      <ConversationSelector
        conversations={[]}
        selectedConversationId={null}
        onSelect={vi.fn()}
        isDisabled={false}
      />
    );
    expect(screen.getByText('No previous sessions')).toBeDefined();
  });

  it('should render "Select session" when disabled', () => {
    render(
      <ConversationSelector
        conversations={mockConversations}
        selectedConversationId={null}
        onSelect={vi.fn()}
        isDisabled={true}
      />
    );
    expect(screen.getByText('Select session')).toBeDefined();
  });

  it('should display the selected conversation name', () => {
    render(
      <ConversationSelector
        conversations={mockConversations}
        selectedConversationId="1"
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText('Conv 1')).toBeDefined();
  });

  it('should call onSelect when a conversation is clicked', () => {
    const onSelect = vi.fn();
    render(
      <ConversationSelector
        conversations={mockConversations}
        selectedConversationId={null}
        onSelect={onSelect}
      />
    );

    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByText('Conv 2'));

    expect(onSelect).toHaveBeenCalledWith('2');
  });
});
