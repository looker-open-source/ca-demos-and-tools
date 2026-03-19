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
import { AgentSelector } from './AgentSelector';

describe('AgentSelector Formatting', () => {
  const agentsWithMeta = [
    { 
      id: 'agent-1', 
      name: 'Sales Agent', 
      description: 'Handles sales',
      created_by_name: 'John Doe',
      created_at: '2026-03-10T10:00:00Z',
      updated_at: '2026-03-12T15:30:00Z',
      sources: [
        { model: 'model-1', explore: 'explore-1' },
        { model: 'model-2', explore: 'explore-2' }
      ],
      context: { instructions: 'Be helpful and concise.' },
      code_interpreter: true
    }
  ];

  it('should format timestamps correctly in the tooltip', () => {
    render(<AgentSelector agents={agentsWithMeta} selectedAgentId={null} onSelect={() => {}} />);
    
    fireEvent.click(screen.getByText(/Select Agent/i));
    const agentItem = screen.getByText('Sales Agent');
    fireEvent.mouseEnter(agentItem);
    
    // Check if dates are formatted.
    expect(screen.getByText(/Created: Mar 10, 2026/i)).toBeInTheDocument();
    expect(screen.getByText(/Updated: Mar 12, 2026/i)).toBeInTheDocument();
  });

  it('should list all data sources', () => {
    render(<AgentSelector agents={agentsWithMeta} selectedAgentId={null} onSelect={() => {}} />);
    
    fireEvent.click(screen.getByText(/Select Agent/i));
    fireEvent.mouseEnter(screen.getByText('Sales Agent'));
    
    expect(screen.getByText('model-1')).toBeInTheDocument();
    expect(screen.getByText('explore-1')).toBeInTheDocument();
    expect(screen.getByText('model-2')).toBeInTheDocument();
    expect(screen.getByText('explore-2')).toBeInTheDocument();
  });

  it('should show code interpreter status', () => {
    render(<AgentSelector agents={agentsWithMeta} selectedAgentId={null} onSelect={() => {}} />);
    
    fireEvent.click(screen.getByText(/Select Agent/i));
    fireEvent.mouseEnter(screen.getByText('Sales Agent'));
    
    expect(screen.getByText(/Code Interpreter/i)).toBeInTheDocument();
    expect(screen.getByText(/Enabled/i)).toBeInTheDocument();
  });
});
