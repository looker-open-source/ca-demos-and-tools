// src/App.tsx
import React, { useEffect, useMemo } from 'react';
import { ComponentsProvider } from '@looker/components-providers';
import { apiClient } from './services/clientService';
import { Box, Typography, ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import TopBanner from './components/TopBanner';
import { SidePanel } from './components/SidePanel';
import { AppThemeProvider, useAppTheme } from './context/ThemeContext'; // Import Provider & Hook
import './App.css';

// 1. Create a child component that handles the UI and MUI Theme
const AppContent = () => {
  const { themeMode } = useAppTheme(); // Consuming the context

  // Data Fetching
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

  // MUI Theme setup
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
        {/* The data-theme attribute now comes from Context */}
        <div className="App" data-theme={themeMode}>
          <Box className="app-layout">
            <TopBanner />
            <Box>
              <Typography variant="body1" className="dashboard-text">
                This app is now using React Context API!
                <br/>
                Current Theme: <strong>{themeMode}</strong>
              </Typography>
            </Box>

          </Box>
        </div>
      </ComponentsProvider>
    </ThemeProvider>
  );
};

// 2. Main App Component wraps everything in the Provider
function App() {
  return (
    <AppThemeProvider>
      <AppContent />
    </AppThemeProvider>
  );
}

export default App;

