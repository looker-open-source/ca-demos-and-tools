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

describe('AgentSelector', () => {
  const mockAgents = [
    { id: 'agent-1', name: 'Sales Agent' },
    { id: 'agent-2', name: 'Marketing Agent' },
  ];

  it('should render the agent selector with available agents', () => {
    render(<AgentSelector agents={mockAgents} selectedAgentId={null} onSelect={() => {}} />);
    
    // Initially it might be a button or a select that shows current selection
    expect(screen.getByText(/Select Agent/i)).toBeInTheDocument();
  });

  it('should show agent names in the dropdown when clicked', () => {
    render(<AgentSelector agents={mockAgents} selectedAgentId={null} onSelect={() => {}} />);
    
    const trigger = screen.getByText(/Select Agent/i);
    fireEvent.click(trigger);
    
    expect(screen.getByText('Sales Agent')).toBeInTheDocument();
    expect(screen.getByText('Marketing Agent')).toBeInTheDocument();
  });

  it('should call onSelect when an agent is selected', () => {
    const onSelect = vi.fn();
    render(<AgentSelector agents={mockAgents} selectedAgentId={null} onSelect={onSelect} />);
    
    fireEvent.click(screen.getByText(/Select Agent/i));
    fireEvent.click(screen.getByText('Sales Agent'));
    
    expect(onSelect).toHaveBeenCalledWith('agent-1');
  });

  it('should display the selected agent name', () => {
    render(<AgentSelector agents={mockAgents} selectedAgentId="agent-2" onSelect={() => {}} />);
    expect(screen.getByText('Marketing Agent')).toBeInTheDocument();
  });

  it('should filter agents based on search input', () => {
    render(<AgentSelector agents={mockAgents} selectedAgentId={null} onSelect={() => {}} />);
    
    fireEvent.click(screen.getByText(/Select Agent/i));
    
    const searchInput = screen.getByPlaceholderText(/Search agents/i);
    fireEvent.change(searchInput, { target: { value: 'Sales' } });
    
    expect(screen.getByText('Sales Agent')).toBeInTheDocument();
    expect(screen.queryByText('Marketing Agent')).not.toBeInTheDocument();
  });

  it('should show loading state', () => {
    render(<AgentSelector agents={[]} selectedAgentId={null} onSelect={() => {}} isLoading={true} />);
    expect(screen.getByText(/Loading agents/i)).toBeInTheDocument();
  });

  it('should show tooltip on agent hover', () => {
    const agentsWithMeta = [
      { id: 'agent-1', name: 'Sales Agent', description: 'Handles sales' }
    ];
    render(<AgentSelector agents={agentsWithMeta} selectedAgentId={null} onSelect={() => {}} />);
    
    fireEvent.click(screen.getByText(/Select Agent/i));
    
    const agentItem = screen.getByText('Sales Agent');
    fireEvent.mouseEnter(agentItem);
    
    expect(screen.getByText('Handles sales')).toBeInTheDocument();
    
    fireEvent.mouseLeave(agentItem);
    expect(screen.queryByText('Handles sales')).not.toBeInTheDocument();
  });
});
