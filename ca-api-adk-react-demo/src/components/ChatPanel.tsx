import React, { useRef, useEffect } from 'react';
import {
  Box, Typography, IconButton, Tooltip, Card, 
  TextField, InputAdornment, Stack, Chip, Grid
} from '@mui/material';
import {
  InfoOutlined, AttachFile, Mic, MoreVert, InsertDriveFile
} from '@mui/icons-material';
import '../App.css'; // Ensure CSS is imported

// --- Types ---
export interface Message {
  role: 'user' | 'bot';
  text: string;
}

interface ChatPanelProps {
  messages: Message[];
  userInput: string;
  selectedFiles: any[];
  onUserInputChange: (val: string) => void;
  onSendMessage: () => void;
  onToggleRightPanel?: () => void;
}

// --- Constants ---
const SUGGESTIONS = [
  "Show the top areas of improvement for a specific workflow",
  "Show the top areas of improvement for a specific workflow",
  "Identify quality gaps for a specific customer segment",
  "Generate a quality report for a workflow by vendor partner"
];

const tabIconSrc = "/Tab.png";

const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  userInput,
  selectedFiles,
  onUserInputChange,
  onSendMessage,
  onToggleRightPanel
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logic
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSendMessage();
    }
  };

  return (
    <div className="chat-panel-container">

      {/* 1. Header Bar */}
      <div className="chat-header-bar">
        <Stack direction="row" alignItems="center" justifyContent="space-between" width="100%">
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="subtitle2" sx={{ fontWeight: 500, color: 'var(--text-primary)' }}>
              Cases Eng Default Pool
            </Typography>
            <IconButton size="small" sx={{ color: 'var(--text-secondary)' }}>
              <InfoOutlined fontSize="small" />
            </IconButton>
          </Stack>
          
          <Tooltip title="Toggle Inspector">
            <IconButton onClick={onToggleRightPanel} sx={{ p: 0 }}>
               <img src={tabIconSrc} alt="Tab" style={{ width: 24, height: 24 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      </div>

      {/* 2. Scrollable Content Area */}
      <div className="chat-content-area" ref={scrollRef}>
        
        {messages.length === 0 ? (
          // --- ZERO STATE (Welcome) ---
          <div className="welcome-container">
            <div className="welcome-content-wrapper">
              
              <div style={{ textAlign: 'left' }}>
                <h1 className="welcome-text-hi">Hi,</h1>
                <h1 className="welcome-text-subtitle">What can I help you with today?</h1>
              </div>

              {/* Grid V2 Syntax (Material UI v6) */}
              <Grid container spacing={2}>
                {SUGGESTIONS.map((text, idx) => (
                  <Grid size={{ xs: 12, sm: 6, md: 3 }} key={idx}>
                    <div 
                      className="suggestion-card" 
                      onClick={() => onUserInputChange(text)}
                    >
                      <span className="suggestion-text">{text}</span>
                    </div>
                  </Grid>
                ))}
              </Grid>

            </div>
          </div>
        ) : (
          // --- MESSAGES ---
          <div className="welcome-content-wrapper" style={{ marginTop: '1rem' }}>
            {messages.map((msg, i) => (
              <div 
                key={i} 
                className="message-row" 
                style={{ textAlign: msg.role === 'user' ? 'right' : 'left' }}
              >
                <div className={`message-card ${msg.role}`}>
                  <Typography variant="body1">{msg.text}</Typography>
                </div>
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
                <Chip key={i} label={f.file.name} icon={<InsertDriveFile />} />
              ))}
            </Stack>
          )}

          <TextField
            fullWidth
            placeholder="Type a message..."
            value={userInput}
            onChange={(e) => onUserInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            className="chat-input-field" // Applied styling class
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <Stack direction="row">
                    <Tooltip title="Upload"><IconButton><AttachFile /></IconButton></Tooltip>
                    <Tooltip title="Mic"><IconButton><Mic /></IconButton></Tooltip>
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