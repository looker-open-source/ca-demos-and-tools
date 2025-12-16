// src/components/ThemeSwitcher.tsx
import React, { useState, MouseEvent } from 'react';
import {
  IconButton, Menu, MenuItem, ListItemIcon, Box, Typography, Stack
} from '@mui/material';
import {
  WbSunnyOutlined, Brightness2Outlined, PaletteOutlined, Check, ArrowDropDown
} from '@mui/icons-material';
import { useAppTheme, ThemeType } from '../context/ThemeContext'; // Import Hook
import '../App.css';

interface ThemeOption {
  id: ThemeType;
  label: string;
  icon: React.ReactNode;
}

const themeOptions: ThemeOption[] = [
  { id: 'light', label: 'Light Theme', icon: <WbSunnyOutlined fontSize="small" /> },
  { id: 'dark', label: 'Dark Theme', icon: <Brightness2Outlined fontSize="small" /> },
  { id: 'custom', label: 'Custom Theme', icon: <PaletteOutlined fontSize="small" /> },
];

interface ThemeSwitcherProps {
  iconSrc: string;
}

const ThemeSwitcher = ({ iconSrc }: ThemeSwitcherProps) => {
  // 1. USE THE HOOK instead of props/state
  const { themeMode, setThemeMode } = useAppTheme();
  
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleClick = (event: MouseEvent<HTMLElement>) => setAnchorEl(event.currentTarget);
  const handleClose = () => setAnchorEl(null);

  const handleMenuItemClick = (newTheme: ThemeType) => {
    setThemeMode(newTheme); // Uses context function
    handleClose();
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={0}>
        <IconButton size="small">
          <img src={iconSrc} alt="Theme Icon" className="theme-switcher-icon" />
        </IconButton>

        <IconButton
          onClick={handleClick}
          size="small"
          className="theme-switcher-arrow-btn"
        >
          <ArrowDropDown fontSize="small" />
        </IconButton>
      </Stack>

      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        className="theme-switcher-menu"
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        {themeOptions.map((option) => {
          const isSelected = themeMode === option.id; // Compare with Context value
          return (
            <MenuItem
              key={option.id}
              onClick={() => handleMenuItemClick(option.id)}
              selected={isSelected}
              className="theme-switcher-menu-item"
            >
              <Box className="theme-switcher-item-content">
                <ListItemIcon className="theme-switcher-option-icon">
                  {option.icon}
                </ListItemIcon>
                <Typography variant="body2">{option.label}</Typography>
              </Box>
              {isSelected && (
                <ListItemIcon className="theme-switcher-check">
                  <Check fontSize="small" />
                </ListItemIcon>
              )}
            </MenuItem>
          );
        })}
      </Menu>
    </Box>
  );
};

export default ThemeSwitcher;