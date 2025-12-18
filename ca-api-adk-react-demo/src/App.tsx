import React, { useEffect, useMemo, useState } from 'react';
import { ComponentsProvider } from '@looker/components-providers';
import { apiClient } from './services/clientService';
import { Box, ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import TopBanner from './components/TopBanner';
import { AppThemeProvider, useAppTheme } from './context/ThemeContext';
import './App.css';

import ChatPanel, { Message } from './components/ChatPanel';
import { SidePanel } from './components/SidePanel';

const AppContent = () => {
  const { themeMode } = useAppTheme();

  // --- Chat State ---
  const [messages, setMessages] = useState<Message[]>([]);
  const [userInput, setUserInput] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<any[]>([]);

  // --- Data Fetching ---
  useEffect(() => {
    const fetchData = async () => {
      try {
        await apiClient.get('/list-apps');
      } catch (error) {
        console.error("Failed to fetch initial data:", error);
      }
    };
    fetchData();
  }, []);

  // --- Handlers ---

  const handleSendMessage = () => {
    if (!userInput.trim() && selectedFiles.length === 0) return;

    // 1. Add User Message
    const newUserMsg: Message = {
      role: 'user',
      text: userInput,
    };

    setMessages((prev) => [...prev, newUserMsg]);
    
    // 2. Reset Inputs
    setUserInput('');
    setSelectedFiles([]);

    // 3. Simulate Bot Response
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          text: "I received your message! This is a simulated response."
        }
      ]);
    }, 1000);
  };

  const handleUserInputChange = (val: string) => {
    setUserInput(val);
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

  // --- Theme Setup ---
  const muiTheme = useMemo(() => createTheme({
    palette: {
      mode: themeMode === 'dark' ? 'dark' : 'light',
      primary: { main: '#1976d2' },
    },
    typography: {
      fontFamily: '"Google Sans", Roboto, Arial, sans-serif',
    }
  }), [themeMode]);

  return (
    <ThemeProvider theme={muiTheme}>
      <CssBaseline />
      <ComponentsProvider>
        <div className="App" data-theme={themeMode}>
          
          <Box className="app-layout" sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

            {/* 1. Top Banner (Logo Header) */}
            <TopBanner />
            

            {/* 2. Main Workspace */}
            <Box sx={{ display: 'flex', flexGrow: 1, overflow: 'hidden' }}>
              <SidePanel />

              {/* Chat Panel (Fills the screen) */}
              <Box sx={{ flexGrow: 1, height: '100%', overflow: 'hidden', position: 'relative' }}>
                <ChatPanel
                  messages={messages}
                  userInput={userInput}
                  selectedFiles={selectedFiles}
                  onUserInputChange={handleUserInputChange}
                  onSendMessage={handleSendMessage}
                  // Optional handlers (pass dummy functions if not used yet)
                  onToggleRightPanel={() => console.log('Toggle Right Panel')}
                />
              </Box>

            </Box>

          </Box>
        </div>
      </ComponentsProvider>
    </ThemeProvider>
  );
};

function App() {
  return (
    <AppThemeProvider>
      <AppContent />
    </AppThemeProvider>
  );
}

export default App;