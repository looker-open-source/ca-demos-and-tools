import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { 
  Add as AddIcon, 
  MoreVert as MoreVertIcon,
  PushPinOutlined as PinIcon,
  EditOutlined as RenameIcon,
  FileDownloadOutlined as DownloadIcon,
  DeleteOutline as DeleteIcon
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
  { id: '4', title: 'Test Session Four', timestamp: '2 days ago' },
];

const DUMMY_AGENTS: AgentOption[] = [
  { id: 'code_execution', name: 'Agent code_execution' },
  { id: 'data_analysis', name: 'Agent data_analysis' },
];

export const SidePanel: React.FC = () => {
  const [sessionHistory] = useState<Session[]>(DUMMY_SESSIONS);
  const [agentOptions] = useState<AgentOption[]>(DUMMY_AGENTS);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(DUMMY_SESSIONS[0]?.id || null);
  const [selectedAgentId, setSelectedAgentId] = useState(DUMMY_AGENTS[0]?.id || '');
  
  // State for the portal menu
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });

  const handleAgentChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedAgentId(event.target.value);
  };

  const toggleMenu = (e: React.MouseEvent<HTMLButtonElement>, id: string) => {
    e.stopPropagation();
    
    if (menuOpenId === id) {
      setMenuOpenId(null);
    } else {
      // Calculate screen position of the button to place the portal menu
      const rect = e.currentTarget.getBoundingClientRect();
      setMenuPos({
        top: rect.top,
        left: rect.right + 10 // Position 10px to the right of the dots
      });
      setMenuOpenId(id);
    }
  };

  // Close menu if user clicks elsewhere
  const closeMenu = () => setMenuOpenId(null);

  return (
    <div className="side-panel-container" onClick={closeMenu}>
      <div className="side-panel-header-section">
        <div className="side-panel-agent-dropdown">
          <select 
            className="side-panel-dropdown-selector" 
            onChange={handleAgentChange} 
            value={selectedAgentId}
          >
            {agentOptions.map(agent => (
              <option key={agent.id} value={agent.id}>{agent.name}</option>
            ))}
          </select>
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
              onClick={() => {
                setActiveSessionId(session.id);
                closeMenu();
              }}
            >
              <div className="side-panel-content-wrapper">
                <div className="side-panel-text-content">
                  <div className="side-panel-session-title">{session.title}</div>
                  <div className="side-panel-session-timestamp">{session.timestamp}</div>
                </div>

                <button 
                  className={`side-panel-action-dots ${isMenuOpen ? 'visible' : ''}`}
                  onClick={(e) => toggleMenu(e, session.id)}
                >
                  <MoreVertIcon fontSize="small" />
                </button>
              </div>

              {/* RENDER PORTAL MENU: Teleports the menu to the end of the body tag */}
              {isMenuOpen && createPortal(
                <div 
                  className="side-panel-toolbar-menu"
                  style={{ 
                    position: 'fixed', // Fixed to stay above everything
                    top: `${menuPos.top}px`,
                    left: `${menuPos.left}px`,
                    zIndex: 99999 
                  }}
                  onClick={(e) => e.stopPropagation()} // Click inside menu won't close it
                >
                  <div className="menu-item" onClick={closeMenu}><PinIcon fontSize="small" /> Pin</div>
                  <div className="menu-item" onClick={closeMenu}><RenameIcon fontSize="small" /> Rename</div>
                  <div className="menu-item" onClick={closeMenu}><DownloadIcon fontSize="small" /> Download</div>
                  <div className="menu-divider"></div>
                  <div className="menu-item delete" onClick={closeMenu}><DeleteIcon fontSize="small" /> Delete</div>
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