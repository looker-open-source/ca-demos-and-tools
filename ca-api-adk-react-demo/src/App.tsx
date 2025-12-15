import React, { useEffect } from 'react';
import logo from './logo.svg';
import './App.css';
import { ComponentsProvider } from '@looker/components-providers';
import { apiClient } from './services/clientService';
import { Box, Typography } from '@mui/material';
import TopBanner from './components/TopBanner';

function App() {
  // 2. Use useEffect with an empty dependency array [] to run once on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        // We call the generic get. 
        // Note: Your clientService currently hardcodes the URL to '/list-apps' 
        // and handles the console.log internally.
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
         <Box sx={{ minHeight: '100vh', bgcolor: '#f9fafb' }}>
      <TopBanner />
      
      {/* Content to show layout context */}
      <Box sx={{ maxWidth: '1280px', mx: 'auto', px: { xs: 2, sm: 3, lg: 4 }, py: 6 }}>
        <Typography variant="h4" component="h1" fontWeight="bold" gutterBottom color="text.primary">
          Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
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