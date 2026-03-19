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
import { Conversation } from '@/store/useChatStore';

interface ConversationSelectorProps {
  conversations: Conversation[];
  selectedConversationId: string | null;
  onSelect: (id: string) => void;
  isLoading?: boolean;
  isDisabled?: boolean;
}

export const ConversationSelector: React.FC<ConversationSelectorProps> = ({
  conversations,
  selectedConversationId,
  onSelect,
  isLoading = false,
  isDisabled = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedConversation = conversations.find((c) => c.id === selectedConversationId);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (id: string) => {
    onSelect(id);
    setIsOpen(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 text-zinc-500 text-xs font-mono uppercase tracking-widest animate-pulse p-2 border border-zinc-800 rounded-md bg-zinc-900/50">
        <span className="w-2 h-2 bg-zinc-600 rounded-full"></span>
        <span>Loading sessions...</span>
      </div>
    );
  }

  const label = isDisabled 
    ? 'Select session' 
    : (selectedConversation ? selectedConversation.name : (conversations.length > 0 ? 'Resume previous session' : 'No previous sessions'));

  return (
    <div className="relative w-full" ref={dropdownRef}>
      <button
        type="button"
        disabled={isDisabled || conversations.length === 0}
        className={`w-full flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-md p-2.5 text-sm text-left transition-colors focus:outline-none focus:ring-1 focus:ring-cyan-500 ${
          isDisabled || conversations.length === 0 ? 'opacity-50 cursor-not-allowed' : 'hover:border-zinc-700'
        }`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className={selectedConversation ? 'text-cyan-400' : 'text-zinc-500'}>
          {label}
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

      {isOpen && conversations.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-zinc-900 border border-zinc-800 rounded-md shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-100">
          <div className="max-h-60 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                className={`w-full text-left px-3 py-2 text-sm hover:bg-zinc-800 transition-colors ${
                  conv.id === selectedConversationId ? 'text-cyan-400 bg-zinc-800/50' : 'text-zinc-300'
                }`}
                onClick={() => handleSelect(conv.id)}
              >
                <div className="truncate font-medium">{conv.name}</div>
                {conv.created_at && (
                  <div className="text-[10px] text-zinc-600 font-mono">
                    {new Date(conv.created_at).toLocaleDateString()}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
