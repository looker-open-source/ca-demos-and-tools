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

import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatWindow } from './ChatWindow';

describe('ChatWindow - Thought Messages', () => {
  it('should render thoughts as individual blocks within a turn-based group', () => {
    const messages = [
      { type: 'user', text: 'Turn 1 start' },
      { type: 'system', text: 'Thought 1', isThought: true },
      { type: 'system', text: 'Thought 2', isThought: true },
      { type: 'system', text: 'Final Answer' },
    ];
    render(<ChatWindow messages={messages} />);
    
    // Thoughts should be visible by default (isOpen: true)
    expect(screen.getByText('Thought 1')).toBeInTheDocument();
    expect(screen.getByText('Thought 2')).toBeInTheDocument();
    
    // They should be in separate blocks (divs)
    const thoughtBlocks = screen.getAllByText(/Thought [12]/);
    expect(thoughtBlocks).toHaveLength(2);

    // Collapsed state should NOT show any thought text
    const hideButton = screen.getByRole('button', { name: /Hide Reasoning/i });
    fireEvent.click(hideButton);
    
    expect(screen.queryByText('Thought 1')).not.toBeInTheDocument();
    expect(screen.queryByText('Thought 2')).not.toBeInTheDocument();
    
    // Button should now show count
    expect(screen.getByRole('button', { name: /Show Reasoning \(2\)/i })).toBeInTheDocument();
  });
});
