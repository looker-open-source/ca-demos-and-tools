import React, { createContext, useContext, useState, ReactNode, useEffect, useRef } from 'react';
import { chatService } from '../services/clientService'; 
export interface Message {
  role: 'user' | 'bot';
  text: string;
}

interface SessionContextType {
  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;
  selectedAgentId: string | null;
  setSelectedAgentId: (id: string | null) => void;
  renameSession: (sessionId: string, newName: string) => void;
  getSessionName: (sessionId: string, defaultName: string) => string;
  traceRefreshTrigger: number; 
  notifyMessageSent: () => void;
  messages: Message[];
  isSending: boolean;
  sendMessage: (text: string, files: any[]) => Promise<void>;
  clearMessages: () => void;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export const SessionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [traceRefreshTrigger, setTraceRefreshTrigger] = useState(0);

  const [messages, setMessages] = useState<Message[]>([]);
  const [isSending, setIsSending] = useState(false);
  const activeSessionIdRef = useRef(activeSessionId);
  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  const [sessionNames, setSessionNames] = useState<Record<string, string>>(() => {
    try {
      const saved = localStorage.getItem('session_renames');
      return saved ? JSON.parse(saved) : {};
    } catch (error) {
      console.error("Failed to load session names", error);
      return {};
    }
  });

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }

    setIsSending(false); 
    try {
      const savedHistory = localStorage.getItem(`chat_history_${activeSessionId}`);
      if (savedHistory) {
        setMessages(JSON.parse(savedHistory));
      } else {
        setMessages([]);
      }
    } catch (e) {
      console.error("Failed to parse chat history", e);
      setMessages([]);
    }
  }, [activeSessionId]);

  useEffect(() => {
    const currentId = activeSessionIdRef.current;
    if (currentId && messages.length > 0) {
      localStorage.setItem(`chat_history_${currentId}`, JSON.stringify(messages));
    }
  }, [messages]);

  const renameSession = (sessionId: string, newName: string) => {
    setSessionNames((prev) => {
      const updated = { ...prev, [sessionId]: newName };
      localStorage.setItem('session_renames', JSON.stringify(updated));
      return updated;
    });
  };

  const getSessionName = (sessionId: string, defaultName: string) => {
    return sessionNames[sessionId] || defaultName;
  };

  const notifyMessageSent = () => {
    setTraceRefreshTrigger(prev => prev + 1);
  };

  const clearMessages = () => setMessages([]);
  const sendMessage = async (text: string, files: any[]) => {
    if (!activeSessionId) {
        alert("No active session!");
        return;
    }

    const newUserMsg: Message = { role: 'user', text: text };
    const placeholderBotMsg: Message = { role: 'bot', text: '' };

    setMessages((prev) => [...prev, newUserMsg, placeholderBotMsg]);
    setIsSending(true);

    try {
        await chatService.sendUserMessage(
            selectedAgentId || "ca_api_agent",
            text, 
            activeSessionId, 
            files, 
            (chunk) => {
                setMessages((prev) => {
                    const updated = [...prev];
                    const lastIndex = updated.length - 1;
                    const lastMsg = updated[lastIndex];

                    if (lastMsg.role === 'bot') {
                        updated[lastIndex] = {
                            ...lastMsg,
                            text: lastMsg.text + chunk
                        };
                    }
                    return updated;
                });
            }
        );
        notifyMessageSent();
    } catch (error) {
        console.error("API Error:", error);
        setMessages((prev) => {
            const updated = [...prev];
            const lastIndex = updated.length - 1;
            const lastMsg = updated[lastIndex];
            
            if (lastMsg.role === 'bot' && !lastMsg.text) {
                updated[lastIndex] = {
                    ...lastMsg,
                    text: "Error: Could not reach agent."
                };
            }
            return updated;
        });
    } finally {
        setIsSending(false);
    }
  };

  return (
    <SessionContext.Provider value={{ 
      activeSessionId, 
      setActiveSessionId, 
      selectedAgentId, 
      setSelectedAgentId, 
      renameSession, 
      getSessionName, 
      traceRefreshTrigger, 
      notifyMessageSent,
      messages,
      isSending,
      sendMessage,
      clearMessages
    }}>
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = () => {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};