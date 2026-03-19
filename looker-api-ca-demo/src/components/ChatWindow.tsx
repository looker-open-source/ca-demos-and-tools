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

"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface ChatWindowProps {
  onSendMessage?: (message: string) => void;
  messages?: any[];
  isLoading?: boolean;
  isStreaming?: boolean;
  onStop?: () => void;
  conversationName?: string | null;
  onRename?: (name: string) => Promise<void>;
  onDelete?: () => Promise<void>;
}

const ThoughtAccordion: React.FC<{ thoughts: any[] }> = ({ thoughts }) => {
  const [isOpen, setIsOpen] = useState(true); // Open by default

  return (
    <div className="mt-2 mb-4 w-full">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-[10px] uppercase tracking-widest font-bold text-zinc-500 hover:text-cyan-400 flex items-center space-x-1 transition-colors mb-2"
      >
        <span>
          {isOpen ? "Hide Reasoning" : `Show Reasoning (${thoughts.length})`}
        </span>
        <span
          className={`transform transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
        >
          ▼
        </span>
      </button>
      {isOpen && (
        <div className="space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
          {thoughts.map((t, i) => (
            <div
              key={i}
              className="flex justify-start opacity-70 hover:opacity-100 transition-opacity"
            >
              <div className="max-w-[90%] p-2 rounded-lg bg-zinc-900/50 border border-zinc-800 text-zinc-400 text-xs font-mono leading-relaxed">
                {t.parts && t.parts.length >= 2 ? (
                  <>
                    <p className="font-bold mb-1">{t.parts[0]}</p>
                    <MarkdownRenderer content={t.parts[1]} />
                  </>
                ) : (
                  <MarkdownRenderer content={t.text} />
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const ChatWindow: React.FC<ChatWindowProps> = ({
  onSendMessage,
  messages = [],
  isLoading = false,
  isStreaming = false,
  onStop,
  conversationName,
  onRename,
  onDelete,
}) => {
  const [inputValue, setInputValue] = useState("");
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const wasAtBottom = useRef(true);

  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState("");

  const handleSend = () => {
    if (inputValue.trim() && onSendMessage) {
      onSendMessage(inputValue);
      setInputValue("");
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSend();
    }
  };

  const handleScroll = () => {
    const container = scrollContainerRef.current;
    if (container) {
      // Check if user is near the bottom (with a buffer)
      const isAtBottom =
        container.scrollHeight - container.scrollTop <=
        container.clientHeight + 100;
      wasAtBottom.current = isAtBottom;
    }
  };

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (container && messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      const isUserMessage = lastMessage.type === "user";

      if (wasAtBottom.current || isUserMessage) {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: "smooth",
        });
      }
    }
  }, [messages]);

  // Group messages by turn (User Prompt -> All Thoughts -> Other System Messages)
  const displayUnits = useMemo(() => {
    const units: {
      type: "user" | "thought_group" | "system_message";
      data: any;
    }[] = [];

    let currentTurnThoughts: any[] = [];
    let currentTurnSystems: any[] = [];

    const flushTurn = () => {
      if (currentTurnThoughts.length > 0) {
        units.push({ type: "thought_group", data: currentTurnThoughts });
      }
      currentTurnSystems.forEach((msg) => {
        units.push({ type: "system_message", data: msg });
      });
      currentTurnThoughts = [];
      currentTurnSystems = [];
    };

    messages.forEach((msg) => {
      if (msg.type === "user") {
        flushTurn();
        units.push({ type: "user", data: msg });
      } else if (msg.isThought) {
        currentTurnThoughts.push(msg);
      } else if ((msg.text && msg.text.trim()) || msg.payload?.query) {
        currentTurnSystems.push(msg);
      }
    });

    flushTurn();
    return units;
  }, [messages]);

  const handleRenameSubmit = async () => {
    if (onRename && editedName.trim() && editedName !== conversationName) {
      await onRename(editedName);
    }
    setIsEditingName(false);
  };

  return (
    <div className="flex flex-col h-full bg-black text-white font-sans border border-zinc-800 rounded-lg overflow-hidden">
      <header className="p-4 border-b border-zinc-800 flex justify-between items-center bg-zinc-950">
        <div className="flex-1 min-w-0 mr-4">
          {isEditingName ? (
            <div className="flex items-center space-x-2">
              <input
                type="text"
                className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm text-cyan-400 focus:outline-none focus:border-cyan-500 w-full max-w-md"
                value={editedName}
                onChange={(e) => setEditedName(e.target.value)}
                onBlur={handleRenameSubmit}
                onKeyDown={(e) => e.key === "Enter" && handleRenameSubmit()}
                autoFocus
              />
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <h1 
                className={`text-xl font-bold tracking-tight text-cyan-400 truncate ${conversationName ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}`}
                onClick={() => {
                  if (conversationName) {
                    setEditedName(conversationName);
                    setIsEditingName(true);
                  }
                }}
              >
                {conversationName || "Conversational Analytics"}
              </h1>
              {conversationName && onDelete && (
                <button
                  onClick={onDelete}
                  className="text-zinc-600 hover:text-red-400 p-1 transition-colors"
                  aria-label="Delete session"
                >
                  <svg className="ml-1 w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              )}
            </div>
          )}
        </div>
        {!isEditingName && (
          <div className="text-xs text-zinc-500 uppercase tracking-widest shrink-0">
            {conversationName ? "" : "Looker + Gemini"}
          </div>
        )}
      </header>

      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-zinc-700"
      >
        {displayUnits.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-zinc-500 space-y-2 text-center">
            <div className="text-4xl">✨</div>
            <p>Ask a question about your data to get started.</p>
          </div>
        ) : (
          displayUnits.map((unit, idx) => {
            if (unit.type === "thought_group") {
              return (
                <div key={`tg-${idx}`} className="flex justify-start">
                  <div className="max-w-full w-full">
                    <ThoughtAccordion thoughts={unit.data} />
                  </div>
                </div>
              );
            }

            const msg = unit.data;
            return (
              <div
                key={`${unit.type}-${idx}`}
                className={`flex ${msg.type === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[90%] p-3 rounded-lg overflow-x-auto ${
                    msg.type === "user"
                      ? "bg-cyan-600 text-white rounded-br-none"
                      : "bg-zinc-800 text-zinc-100 rounded-bl-none border border-zinc-700"
                  }`}
                >
                  {msg.type === "user" ? (
                    <MarkdownRenderer content={msg.text} />
                  ) : (
                    <div className="space-y-3">
                      {msg.text && <MarkdownRenderer content={msg.text} />}
                      {msg.payload?.query && (
                        <div className="mt-2 pt-2 border-t border-zinc-700/50">
                          <p className="text-[10px] uppercase tracking-widest font-bold text-zinc-500 mb-2">
                            Looker Query
                          </p>
                          <pre className="p-2 bg-black/50 border border-zinc-700 rounded text-[10px] text-cyan-400 font-mono overflow-x-auto whitespace-pre">
                            <code>
                              {JSON.stringify(msg.payload.query, null, 2)}
                            </code>
                          </pre>
                          {msg.payload.exploreUrl && (
                            <a
                              href={msg.payload.exploreUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center mt-2 text-[10px] text-cyan-500 hover:text-cyan-400 font-bold uppercase tracking-tighter transition-colors"
                            >
                              Open in Looker Explore
                              <svg
                                className="ml-1 w-2.5 h-2.5"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                                xmlns="http://www.w3.org/2000/svg"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth="2"
                                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                                ></path>
                              </svg>
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      <footer className="p-4 border-t border-zinc-800 bg-zinc-950">
        <div className="flex space-x-2">
          <input
            type="text"
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded-md p-2 focus:outline-none focus:border-cyan-500 text-white placeholder-zinc-500 transition-colors"
            placeholder="Ask a question..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={isLoading}
          />
          {isStreaming ? (
            <button
              aria-label="Stop"
              className="bg-red-500 hover:bg-red-400 text-white font-bold py-2 px-4 rounded-md transition-all active:scale-95"
              onClick={onStop}
            >
              Stop
            </button>
          ) : (
            <button
              aria-label="Send"
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold py-2 px-4 rounded-md transition-all active:scale-95 disabled:opacity-50 disabled:active:scale-100"
              onClick={handleSend}
              disabled={isLoading || !inputValue.trim()}
            >
              Send
            </button>
          )}
        </div>
      </footer>
    </div>
  );
};
