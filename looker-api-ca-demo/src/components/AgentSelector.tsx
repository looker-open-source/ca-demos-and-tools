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

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Agent } from '@/store/useChatStore';
import { Tooltip } from './Tooltip';

interface AgentSelectorProps {
  agents: Agent[];
  selectedAgentId: string | null;
  onSelect: (agentId: string) => void;
  isLoading?: boolean;
}

export const AgentSelector: React.FC<AgentSelectorProps> = ({
  agents,
  selectedAgentId,
  onSelect,
  isLoading = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [hoveredAgentId, setHoveredAgentId] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedAgent = agents.find((a) => a.id === selectedAgentId);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredAgents = agents.filter((agent) =>
    agent.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSelect = (agentId: string) => {
    onSelect(agentId);
    setIsOpen(false);
    setSearchQuery('');
  };

  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const renderAgentTooltip = (agent: Agent) => (
    <div className="space-y-2">
      <div className="flex justify-between items-start border-b border-zinc-800 pb-1.5 mb-1.5">
        <span className="font-bold text-cyan-400">Agent Metadata</span>
        <span className="text-[10px] text-zinc-500 font-mono">{agent.id.substring(0, 8)}...</span>
      </div>
      
      {agent.description && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-0.5">Description</p>
          <p className="text-zinc-300 leading-relaxed">{agent.description}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 text-[11px]">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-0.5">Created By</p>
          <p className="text-zinc-300">{agent.created_by_name || 'System'}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-0.5">Code Interpreter</p>
          <p className={agent.code_interpreter ? 'text-cyan-400' : 'text-zinc-500'}>
            {agent.code_interpreter ? 'Enabled' : 'Disabled'}
          </p>
        </div>
      </div>

      {agent.sources && agent.sources.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-0.5">Data Sources</p>
          <div className="space-y-1">
            {agent.sources.map((s, i) => (
              <div key={i} className="bg-zinc-900/50 border border-zinc-800 rounded px-1.5 py-1 flex justify-between">
                <span className="text-zinc-400">{s.model}</span>
                <span className="text-cyan-600 mx-1">→</span>
                <span className="text-zinc-300">{s.explore}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {agent.context?.instructions && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold mb-0.5">Context</p>
          <p className="text-zinc-400 italic line-clamp-3 leading-snug">"{agent.context.instructions}"</p>
        </div>
      )}

      <div className="flex justify-between items-center pt-1.5 border-t border-zinc-800 text-[9px] text-zinc-600 font-mono">
        <span>Created: {formatDate(agent.created_at)}</span>
        <span>Updated: {formatDate(agent.updated_at)}</span>
      </div>
    </div>
  );

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 text-zinc-500 text-xs font-mono uppercase tracking-widest animate-pulse p-2 border border-zinc-800 rounded-md bg-zinc-900/50">
        <span className="w-2 h-2 bg-zinc-600 rounded-full"></span>
        <span>Loading agents...</span>
      </div>
    );
  }

  return (
    <div className="relative w-full" ref={dropdownRef}>
      <button
        type="button"
        className="w-full flex items-center justify-between bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-md p-2.5 text-sm text-left transition-colors focus:outline-none focus:ring-1 focus:ring-cyan-500"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className={selectedAgent ? 'text-zinc-100' : 'text-zinc-500'}>
          {selectedAgent ? selectedAgent.name : 'Select Agent'}
        </span>
        <svg
          className={`w-4 h-4 text-zinc-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-zinc-900 border border-zinc-800 rounded-md shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-100">
          <div className="p-2 border-b border-zinc-800">
            <input
              type="text"
              className="w-full bg-zinc-950 border border-zinc-800 rounded p-1.5 text-xs focus:outline-none focus:border-cyan-500 text-zinc-200 placeholder-zinc-600"
              placeholder="Search agents..."
              autoFocus
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="max-h-60 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800">
            {filteredAgents.length > 0 ? (
              filteredAgents.map((agent) => (
                <Tooltip
                  key={agent.id}
                  isVisible={hoveredAgentId === agent.id}
                  content={renderAgentTooltip(agent)}
                >
                  <button
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-zinc-800 transition-colors ${
                      agent.id === selectedAgentId ? 'text-cyan-400 bg-zinc-800/50' : 'text-zinc-300'
                    }`}
                    onClick={() => handleSelect(agent.id)}
                    onMouseEnter={() => setHoveredAgentId(agent.id)}
                    onMouseLeave={() => setHoveredAgentId(null)}
                  >
                    {agent.name}
                  </button>
                </Tooltip>
              ))
            ) : (
              <div className="px-3 py-4 text-center text-xs text-zinc-600">
                No agents found
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
