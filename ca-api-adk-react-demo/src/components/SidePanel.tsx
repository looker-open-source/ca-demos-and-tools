import React, { useState } from 'react';
import { Add as AddIcon, ArrowDropDown as ArrowDropDownIcon } from '@mui/icons-material';

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

// --- Dummy Data (Included in the component) ---
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

// --- Component Implementation ---
// NOTE: Since the logic is internal, we don't need props for data/handlers here.
export const SidePanel: React.FC = () => {
  // Internal State Management
  const [sessionHistory] = useState<Session[]>(DUMMY_SESSIONS);
  const [agentOptions] = useState<AgentOption[]>(DUMMY_AGENTS);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(DUMMY_SESSIONS[0]?.id || null);
  const [selectedAgentId, setSelectedAgentId] = useState(DUMMY_AGENTS[0]?.id || '');

  const handleAgentChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const newAgentId = event.target.value;
    setSelectedAgentId(newAgentId);
    console.log(`Agent selected: ${newAgentId}`);
  };

  const handleNewSession = () => {
    // Logic to create a new session and set it as active
    console.log('New Session initiated!');
    setActiveSessionId(null); // Clear active session state
  };

  const handleSessionClick = (sessionId: string) => {
    setActiveSessionId(sessionId);
    console.log(`Session clicked: ${sessionId}`);
  };

  return (
    <div className="side-panel-container">
      
      <div className="side-panel-header-section">
        
        {/* Agent Dropdown Section */}
        <div className="side-panel-agent-dropdown">
          <select 
            className="side-panel-dropdown-selector" 
            onChange={handleAgentChange} 
            value={selectedAgentId}
          >
            {agentOptions.map(agent => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </div>

        {/* New Session Button */}
        <button 
          className="side-panel-new-session-button" 
          onClick={handleNewSession}
        >
          <AddIcon style={{ fontSize: '1.25rem' }} />
          New Session
        </button>

        {/* Session History Header */}
        <h3 className="side-panel-history-header">
          Session History
        </h3>

      </div>

      {/* Session History List (Scrollable Area) */}
      <div className="side-panel-session-list-container">
        {sessionHistory.map((session) => {
          const isActive = session.id === activeSessionId;
          const itemClassName = `side-panel-session-item ${isActive ? 'active' : ''}`;

          return (
            <div
              key={session.id}
              className={itemClassName}
              onClick={() => handleSessionClick(session.id)}
            >
              <div className="side-panel-session-title">{session.title}</div>
              <div className="side-panel-session-timestamp">{session.timestamp}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};