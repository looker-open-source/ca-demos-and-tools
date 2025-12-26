import React, { useRef, useEffect, useState } from 'react';
import {
  Typography, IconButton, Tooltip, 
  TextField, InputAdornment, Stack, Chip, Grid, Avatar
} from '@mui/material';
import {
  InfoOutlined, AttachFile, Mic, MoreVert, InsertDriveFile,
  SmartToyOutlined, PersonOutline
} from '@mui/icons-material';
import { useSession } from '../context/SessionContext';
import '../App.css'; 

// --- Types ---
export interface Message {
  role: 'user' | 'bot';
  text: string;
}

interface ChatPanelProps {
  onToggleRightPanel?: () => void;
}

const SUGGESTIONS = [
  "Show the top areas of improvement for a specific workflow",
  "Show the top areas of improvement for a specific workflow",
  "Identify quality gaps for a specific customer segment",
  "Generate a quality report for a workflow by vendor partner"
];

const tabIconSrc = "/Tab.png";

const ChatPanel: React.FC<ChatPanelProps> = ({ onToggleRightPanel }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { activeSessionId, getSessionName, messages, isSending, sendMessage } = useSession();

  const [userInput, setUserInput] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<any[]>([]);

  const handleSendMessage = async () => {
    if (!userInput.trim() && selectedFiles.length === 0) return;
    if (isSending) return;
    if (!activeSessionId) {
        alert("Please select or create a session from the side panel first.");
        return;
    }

    // Call the centralized send function
    await sendMessage(userInput, selectedFiles);
    
    // Clear inputs immediately
    setUserInput('');
    setSelectedFiles([]);
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      const newFiles = Array.from(event.target.files).map(file => ({
        file,
        name: file.name
      }));
      setSelectedFiles((prev) => [...prev, ...newFiles]);
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSuggestionClick = (text: string) => {
    setUserInput(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isSending]);

  const sessionDisplayName = activeSessionId 
    ? getSessionName(activeSessionId, `Session: ${activeSessionId.substring(0,8)}...`)
    : 'No Active Session';
  return (
    <div className="chat-panel-container">

      {/* 1. Header Bar */}
      <div className="chat-header-bar">
        <Stack direction="row" alignItems="center" justifyContent="space-between" width="100%">
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="subtitle2" sx={{ fontWeight: 500, color: 'var(--text-primary)' }}>
              {sessionDisplayName}
            </Typography>
            <IconButton size="small" sx={{ color: 'var(--text-secondary)' }}>
              <InfoOutlined fontSize="small" />
            </IconButton>
          </Stack>
          
          <Tooltip title="Toggle Inspector">
            <IconButton onClick={onToggleRightPanel} className="inspector-tab-btn" disableRipple>
               <img src={tabIconSrc} alt="Tab" className="inspector-toggle-icon" />
            </IconButton>
          </Tooltip>
        </Stack>
      </div>

      {/* 2. Scrollable Content Area */}
      <div className="chat-content-area" ref={scrollRef}>
        
        {messages.length === 0 ? (
          <div className="welcome-container">
            <div className="welcome-content-wrapper">
              <div style={{ textAlign: 'left' }}>
                <h1 className="welcome-text-hi">Hi,</h1>
                <h1 className="welcome-text-subtitle">What can I help you with today?</h1>
              </div>

              <Grid container spacing={2}>
                {SUGGESTIONS.map((text, idx) => (
                  <Grid size={{ xs: 12, sm: 6, md: 3 }} key={idx}>
                    <div 
                      className="suggestion-card" 
                      onClick={() => handleSuggestionClick(text)}
                    >
                      <span className="suggestion-text">{text}</span>
                    </div>
                  </Grid>
                ))}
              </Grid>
            </div>
          </div>
        ) : (
          <div className="welcome-content-wrapper" style={{ marginTop: '1rem' }}>
            {messages.map((msg, i) => (
              <div key={i} className={`message-row ${msg.role}`}>
                {msg.role === 'bot' && (
                  <Avatar className="chat-avatar bot">
                    <SmartToyOutlined fontSize="small" />
                  </Avatar>
                )}
                <div className={`message-card ${msg.role}`}>
                  <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                    {msg.text}
                  </Typography>
                </div>
                {msg.role === 'user' && (
                   <Avatar className="chat-avatar user">
                     <PersonOutline fontSize="small" />
                   </Avatar>
                )}
              </div>
            ))}
            
          </div>
        )}
      </div>

      {/* 3. Input Footer */}
      <div className="chat-input-container">
        <div className="chat-input-wrapper">
          
          {selectedFiles.length > 0 && (
            <Stack direction="row" spacing={1} mb={1}>
              {selectedFiles.map((f, i) => (
                <Chip key={i} label={f.name} onDelete={() => handleRemoveFile(i)} icon={<InsertDriveFile />} />
              ))}
            </Stack>
          )}

          <TextField
            fullWidth
            placeholder={activeSessionId ? "Type a message..." : "Select a session to start chatting"}
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSending || !activeSessionId}
            className="chat-input-field" 
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <Stack direction="row">
                    <input type="file" multiple hidden ref={fileInputRef} onChange={handleFileSelect} />
                    <Tooltip title="Upload">
                        <IconButton onClick={() => fileInputRef.current?.click()} disabled={!activeSessionId}>
                            <AttachFile />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Mic"><IconButton disabled={!activeSessionId}><Mic /></IconButton></Tooltip>
                    <IconButton><MoreVert /></IconButton>
                  </Stack>
                </InputAdornment>
              )
            }}
          />
        </div>
      </div>

    </div>
  );
};

export default ChatPanel;