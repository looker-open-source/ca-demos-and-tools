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

import React, { useEffect, useRef, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { ChatWindow } from "@/components/ChatWindow";
import { DataVisualization } from "@/components/DataVisualization";
import { ErrorMessage } from "@/components/ErrorMessage";
import { AgentSelector } from "@/components/AgentSelector";
import { ConversationSelector } from "@/components/ConversationSelector";
import LoadingOverlay from "@/components/LoadingOverlay";
import { LogDrawer } from "@/components/dev-log/LogDrawer";
import { useChatStore } from "@/store/useChatStore";
import { logRequest as fetch } from "@/lib/dev-logger/interceptor";
import { useDevLogStore } from "@/lib/dev-logger/store";
import { parseLookerMessage } from "@/lib/message-utils";
import { useLookerAuth } from "@/components/LookerAuthProvider";

export default function Home() {
  const abortControllerRef = React.useRef<AbortController | null>(null);
  const isSilentAbortRef = React.useRef(false);
  const workspaceScrollRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { isAuthenticated, logout, isInitialized, authConfig } = useLookerAuth();

  const isOAuthMode = useMemo(() => {
    // Explicitly check for 'env' mode
    if (authConfig.authMode === 'env') return false;
    
    // Default to OAuth if mode is 'oauth' OR if a valid client ID is present
    return authConfig.authMode === 'oauth' || (!!authConfig.oauthClientId && authConfig.oauthClientId !== 'your-client-id');
  }, [authConfig]);

  // Redirect to login if in OAuth mode and not authenticated
  useEffect(() => {
    if (isInitialized && isOAuthMode && !isAuthenticated) {
      router.push('/login');
    }
  }, [isInitialized, isOAuthMode, isAuthenticated, router]);

  const {
    messages,
    addMessage,
    isLoading,
    setLoading,
    conversationId,
    setConversationId,
    error,
    setError,
    clearMessages,
    agents,
    setAgents,
    selectedAgentId,
    setSelectedAgentId,
    conversations,
    fetchConversations,
    selectConversation,
    currentConversationName,
    updateConversationName,
    deleteConversation,
    setLookerBaseUrl: setStoreLookerBaseUrl,
    resetTitle,
  } = useChatStore();

  const [isAgentsLoading, setIsAgentsLoading] = React.useState(false);
  const [statusText, setStatusText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [lookerBaseUrl, setLookerBaseUrl] = useState<string | null>(null);

  useEffect(() => {
    const fetchAgents = async () => {
      // Don't fetch if in OAuth mode and not authenticated
      if (isOAuthMode && !isAuthenticated) return;
      if (agents.length > 0) return;

      setIsAgentsLoading(true);
      try {
        const response = await fetch("/api/agents");
        if (!response.ok) throw new Error("Failed to fetch agents");
        const {
          agents: data,
          defaultAgentId: serverDefaultId,
          lookerBaseUrl: serverBaseUrl,
        } = await response.json();

        // Sort agents alphanumeric by name
        const sortedAgents = [...data].sort((a, b) =>
          a.name.localeCompare(b.name),
        );

        setAgents(sortedAgents);
        setLookerBaseUrl(serverBaseUrl);
        setStoreLookerBaseUrl(serverBaseUrl);

        if (sortedAgents.length > 0 && !selectedAgentId) {
          // Use the ID from the server if available, otherwise fallback to the build-time env var
          const defaultAgentId =
            serverDefaultId || process.env.NEXT_PUBLIC_DEFAULT_AGENT_ID;
          const defaultAgentExists = sortedAgents.find(
            (a: any) => a.id === defaultAgentId,
          );

          if (defaultAgentId && defaultAgentExists) {
            setSelectedAgentId(defaultAgentId);
          } else {
            setSelectedAgentId(sortedAgents[0].id);
          }
        }
      } catch (err: any) {
        console.error("Error fetching agents:", err);
      } finally {
        setIsAgentsLoading(false);
      }
    };

    fetchAgents();
  }, [
    setAgents,
    setSelectedAgentId,
    agents.length,
    selectedAgentId,
    setStoreLookerBaseUrl,
    isOAuthMode,
    isAuthenticated,
  ]);

  useEffect(() => {
    if (selectedAgentId) {
      // Don't fetch if in OAuth mode and not authenticated
      if (isOAuthMode && !isAuthenticated) return;
      setStatusText("Loading past conversations ...");
      fetchConversations(selectedAgentId);
    }
  }, [selectedAgentId, fetchConversations, isOAuthMode, isAuthenticated]);

  useEffect(() => {
    const container = workspaceScrollRef.current;
    if (container && messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      const hasNewPayload = !!lastMessage.payload;

      if (hasNewPayload) {
        setTimeout(() => {
          container.scrollTo({
            top: container.scrollHeight,
            behavior: "smooth",
          });
        }, 100);
      }
    }
  }, [messages]);

  const handleStop = (isSilent = false) => {
    if (abortControllerRef.current) {
      isSilentAbortRef.current = isSilent;
      abortControllerRef.current.abort();
    }
  };

  const handleSendMessage = async (text: string) => {
    handleStop(true);
    setError(null);
    setLoading(true);
    setIsStreaming(true);
    setStatusText("Analyzing question ...");
    addMessage({ type: "user", text });

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortControllerRef.current.signal,
        body: JSON.stringify({
          userMessage: text,
          conversationId: conversationId || undefined,
          agentId: selectedAgentId || undefined,
          timestamp: new Date().toISOString(),
        }),
      });

      const logId = (response as any).logId;

      if (!response.ok) throw new Error("API request failed");

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error("ReadableStream not supported");

      let partialChunk = "";
      let isFirstControlMessage = true;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });

        const lines = (partialChunk + chunk).split("\n");
        partialChunk = lines.pop() || ""; // Keep the last partial line

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const obj = JSON.parse(line);
            console.log("[UI] Parsed object:", obj);

            if (logId) {
              useDevLogStore.getState().appendChunk(logId, line);
              if (
                obj.type === "message" &&
                obj.data?.systemMessage?.text?.textType === "FINAL_RESPONSE"
              ) {
                useDevLogStore
                  .getState()
                  .updateLog(logId, { status: "200 (Done)" });
              }
            }

            if (obj.type === "control" && obj.conversationId) {
              const newConvId = obj.conversationId;
              const isNewSession = !conversationId;
              setConversationId(newConvId);

              // Rename conversation if it's a new session and this is the first control message
              if (isNewSession && isFirstControlMessage) {
                isFirstControlMessage = false;
                const newName = text.slice(0, 100);
                await updateConversationName(newConvId, newName);
                if (selectedAgentId) {
                  fetchConversations(selectedAgentId);
                }
              }
            } else if (obj.type === "dev-log" && obj.log) {
              const { id, status, ...rest } = obj.log;
              const existingLog = useDevLogStore
                .getState()
                .logs.find((l) => l.id === id);
              if (existingLog) {
                useDevLogStore.getState().updateLog(id, { status, ...rest });
              } else {
                useDevLogStore.getState().addLog({ id, status, ...rest });
              }
            } else if (obj.type === "message") {
              const lm = obj.data;
              const {
                type,
                text: parsedText,
                payload,
                isThought,
                parts,
              } = parseLookerMessage(lm, lookerBaseUrl || undefined);

              if (isThought && parts.length > 0) {
                setStatusText(parts[0]);
              }

              if (parsedText || payload) {
                addMessage({
                  type,
                  text: parsedText,
                  payload,
                  isThought,
                  parts,
                });
              }
            } else if (obj.type === "error") {
              throw new Error(obj.message);
            }
          } catch (e) {
            console.error("Error parsing stream line:", e, line);
          }
        }
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        if (!isSilentAbortRef.current) {
          addMessage({ type: "system", text: "The query was cancelled" });
        }
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
      setIsStreaming(false);
      setStatusText("");
      abortControllerRef.current = null;
      isSilentAbortRef.current = false;
    }
  };

  const handleReset = () => {
    handleStop(true);
    clearMessages();
    setConversationId(null);
    setError(null);
    resetTitle();
  };

  const handleConversationSelect = async (id: string) => {
    setStatusText("Loading conversation ...");
    await selectConversation(id);
  };

  const handleAgentSelect = (id: string) => {
    if (id === selectedAgentId) return;

    const hasContent = messages.length > 0 || conversationId || isLoading;
    if (hasContent) {
      const proceed = window.confirm(
        "This will clear your current conversation, proceed?",
      );
      if (!proceed) return;
    }

    handleReset();
    setSelectedAgentId(id);
  };

  const handleDeleteSession = async () => {
    if (!conversationId) return;
    const confirmed = window.confirm(
      "Are you sure you want to delete this session? This action cannot be undone.",
    );
    if (confirmed) {
      await deleteConversation(conversationId);
      handleReset();
    }
  };

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  // If in OAuth mode and not authenticated, or if agents are still loading, show overlay
  if (!isInitialized || (isOAuthMode && !isAuthenticated)) {
    return <LoadingOverlay isVisible={true} />;
  }

  // Ensure we don't flash the main content while agents are first loading
  const isInitialLoad = isAgentsLoading && agents.length === 0;

  return (
    <main className="flex h-screen flex-col bg-black text-white font-sans p-6 md:p-10 space-y-6 overflow-hidden transition-all duration-300">
      <LoadingOverlay isVisible={isAgentsLoading || isInitialLoad} />
      <header className="flex justify-between items-center mb-4">
        <div>
          <h1 className="text-3xl font-black italic tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-600">
            LOOKER CONVERSATIONAL ANALYTICS API
          </h1>
          <p className="text-zinc-500 text-xs font-mono uppercase tracking-widest mt-1">
            Reference Implementation
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <button
            onClick={handleReset}
            className="text-xs border border-zinc-800 hover:border-zinc-600 px-3 py-1.5 rounded uppercase tracking-tighter transition-colors text-zinc-400"
          >
            New Session ⚡
          </button>
          {isOAuthMode && isAuthenticated && (
            <button
              onClick={handleLogout}
              className="text-xs border border-red-900/50 bg-red-950/20 hover:bg-red-900/40 px-3 py-1.5 rounded uppercase tracking-tighter transition-colors text-red-400"
            >
              Logout 🚪
            </button>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 flex-1 overflow-hidden">
        {/* Chat Sidebar */}
        <div className="lg:col-span-4 flex flex-col h-[70vh] lg:h-full min-h-0">
          <div className="space-y-3 mb-4">
            <AgentSelector
              agents={agents}
              selectedAgentId={selectedAgentId}
              onSelect={handleAgentSelect}
              isLoading={isAgentsLoading}
            />
            <ConversationSelector
              conversations={conversations}
              selectedConversationId={conversationId}
              onSelect={handleConversationSelect}
              isLoading={isLoading && conversations.length === 0}
              isDisabled={!selectedAgentId}
            />
          </div>
          <div className="flex-1 min-h-0">
            <ChatWindow
              messages={messages}
              onSendMessage={handleSendMessage}
              isLoading={isLoading || isAgentsLoading}
              isStreaming={isStreaming}
              onStop={() => handleStop()}
              conversationName={currentConversationName}
              onRename={(name) => updateConversationName(conversationId!, name)}
              onDelete={handleDeleteSession}
            />
          </div>

          {(isLoading || isStreaming || isAgentsLoading) && (
            <div className="mt-3 flex items-center justify-center space-x-2 text-cyan-400 font-mono text-xs uppercase tracking-widest animate-pulse shrink-0">
              <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-ping"></span>
              <span>
                {statusText ||
                  (isAgentsLoading
                    ? "Initializing agents..."
                    : "Gemini is working...")}
              </span>
            </div>
          )}

          {error && (
            <div className="mt-4">
              <ErrorMessage
                message={error}
                onRetry={() =>
                  handleSendMessage(
                    messages.filter((m) => m.type === "user").pop()?.text ||
                      "Hello",
                  )
                }
              />
            </div>
          )}
        </div>

        {/* Insight Workspace */}
        <div className="lg:col-span-8 flex flex-col h-[70vh] lg:h-full min-h-0">
          <div
            ref={workspaceScrollRef}
            className="bg-zinc-950 border border-zinc-900 rounded-xl p-6 flex-1 flex flex-col overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800"
          >
            <h2 className="text-sm font-bold text-zinc-400 uppercase tracking-widest mb-6 flex items-center">
              <span className="w-2 h-2 bg-blue-500 rounded-full mr-2"></span>
              Insight Workspace
            </h2>

            <div className="flex-1">
              {messages.some(
                (m) =>
                  m.payload &&
                  (m.payload.data?.length > 0 ||
                    m.payload.isChart ||
                    m.payload.vegaConfig),
              ) ? (
                <div className="w-full space-y-8 pb-10">
                  {messages
                    .filter(
                      (m) =>
                        m.payload &&
                        (m.payload.data?.length > 0 ||
                          m.payload.isChart ||
                          m.payload.vegaConfig),
                    )
                    .map((m, idx) => (
                      <div
                        key={idx}
                        className="animate-in fade-in slide-in-from-bottom-4 duration-700"
                      >
                        <h3 className="text-xs font-mono text-zinc-600 mb-2 px-2">
                          RESULT #{idx + 1}
                        </h3>
                        <DataVisualization
                          data={m.payload.data || []}
                          type={m.payload.data ? "table" : "chart"}
                          payload={m.payload}
                        />
                      </div>
                    ))}
                </div>
              ) : (
                <div className="h-full flex flex-col justify-center items-center text-center space-y-4">
                  <div className="text-6xl grayscale opacity-20">📊</div>
                  <h3 className="text-zinc-700 font-medium">
                    No active visualizations
                  </h3>
                  <p className="text-zinc-800 text-sm max-w-xs">
                    Interactive charts and tables will appear here based on your
                    conversation.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      <LogDrawer />
    </main>
  );
}
