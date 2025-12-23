import React, { useMemo, useState } from 'react';
import { ComponentsProvider } from '@looker/components-providers';
import { Box, ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import TopBanner from './components/TopBanner';
import { AppThemeProvider, useAppTheme } from './context/ThemeContext';
import './App.css';

import ChatPanel from './components/ChatPanel';
import { SidePanel } from './components/SidePanel';
import { SessionProvider } from './context/SessionContext';
import RightPanel from './components/RightPanel';

const AppContent = () => {
  const { themeMode } = useAppTheme();
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);

  // MUI Theme Setup
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
            <TopBanner />
            <Box sx={{ display: 'flex', flexGrow: 1, overflow: 'hidden' }}>
              <SidePanel />
              <Box sx={{ flexGrow: 1, height: '100%', overflow: 'hidden', position: 'relative' }}>
                <ChatPanel 
                  onToggleRightPanel={() => setIsInspectorOpen(!isInspectorOpen)}                
                />
              </Box>
              <RightPanel 
                isOpen={isInspectorOpen} 
                onClose={() => setIsInspectorOpen(false)} 
              />
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
      <SessionProvider>
         <AppContent />
      </SessionProvider>
    </AppThemeProvider>
  );
}

export default App;