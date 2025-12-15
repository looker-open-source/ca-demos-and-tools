import React, { useEffect } from 'react';
import './App.css';
import { ComponentsProvider } from '@looker/components-providers';
import { apiClient } from './services/clientService';
import { Box, Typography } from '@mui/material';
import TopBanner from './components/TopBanner';

function App() {
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

  return (
    <ComponentsProvider>
      <div className="App">
        {/* <header className="App-header">
          <img src={logo} className="App-logo" alt="logo" />
          <p>
            Edit <code>src/App.tsx</code> and save to reload.
          </p>
          <a
            className="App-link"
            href="https://reactjs.org"
            target="_blank"
            rel="noopener noreferrer"
          >
            Learn React
          </a>
        </header> */}
        <Box className="app-layout">
          <TopBanner />
          
          {/* Replaced layout context Box styles */}
          <Box className="dashboard-container">
            <Typography 
              variant="h4" 
              component="h1" 
              className="dashboard-heading"
            >
              Dashboard
            </Typography>
            
            <Typography 
              variant="body1" 
              className="dashboard-text"
            >
              The top banner component sits above your main navigation or content. 
              It is fully responsive, uses Material UI components, and is dismissible.
            </Typography>
          </Box>
        </Box>

      </div>
    </ComponentsProvider>
  );
}

export default App;