import React, { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { apiClient } from '../services/clientService';
import { DialogBox } from './DialogBox';
import { useSession } from '../context/SessionContext';
import { 
  Add as AddIcon, 
  MoreVert as MoreVertIcon,
  PushPinOutlined as PinIcon, 
  EditOutlined as RenameIcon,
  FileDownloadOutlined as DownloadIcon, 
  DeleteOutline as DeleteIcon,
  ArrowDropDown as ArrowDropDownIcon
} from '@mui/icons-material';
import CircularProgress from '@mui/material/CircularProgress';
import Box from '@mui/material/Box';

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
  const { 
    activeSessionId, 
    setActiveSessionId, 
    selectedAgentId, 
    setSelectedAgentId,
    renameSession,
    getSessionName
  } = useSession();

  const [agents, setAgents] = useState<AgentOption[]>([]);
  const [sessionHistory, setSessionHistory] = useState<Session[]>([]);
  const [pinnedSessionIds, setPinnedSessionIds] = useState<string[]>([]);
  const [toast, setToast] = useState<{ message: string; visible: boolean }>({ message: '', visible: false });

  // UI State
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [agentMenuOpen, setAgentMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0, openUp: false });
  
  // Loading States
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [isGlobalLoading, setIsGlobalLoading] = useState(false);

  // Dialog States
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);
  const [isAgentWarningOpen, setIsAgentWarningOpen] = useState(false);
  
  // Rename States
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const [sessionToRename, setSessionToRename] = useState<string | null>(null);
  const [newNameInput, setNewNameInput] = useState("");

  const [isUnpinHovered, setIsUnpinHovered] = useState<string | null>(null);
  const isInitialized = useRef(false);

  // 1. Sort Helper
  const sortHistory = useCallback((history: Session[], pinnedIds: string[]) => {
    return [...history].sort((a, b) => {
      const aPinned = pinnedIds.includes(a.id);
      const bPinned = pinnedIds.includes(b.id);
      if (aPinned && !bPinned) return -1;
      if (!aPinned && bPinned) return 1;
      return b.lastUpdateTime - a.lastUpdateTime;
    });
  }, []);

  // 2. Details Fetch Helper
  const fetchSessionDetails = useCallback(async (agentId: string, sessionId: string) => {
    setIsLoadingDetails(true);
    try {
      await apiClient.get(`/apps/${agentId}/users/user/sessions/${sessionId}`);
      await apiClient.get(`/debug/trace/session/${sessionId}`);
    } catch (err) {
      console.error("Failed to load session details", err);
    } finally {
      setIsLoadingDetails(false);
    }
  }, []);

  // 3. Refresh List Helper
  const refreshAndSortHistory = useCallback(async (agentId: string, shouldFetchDetails = true) => {
    try {
      const history: Session[] = await apiClient.get(`/apps/${agentId}/users/user/sessions`);
      const sorted = sortHistory(history, pinnedSessionIds);
      setSessionHistory(sorted);
      if (sorted.length > 0 && shouldFetchDetails) {
        const firstId = sorted[0].id;
        setActiveSessionId(firstId);
        fetchSessionDetails(agentId, firstId);
      }
    } catch (err) { console.error("Refresh failed", err); }
  }, [sortHistory, pinnedSessionIds, setActiveSessionId, fetchSessionDetails]);

  // 4. Create New Session Flow
  const runFullSessionFlow = useCallback(async (agentId: string) => {
    setIsGlobalLoading(true);
    try {
      const sessionData = await apiClient.post(`/apps/${agentId}/users/user/sessions`);
      const newId = sessionData.id;
      setActiveSessionId(newId);
      await fetchSessionDetails(agentId, newId);
      await refreshAndSortHistory(agentId, false);
    } catch (err) { 
      console.error("Flow failed", err); 
    } finally {
      setIsGlobalLoading(false);
    }
  }, [fetchSessionDetails, refreshAndSortHistory, setActiveSessionId]);

  // --- INITIALIZATION & DEEP LINKING ---
  useEffect(() => {
    if (isInitialized.current) return;
    isInitialized.current = true;

    const initializeApp = async () => {
      setIsGlobalLoading(true);
      const params = new URLSearchParams(window.location.search);
      const urlApp = params.get('app');
      const urlSession = params.get('session');

      try {
        const response = await apiClient.get('/list-apps');
        if (Array.isArray(response) && response.length > 0) {
          setAgents(response.map(name => ({ id: name, name: name })));

          // CASE A: Deep Link exists in URL
          if (urlApp && response.includes(urlApp)) {
            setSelectedAgentId(urlApp);
            const history: Session[] = await apiClient.get(`/apps/${urlApp}/users/user/sessions`);
            const sorted = sortHistory(history, pinnedSessionIds);
            setSessionHistory(sorted);

            if (urlSession && history.find(s => s.id === urlSession)) {
              setActiveSessionId(urlSession);
              await fetchSessionDetails(urlApp, urlSession);
            }
          } 
          // CASE B: Default Load (No URL params) -> Select First Agent & Create Session
          else if (!urlApp) {
            const firstAgent = response[0];
            setSelectedAgentId(firstAgent);
            await runFullSessionFlow(firstAgent);
          }
        }
      } catch (err) {
        console.error("Initialization Flow Failed", err);
      } finally {
        setIsGlobalLoading(false);
      }
    };

    initializeApp();
  }, [sortHistory, pinnedSessionIds, fetchSessionDetails, setSelectedAgentId, setActiveSessionId, runFullSessionFlow]);

  // --- URL SYNCHRONIZATION ---
  useEffect(() => {
    const params = new URLSearchParams();
    if (selectedAgentId) params.set('app', selectedAgentId);
    if (activeSessionId) params.set('session', activeSessionId);
    if (selectedAgentId || activeSessionId) params.set('userId', 'user');

    const queryString = params.toString();
    const newPath = queryString ? `/dev-ui/?${queryString}` : '/dev-ui/';

    if (window.location.pathname + window.location.search !== newPath) {
      window.history.pushState(null, '', newPath);
    }
  }, [selectedAgentId, activeSessionId]);

  // --- Handlers ---
  const handleSessionClick = (sessionId: string) => {
    if (!selectedAgentId || sessionId === activeSessionId) return;
    setActiveSessionId(sessionId);
    fetchSessionDetails(selectedAgentId, sessionId);
  };

  const handleRenameClick = (sessionId: string) => {
    const defaultName = `${sessionId.substring(0, 8)}...`;
    const currentName = getSessionName(sessionId, defaultName);
    
    setSessionToRename(sessionId);
    // If name matches the default ID format, leave input empty. Otherwise, show custom name.
    setNewNameInput(currentName === defaultName ? "" : currentName);
    setIsRenameDialogOpen(true);
    closeAllMenus();
  };

  const handleRenameConfirm = () => {
    if (sessionToRename && newNameInput.trim()) {
      renameSession(sessionToRename, newNameInput.trim());
    }
    setIsRenameDialogOpen(false);
    setSessionToRename(null);
  };

  const closeAllMenus = useCallback(() => {
    setMenuOpenId(null);
    setAgentMenuOpen(false);
  }, []);

  useEffect(() => {
    const handleGlobalEvents = () => closeAllMenus();
    window.addEventListener('scroll', handleGlobalEvents, true);
    window.addEventListener('click', handleGlobalEvents);
    return () => {
      window.removeEventListener('scroll', handleGlobalEvents, true);
      window.removeEventListener('click', handleGlobalEvents);
    };
  }, [closeAllMenus]);

  const togglePin = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    const isCurrentlyPinned = pinnedSessionIds.includes(sessionId);
    const newPinned = isCurrentlyPinned ? [] : [sessionId];
    setPinnedSessionIds(newPinned);
    setSessionHistory(prev => sortHistory(prev, newPinned));
    closeAllMenus();
    setToast({ message: isCurrentlyPinned ? "Session unpinned" : "Session pinned", visible: true });
    setTimeout(() => setToast({ message: '', visible: false }), 3000);
  };

  const handleToolbarClick = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (menuOpenId === id) { closeAllMenus(); return; }
    const rect = e.currentTarget.getBoundingClientRect();
    const menuHeight = 170;
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

  const handleAgentDropdownClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setMenuPos({ top: rect.bottom + 5, left: rect.left, openUp: false });
    setAgentMenuOpen(true);
    setMenuOpenId(null);
  };

  const handleDeleteConfirm = async () => {
    if (!sessionToDelete || !selectedAgentId) return;
    setIsGlobalLoading(true);
    try {
      await apiClient.delete(`/apps/${selectedAgentId}/users/user/sessions/${sessionToDelete}`);
      setIsDeleteDialogOpen(false);
      closeAllMenus();
      await refreshAndSortHistory(selectedAgentId, true);
    } catch (err) { 
      console.error("Delete failed", err); 
    } finally {
      setIsGlobalLoading(false);
    }
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

  const handleAgentSelect = (agentId: string) => {
    setSelectedAgentId(agentId);
    closeAllMenus();
    runFullSessionFlow(agentId);
  };

  const formatSessionTime = (epoch: number) => {
    const date = new Date(epoch * 1000);
    return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="side-panel-container" style={{ position: 'relative' }}>
      {isGlobalLoading && (
        <div style={{ 
          position: 'absolute', 
          top: 0, left: 0, right: 0, bottom: 0, 
          backgroundColor: 'rgba(255, 255, 255, 0.7)', 
          zIndex: 10, 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center' 
        }}>
          <CircularProgress />
        </div>
      )}

      <div className="side-panel-header-section">
        <div className="agent-selector-wrapper" onClick={handleAgentDropdownClick}>
          <span className="agent-label">Agent</span>
          <span className={`agent-name-underlined ${!selectedAgentId ? 'placeholder' : ''}`}>
            {agents.find(a => a.id === selectedAgentId)?.name || "select agent"}
          </span>
          <ArrowDropDownIcon className="agent-arrow-icon" />
          {agentMenuOpen && createPortal(
            <div className="side-panel-dropdown-toolbar-menu" style={{ position: 'fixed', zIndex: 99999 }} onClick={(e) => e.stopPropagation()}>
              {agents.map(agent => (
                <div key={agent.id} className="dropdown-item" onClick={() => handleAgentSelect(agent.id)}>{agent.name}</div>
              ))}
            </div>, document.body
          )}
        </div>
        <button className="side-panel-new-session-button" onClick={() => selectedAgentId ? runFullSessionFlow(selectedAgentId) : setIsAgentWarningOpen(true)}>
          <AddIcon style={{ fontSize: '1.25rem' }} /> New Session
        </button>
        <h3 className="side-panel-history-header">Session History</h3>
      </div>
      
      <div className="side-panel-session-list-container">
        {sessionHistory.map((session) => {
          const isPinned = pinnedSessionIds.includes(session.id);
          const isActive = session.id === activeSessionId;
          // Updated: Removed "Session: " prefix from default name
          const displayName = getSessionName(session.id, `${session.id.substring(0, 22)}...`);

          return (
            <div 
              key={session.id} 
              className={`side-panel-session-item ${isActive ? 'active' : ''}`} 
              onClick={() => handleSessionClick(session.id)}
            >
              <div className="side-panel-content-wrapper">
                <div className="side-panel-text-content">
                  <div className="side-panel-session-title">
                    {isActive && isLoadingDetails ? (
                       <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                         Loading... <CircularProgress size={14} thickness={5} />
                       </Box>
                    ) : (
                       displayName
                    )}
                  </div>
                  <div className="side-panel-session-timestamp">{formatSessionTime(session.lastUpdateTime)}</div>
                </div>
                <div className="side-panel-actions-wrapper">
                  {isPinned && <PinIcon className="menu-icon" style={{ color: '#004a77' }} />}
                  <button className={`side-panel-action-dots ${menuOpenId === session.id ? 'visible' : ''}`} onClick={(e) => handleToolbarClick(e, session.id)}>
                    <MoreVertIcon fontSize="small" />
                  </button>
                </div>
              </div>
              {menuOpenId === session.id && createPortal(
                <div className="side-panel-toolbar-menu" style={{ position: 'fixed', top: menuPos.top, left: menuPos.left, zIndex: 99999, transform: menuPos.openUp ? 'translateY(-10%)' : 'none' }} onClick={(e) => e.stopPropagation()}>
                  <div className="menu-item" onClick={(e) => togglePin(e, session.id)} onMouseEnter={() => setIsUnpinHovered(session.id)} onMouseLeave={() => setIsUnpinHovered(null)}>
                    {isPinned ? (
                      <img src={isUnpinHovered === session.id ? "/icons/keep-off-active.svg" : "/icons/keep-off-default.svg"} alt="Unpin" className="menu-icon" style={{ width: '24px', height: '24px', objectFit: 'contain' }} />
                    ) : ( <PinIcon className="menu-icon" /> )}
                    {isPinned ? 'Unpin' : 'Pin'}
                  </div>
                  
                  <div className="menu-item" onClick={(e) => { e.stopPropagation(); handleRenameClick(session.id); }}>
                    <RenameIcon className="menu-icon" /> Rename
                  </div>
                  
                  <div className="menu-item" onClick={(e) => handleDownload(session.id)}><DownloadIcon className="menu-icon" /> Download</div>
                  <div className="menu-divider"></div>
                  <div className="menu-item delete" onClick={() => { setSessionToDelete(session.id); setIsDeleteDialogOpen(true); }}>
                    <DeleteIcon className="menu-icon" /> Delete
                  </div>
                </div>, document.body
              )}
            </div>
          );
        })}
      </div>

      <DialogBox isOpen={isDeleteDialogOpen} title="Delete saved session?" content="This action will delete saved session" confirmLabel="Continue" onConfirm={handleDeleteConfirm} onCancel={() => setIsDeleteDialogOpen(false)} />
      
      <DialogBox isOpen={isAgentWarningOpen} title="No Agent Selected" content="Please select an agent from the dropdown before starting a new session." confirmLabel="Ok" cancelLabel="" onConfirm={() => setIsAgentWarningOpen(false)} onCancel={() => setIsAgentWarningOpen(false)} />
      
      <DialogBox 
        isOpen={isRenameDialogOpen} 
        title="Rename this session" 
        content={
          <input 
            type="text" 
            value={newNameInput} 
            onChange={(e) => setNewNameInput(e.target.value)} 
            placeholder="Enter session name"
            style={{ 
              width: '100%', 
              padding: '8px 12px', 
              fontSize: '14px', 
              border: '2px solid #1976d2', 
              borderRadius: '4px', 
              outline: 'none',
              marginTop: '8px'
            }}
          />
        } 
        confirmLabel="Rename" 
        onConfirm={handleRenameConfirm} 
        onCancel={() => setIsRenameDialogOpen(false)}
        isConfirmDisabled={newNameInput.trim().length === 0} 
      />

      {toast.visible && createPortal(<div className="side-panel-toast">{toast.message}</div>, document.body)}
    </div>
  );
};