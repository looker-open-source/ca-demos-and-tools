// src/components/TopBanner.tsx
import React from 'react';
import { Box, Typography, Stack, Tooltip, IconButton } from '@mui/material';
import { InfoOutlined } from '@mui/icons-material';
import ThemeSwitcher from './ThemeSwitcher';
import '../App.css';
import { SidePanel } from './SidePanel';

const botIconSrc = "/12227ea5e48753deae06ae4fb0ac2a2284b1b95d.png";
const routineIconSrc = "/routine.png";
const SIDEBAR_WIDTH = 256; 

// No Props Interface needed anymore!

const TopBanner = () => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
      <Box component="header" className="top-banner">
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          className="top-banner-content"
        >
          <Stack direction="row" alignItems="center" spacing={1}>
            <img src={botIconSrc} alt="Agent Bot Logo" className="top-banner-logo"/>
            <Typography className="top-banner-title">
              Agent Development Kit
            </Typography>
          </Stack>

          <Stack direction="row" alignItems="center" spacing={0.5}>
            {/* Cleaner! No theme props passed here. */}
            <ThemeSwitcher iconSrc={routineIconSrc} />
          </Stack>
        </Stack>
      </Box>

      <Box className="case-bar">
        <SidePanel /> 
        <Stack direction="row" alignItems="center" className="case-bar-content" sx={{ px: { xs: 2, md: 3 } }}>
          <Typography className="case-bar-text">
            Cases Eng Default Pool
          </Typography>
          <Tooltip title="Session ID: aad0abf9..." arrow placement="bottom">
            <IconButton size="small" className="case-bar-icon-btn">
              <InfoOutlined fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>
    </Box>
  );
};

export default TopBanner;