import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { apiClient } from '../services/clientService';
import { DialogBox } from './DialogBox';
import { 
  Add as AddIcon, 
  MoreVert as MoreVertIcon,
  PushPinOutlined as PinIcon, 
  PushPin as UnpinIcon, 
  EditOutlined as RenameIcon,
  FileDownloadOutlined as DownloadIcon, 
  DeleteOutline as DeleteIcon,
  ArrowDropDown as ArrowDropDownIcon
} from '@mui/icons-material';

interface Session {
  id: string;
  appName: string;
  userId: string;
  lastUpdateTime: number;
}

interface AgentOption {
  id: string;
  name: string;
}

export const SidePanel: React.FC = () => {
  const [agents, setAgents] = useState<AgentOption[]>([]);
  const [sessionHistory, setSessionHistory] = useState<Session[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [pinnedSessionIds, setPinnedSessionIds] = useState<string[]>([]);
  const [toast, setToast] = useState<{ message: string; visible: boolean }>({ message: '', visible: false });

  // UI State
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [agentMenuOpen, setAgentMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0, openUp: false });

  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);

  // Helper to close all menus
  const closeAllMenus = useCallback(() => {
    setMenuOpenId(null);
    setAgentMenuOpen(false);
  }, []);

  // 1. Global Click and Scroll Listeners
  useEffect(() => {
    const handleGlobalEvents = () => closeAllMenus();

    // Close on scroll anywhere in the window
    window.addEventListener('scroll', handleGlobalEvents, true);
    // Close on click anywhere
    window.addEventListener('click', handleGlobalEvents);

    return () => {
      window.removeEventListener('scroll', handleGlobalEvents, true);
      window.removeEventListener('click', handleGlobalEvents);
    };
  }, [closeAllMenus]);

  // Sorting Logic
  const sortHistory = (history: Session[], pinnedIds: string[]) => {
    return [...history].sort((a, b) => {
      const aPinned = pinnedIds.includes(a.id);
      const bPinned = pinnedIds.includes(b.id);
      if (aPinned && !bPinned) return -1;
      if (!aPinned && bPinned) return 1;
      return b.lastUpdateTime - a.lastUpdateTime;
    });
  };

  const showToast = (message: string) => {
    setToast({ message, visible: true });
    setTimeout(() => setToast({ message: '', visible: false }), 3000);
  };

  const togglePin = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    const isCurrentlyPinned = pinnedSessionIds.includes(sessionId);
    const newPinned = isCurrentlyPinned ? [] : [sessionId];
    setPinnedSessionIds(newPinned);
    setSessionHistory(prev => sortHistory(prev, newPinned));
    closeAllMenus();
    showToast(isCurrentlyPinned ? "Session unpinned" : "Session pinned");
  };

  // 2. Smart Positioning for Session Toolbar
  const handleToolbarClick = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (menuOpenId === id) {
      closeAllMenus();
      return;
    }

    const rect = e.currentTarget.getBoundingClientRect();
    const menuHeight = 170; // Estimated height of your toolbar menu
    const spaceBelow = window.innerHeight - rect.bottom;
    const shouldOpenUp = spaceBelow < menuHeight;

    setMenuPos({
      top: shouldOpenUp ? rect.top - menuHeight : rect.top,
      left: rect.right + 10,
      openUp: shouldOpenUp
    });
    setMenuOpenId(id);
    setAgentMenuOpen(false);
  };

  // 3. Smart Positioning for Agent Dropdown
  const handleAgentDropdownClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (agentMenuOpen) {
      closeAllMenus();
      return;
    }

    const rect = e.currentTarget.getBoundingClientRect();
    setMenuPos({ top: rect.bottom + 5, left: rect.left, openUp: false });
    setAgentMenuOpen(true);
    setMenuOpenId(null);
  };

  const refreshAndSortHistory = async (agentId: string) => {
    try {
      const history: Session[] = await apiClient.get(`/apps/${agentId}/users/user/sessions`);
      const sorted = sortHistory(history, pinnedSessionIds);
      setSessionHistory(sorted);
      if (sorted.length > 0) {
        setActiveSessionId(sorted[0].id);
        return sorted[0].id;
      }
    } catch (err) { console.error("Refresh history failed", err); }
    return null;
  };

  const handleDeleteConfirm = async () => {
    if (!sessionToDelete || !selectedAgentId) return;
    try {
      await apiClient.delete(`/apps/${selectedAgentId}/users/user/sessions/${sessionToDelete}`);
      setIsDeleteDialogOpen(false);
      closeAllMenus();
      const newLatestId = await refreshAndSortHistory(selectedAgentId);
      if (newLatestId) {
        await apiClient.get(`/apps/${selectedAgentId}/users/user/sessions/${newLatestId}`);
        await apiClient.get(`/debug/trace/session/${newLatestId}`);
      } else {
        setSessionHistory([]);
        setActiveSessionId(null);
      }
    } catch (err) { console.error("Delete flow failed", err); }
  };

  const handleDownload = async (sessionId: string) => {
    if (!selectedAgentId) return;
    try {
      const blob = await apiClient.download(`/apps/${selectedAgentId}/users/user/sessions/${sessionId}`);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `session-${sessionId.substring(0, 8)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      closeAllMenus();
    } catch (err) { console.error("Download failed", err); }
  };

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await apiClient.get('/list-apps');
        if (Array.isArray(response)) {
          setAgents(response.map(name => ({ id: name, name: name })));
        }
      } catch (err) { console.error("Agents fetch failed", err); }
    };
    fetchAgents();
  }, []);

  const runFullSessionFlow = async (agentId: string) => {
    try {
      const sessionData = await apiClient.post(`/apps/${agentId}/users/user/sessions`);
      const newId = sessionData.id;
      await apiClient.get(`/apps/${agentId}/users/user/sessions/${newId}`);
      await apiClient.get(`/debug/trace/session/${newId}`);
      await refreshAndSortHistory(agentId);
      setActiveSessionId(newId);
    } catch (err) { console.error("Session Flow Failed", err); }
  };

  const handleAgentSelect = (agentId: string) => {
    setSelectedAgentId(agentId);
    closeAllMenus();
    runFullSessionFlow(agentId);
  };

  const handleNewSessionClick = () => {
    if (selectedAgentId) runFullSessionFlow(selectedAgentId);
    else alert("Please select an agent first");
  };

  const formatSessionTime = (epoch: number) => {
    const date = new Date(epoch * 1000);
    return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const getSessionDisplayName = (sessionId: string | null): string => {
    if (!sessionId) return "";
    const session = sessionHistory.find((s) => s.id === sessionId);
    return session?.id || "";
  };

  return (
    <div className="side-panel-container">
      <div className="side-panel-header-section">
        <div className="agent-selector-wrapper" onClick={handleAgentDropdownClick}>
          <span className="agent-label">Agent</span>
          <span className={`agent-name-underlined ${!selectedAgentId ? 'placeholder' : ''}`}>
            {agents.find(a => a.id === selectedAgentId)?.name || "select agent"}
          </span>
          <ArrowDropDownIcon className="agent-arrow-icon" />
          
          {agentMenuOpen && createPortal(
            <div 
              className="side-panel-dropdown-toolbar-menu" 
              style={{ 
                position: 'fixed',  
                zIndex: 99999 
              }}
              onClick={(e) => e.stopPropagation()} // Prevent closing when clicking inside
            >
              {agents.map(agent => (
                <div key={agent.id} className="dropdown-item" onClick={() => handleAgentSelect(agent.id)}>
                  {agent.name}
                </div>
              ))}
            </div>, document.body
          )}
        </div>

        <button className="side-panel-new-session-button" onClick={handleNewSessionClick}>
          <AddIcon style={{ fontSize: '1.25rem' }} />
          New Session
        </button>

        <h3 className="side-panel-history-header">Session History</h3>
      </div>

      <div className="side-panel-session-list-container">
        {sessionHistory.map((session) => {
          const isPinned = pinnedSessionIds.includes(session.id);
          return (
            <div
              key={session.id}
              className={`side-panel-session-item ${session.id === activeSessionId ? 'active' : ''}`}
              onClick={() => setActiveSessionId(session.id)}
            >
              <div className="side-panel-content-wrapper">
                <div className="side-panel-text-content">
                  <div className="side-panel-session-title">Session: {session.id.substring(0, 8)}...</div>
                  <div className="side-panel-session-timestamp">{formatSessionTime(session.lastUpdateTime)}</div>
                </div>

                <div className="side-panel-actions-wrapper">
                  {isPinned && <UnpinIcon className="pinned-indicator-icon" fontSize="small" style={{ color: '#004a77' }} />}
                  <button 
                    className={`side-panel-action-dots ${menuOpenId === session.id ? 'visible' : ''}`}
                    onClick={(e) => handleToolbarClick(e, session.id)}
                  >
                    <MoreVertIcon fontSize="small" />
                  </button>
                </div>
              </div>

              {menuOpenId === session.id && createPortal(
                <div 
                  className="side-panel-toolbar-menu" 
                  style={{ 
                    position: 'fixed', 
                    top: menuPos.top, 
                    left: menuPos.left, 
                    zIndex: 99999,
                    transform: menuPos.openUp ? 'translateY(-10%)' : 'none' 
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="menu-item" onClick={(e) => togglePin(e, session.id)}>
                    {isPinned ? <UnpinIcon className="menu-icon" style={{ color: '#004a77' }} /> : <PinIcon className="menu-icon" />}
                    {isPinned ? 'Unpin' : 'Pin'}
                  </div>
                  <div className="menu-item"><RenameIcon className="menu-icon" /> Rename</div>
                  <div className="menu-item" onClick={(e) => handleDownload(session.id)}>
                    <DownloadIcon className="menu-icon" /> Download
                  </div>
                  <div className="menu-divider"></div>
                  <div className="menu-item delete" onClick={(e) => {
                    setSessionToDelete(session.id);
                    setIsDeleteDialogOpen(true);
                  }}>
                    <DeleteIcon className="menu-icon" /> Delete
                  </div>
                </div>, document.body
              )}
            </div>
          );
        })}
      </div>

      <DialogBox 
        isOpen={isDeleteDialogOpen}
        title="Delete saved session?"
        content={`This action will delete saved session “${getSessionDisplayName(sessionToDelete || '')}”. Are you sure you want to continue ?`}
        confirmLabel="Continue"
        onConfirm={handleDeleteConfirm}
        onCancel={() => { setIsDeleteDialogOpen(false); setSessionToDelete(null); }}
      />

      {toast.visible && createPortal(
        <div className="side-panel-toast">{toast.message}</div>,
        document.body
      )}
    </div>
  );
};