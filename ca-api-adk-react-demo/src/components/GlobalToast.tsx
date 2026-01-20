import React, { useState, useEffect } from 'react';
import { Snackbar, Button, IconButton } from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';
import { toastManager } from '../utils/ToastManager';

export const GlobalToast: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    // Register listener
    toastManager.register((msg, type) => {
      setMessage(msg);
      setOpen(true);
    });

    return () => {
      toastManager.unregister();
    };
  }, []);

  const handleClose = (event?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }
    setOpen(false);
  };

  // The "Dismiss" or "Retry" action button style
  const action = (
    <React.Fragment>
      <Button 
        size="small" 
        onClick={(e) => handleClose(e)}
        sx={{ 
          color: '#8ab4f8', // Light blue color from your image
          fontWeight: 600,
          textTransform: 'none',
          fontSize: '0.9rem'
        }}
      >
        Dismiss
      </Button>
      <IconButton
        size="small"
        aria-label="close"
        color="inherit"
        onClick={handleClose}
        sx={{ ml: 1 }}
      >
        <CloseIcon fontSize="small" sx={{ color: '#fff' }} />
      </IconButton>
    </React.Fragment>
  );

  return (
    <Snackbar
      open={open}
      autoHideDuration={6000}
      onClose={handleClose}
      message={message}
      action={action}
      // UPDATED POSITION: Bottom Left
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      ContentProps={{
        sx: {
          backgroundColor: '#323232', // Dark grey background matching image
          color: '#ffffff',           // White text
          borderRadius: '4px',        // Rounded corners
          boxShadow: '0px 3px 5px -1px rgba(0,0,0,0.2), 0px 6px 10px 0px rgba(0,0,0,0.14), 0px 1px 18px 0px rgba(0,0,0,0.12)',
          fontSize: '0.95rem',
          fontWeight: 400,
          fontFamily: '"Google Sans", Roboto, Arial, sans-serif',
          minWidth: '300px'
        }
      }}
    />
  );
};