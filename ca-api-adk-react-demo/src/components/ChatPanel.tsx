import React, { useRef, useEffect, useState } from 'react';
import {
  Box, Typography, IconButton, Tooltip, 
  TextField, InputAdornment, Stack, Chip, Grid
} from '@mui/material';
import {
  InfoOutlined, AttachFile, Mic, MoreVert, InsertDriveFile
} from '@mui/icons-material';
// Import the specific service we created
import { chatService } from '../services/clientService'; 
import '../App.css';

// --- Types ---
export interface Message {
  role: 'user' | 'bot';
  text: string;
}

interface ChatPanelProps {
  // We removed internal state props since this component is now "smart"
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
const SESSION_ID = "a2b693fd-58b9-4b15-99af-f29c1187e33d"; // Constant ID

const ChatPanel: React.FC<ChatPanelProps> = ({ onToggleRightPanel }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // --- Internal State ---
  const [messages, setMessages] = useState<Message[]>([]);
  const [userInput, setUserInput] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<any[]>([]);
  const [isSending, setIsSending] = useState(false);

  // --- Handlers ---

  const handleSendMessage = async () => {
    // 1. Validation
    if (!userInput.trim() && selectedFiles.length === 0) return;
    if (isSending) return;

    const currentText = userInput;

    // 2. Optimistic Update (Show User Message Immediately)
    const newUserMsg: Message = { role: 'user', text: currentText };
    setMessages((prev) => [...prev, newUserMsg]);
    
    // 3. Reset Inputs & Set Loading
    setUserInput('');
    setSelectedFiles([]);
    setIsSending(true);

    try {
      const response = await chatService.sendUserMessage(currentText, SESSION_ID);
      
      console.log("API Response:", response);

      // 5. Handle Response
      let botText = "Received empty response";
      
      // Adapt this check to match your exact API response structure
      if (response?.parts?.[0]?.text) {
        botText = response.parts[0].text;
      } else if (typeof response === 'string') {
        botText = response;
      }

      setMessages((prev) => [...prev, { role: 'bot', text: botText }]);

    } catch (error) {
      console.error("API Error:", error);
      setMessages((prev) => [...prev, { role: 'bot', text: "Error: Could not reach agent." }]);
    } finally {
      setIsSending(false);
    }
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

  // Helper to click suggestion card
  const handleSuggestionClick = (text: string) => {
    setUserInput(text);
    // Optional: handleSendMessage(); // Uncomment to send immediately on click
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
            <IconButton onClick={onToggleRightPanel} className="inspector-tab-btn" disableRipple>
               <img src={tabIconSrc} alt="Tab" className="inspector-toggle-icon" />
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
              <div 
                key={i} 
                className="message-row" 
                style={{ textAlign: msg.role === 'user' ? 'right' : 'left' }}
              >
                <div className={`message-card ${msg.role}`}>
                  <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                    {msg.text}
                  </Typography>
                </div>
              </div>
            ))}
            
            {isSending && (
               <div className="message-row" style={{ textAlign: 'left' }}>
                 <Typography variant="caption" sx={{ ml: 2, color: 'var(--text-secondary)' }}>
                   Thinking...
                 </Typography>
               </div>
            )}
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
            placeholder="Type a message..."
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSending}
            className="chat-input-field" 
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <Stack direction="row">
                    <input
                      type="file"
                      multiple
                      hidden
                      ref={fileInputRef}
                      onChange={handleFileSelect}
                    />
                    <Tooltip title="Upload">
                        <IconButton onClick={() => fileInputRef.current?.click()}>
                            <AttachFile />
                        </IconButton>
                    </Tooltip>
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