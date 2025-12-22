import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';

interface SessionContextType {
  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;
  selectedAgentId: string | null;
  setSelectedAgentId: (id: string | null) => void;
  renameSession: (sessionId: string, newName: string) => void;
  getSessionName: (sessionId: string, defaultName: string) => string;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export const SessionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  
  // 1. Initialize from LocalStorage to persist names on reload
  const [sessionNames, setSessionNames] = useState<Record<string, string>>(() => {
    try {
      const saved = localStorage.getItem('session_renames');
      return saved ? JSON.parse(saved) : {};
    } catch (error) {
      console.error("Failed to load session names", error);
      return {};
    }
  });

  const renameSession = (sessionId: string, newName: string) => {
    setSessionNames((prev) => {
      const updated = { ...prev, [sessionId]: newName };
      // 2. Save to LocalStorage whenever a name changes
      localStorage.setItem('session_renames', JSON.stringify(updated));
      return updated;
    });
  };

  const getSessionName = (sessionId: string, defaultName: string) => {
    return sessionNames[sessionId] || defaultName;
  };

  return (
    <SessionContext.Provider value={{ 
      activeSessionId, 
      setActiveSessionId, 
      selectedAgentId, 
      setSelectedAgentId,
      renameSession,
      getSessionName
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