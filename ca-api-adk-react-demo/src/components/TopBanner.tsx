// src/components/TopBanner.tsx
import React from 'react';
import { Box, Typography, Stack } from '@mui/material';
import ThemeSwitcher from './ThemeSwitcher';
import '../App.css';

const botIconSrc = "/12227ea5e48753deae06ae4fb0ac2a2284b1b95d.png";
const routineIconSrc = "/routine.png";

const TopBanner = () => {
  return (
    <Box component="header" className="top-banner">
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        className="top-banner-content"
      >
        {/* Left Side: Logo & Title */}
        <Stack direction="row" alignItems="center" spacing={1}>
          <img src={botIconSrc} alt="Agent Bot Logo" className="top-banner-logo" />
          <Typography className="top-banner-title">
            Agent Development Kit
          </Typography>
        </Stack>

        {/* Right Side: Theme Switcher */}
        <Stack direction="row" alignItems="center" spacing={0.5}>
          <ThemeSwitcher iconSrc={routineIconSrc} />
        </Stack>
      </Stack>
    </Box>
  );
};

export default TopBanner;