import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { 
  Add as AddIcon, 
  MoreVert as MoreVertIcon,
  PushPinOutlined as PinIcon,
  EditOutlined as RenameIcon,
  FileDownloadOutlined as DownloadIcon,
  DeleteOutline as DeleteIcon,
  ArrowDropDown as ArrowDropDownIcon
} from '@mui/icons-material';

// --- Types ---
interface Session {
  id: string;
  title: string;
  timestamp: string;
}

interface AgentOption {
  id: string;
  name: string;
}

const DUMMY_SESSIONS: Session[] = [
  { id: '1', title: 'Cases Eng Default Pool ...', timestamp: '2 minutes ago' },
  { id: '2', title: 'Initial Agent greeting', timestamp: '1 hour ago' },
  { id: '3', title: 'JSON output validation', timestamp: 'Yesterday' },
];

const DUMMY_AGENTS: AgentOption[] = [
  { id: 'code_execution', name: 'code_execution' },
  { id: 'public', name: 'public' },
  { id: 'hello_world', name: 'hello_world' },
  { id: 'default_pool', name: 'default_pool' },
];

export const SidePanel: React.FC = () => {
  const [sessionHistory] = useState<Session[]>(DUMMY_SESSIONS);
  const [agentOptions] = useState<AgentOption[]>(DUMMY_AGENTS);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(DUMMY_SESSIONS[0]?.id || null);
  const [selectedAgentId, setSelectedAgentId] = useState(DUMMY_AGENTS[0]?.id || '');
  
  // States for Portal Menus
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [agentMenuOpen, setAgentMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });

  const toggleAgentMenu = (e: React.MouseEvent) => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setMenuPos({ top: rect.bottom + 5, left: rect.left });
    setAgentMenuOpen(!agentMenuOpen);
    setMenuOpenId(null); // Close session menu if open
  };

  const toggleSessionMenu = (e: React.MouseEvent<HTMLButtonElement>, id: string) => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setMenuPos({ top: rect.top, left: rect.right + 10 });
    setMenuOpenId(menuOpenId === id ? null : id);
    setAgentMenuOpen(false); // Close agent menu if open
  };

  const closeMenus = () => {
    setMenuOpenId(null);
    setAgentMenuOpen(false);
  };

  const selectedAgent = agentOptions.find(a => a.id === selectedAgentId);

  return (
    <div className="side-panel-container" onClick={closeMenus}>
      <div className="side-panel-header-section">
        
        {/* CUSTOM AGENT DROPDOWN */}
        <div className="agent-selector-wrapper" onClick={toggleAgentMenu}>
          <span className="agent-label">Agent</span>
          <span className="agent-name-underlined">{selectedAgent?.name}</span>
          <ArrowDropDownIcon className="agent-arrow-icon" />
          
          {agentMenuOpen && createPortal(
            <div 
              className="side-panel-dropdown-toolbar-menu"
            >
              {agentOptions.map(agent => (
                <div 
                  key={agent.id} 
                  className="dropdown-item"
                  onClick={() => { setSelectedAgentId(agent.id); setAgentMenuOpen(false); }}
                >
                  {agent.name}
                </div>
              ))}
            </div>,
            document.body
          )}
        </div>

        <button className="side-panel-new-session-button" onClick={() => console.log('New Session Started')}>
          <AddIcon style={{ fontSize: '1.25rem' }} />
          New Session
        </button>

        <h3 className="side-panel-history-header">Session History</h3>
      </div>

      <div className="side-panel-session-list-container">
        {sessionHistory.map((session) => {
          const isActive = session.id === activeSessionId;
          const isMenuOpen = menuOpenId === session.id;

          return (
            <div
              key={session.id}
              className={`side-panel-session-item ${isActive ? 'active' : ''}`}
              onClick={() => { setActiveSessionId(session.id); closeMenus(); }}
            >
              <div className="side-panel-content-wrapper">
                <div className="side-panel-text-content">
                  <div className="side-panel-session-title">{session.title}</div>
                  <div className="side-panel-session-timestamp">{session.timestamp}</div>
                </div>

                <button 
                  className={`side-panel-action-dots ${isMenuOpen ? 'visible' : ''}`}
                  onClick={(e) => toggleSessionMenu(e, session.id)}
                >
                  <MoreVertIcon fontSize="small" />
                </button>
              </div>

              {isMenuOpen && createPortal(
                <div 
                    className="side-panel-toolbar-menu"
                    style={{ position: 'fixed', top: menuPos.top, left: menuPos.left, zIndex: 99999 }}
                    onClick={(e) => e.stopPropagation()}>
                    <div className="menu-item" onClick={closeMenus}><PinIcon className="menu-icon" /> Pin</div>
                    <div className="menu-item" onClick={closeMenus}><RenameIcon className="menu-icon" /> Rename</div>
                    <div className="menu-item" onClick={closeMenus}><DownloadIcon className="menu-icon" /> Download</div>
                    <div className="menu-divider"></div>
                    <div className="menu-item" onClick={closeMenus}><DeleteIcon className="menu-icon" /> Delete</div>
                </div>,
                document.body
                )}
            </div>
          );
        })}
      </div>
    </div>
  );
};