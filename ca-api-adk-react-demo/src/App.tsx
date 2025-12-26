import React, { useEffect, useMemo, useState } from 'react';
import { ComponentsProvider } from '@looker/components-providers';
import { Box, ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import TopBanner from './components/TopBanner';
import { AppThemeProvider, useAppTheme } from './context/ThemeContext';
import './App.css';

import ChatPanel from './components/ChatPanel';
import { SidePanel } from './components/SidePanel';
import { SessionProvider } from './context/SessionContext';
import RightPanel from './components/RightPanel';
import { GlobalToast } from './components/GlobalToast';

const AppContent = () => {
  const { themeMode, customTheme } = useAppTheme();
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);

useEffect(() => {
    const root = document.documentElement;
    if (themeMode === 'custom') {
      root.style.setProperty('--bg-default', customTheme.bgColor);
      root.style.setProperty('--bg-paper', '#ffffff');
      
      root.style.setProperty('--font-family', `"${customTheme.fontFamily}", "Google Sans", Roboto, Arial, sans-serif`);
    } else {
      root.style.removeProperty('--bg-default');
      root.style.removeProperty('--bg-paper');
      root.style.removeProperty('--font-family');
    }
  }, [themeMode, customTheme]);

  // MUI Theme Setup
  const muiTheme = useMemo(() => createTheme({
    palette: {
      mode: themeMode === 'dark' ? 'dark' : 'light',
      primary: { main: '#1976d2' },
    },
    typography: {
      fontFamily: themeMode === 'custom' 
        ? `"${customTheme.fontFamily}", "Google Sans", Roboto, Arial, sans-serif`
        : '"Google Sans", Roboto, Arial, sans-serif',
    }
  }), [themeMode, customTheme]);

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
          
          {/* 2. Add GlobalToast here, inside the theme/component providers but outside layout boxes */}
          <GlobalToast />
          
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