import React, { useState, MouseEvent } from 'react';
import {
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  Box,
  Typography,
  Stack
} from '@mui/material';
import {
  WbSunnyOutlined,
  Brightness2Outlined,
  PaletteOutlined,
  Check,
  ArrowDropDown
} from '@mui/icons-material';
import '../App.css';

type ThemeType = 'light' | 'dark' | 'custom';

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
  const [theme, setTheme] = useState<ThemeType>('custom');
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleClick = (event: MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleThemeChange = (newTheme: ThemeType) => {
    setTheme(newTheme);
    handleClose();
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={0}>

        {/* 1. The Routine Icon */}
        <IconButton size="small">
          <img
            src={iconSrc}
            alt="Theme Icon"
            className="theme-switcher-icon"
          />
        </IconButton>

        {/* 2. The Arrow Button */}
        <IconButton
          onClick={handleClick}
          size="small"
          className="theme-switcher-arrow-btn"
          aria-controls={open ? 'theme-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
        >
          <ArrowDropDown fontSize="small" />
        </IconButton>
      </Stack>

      {/* 3. The Menu */}
      <Menu
        anchorEl={anchorEl}
        id="theme-menu"
        open={open}
        onClose={handleClose}
        onClick={handleClose}
        // Applying the class to the root menu container to target inner Paper via CSS
        className="theme-switcher-menu"
        PaperProps={{
          elevation: 0,
          // Styles are now handled by .theme-switcher-menu .MuiPaper-root in CSS
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        {themeOptions.map((option) => {
          const isSelected = theme === option.id;
          return (
            <MenuItem
              key={option.id}
              onClick={() => handleThemeChange(option.id)}
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