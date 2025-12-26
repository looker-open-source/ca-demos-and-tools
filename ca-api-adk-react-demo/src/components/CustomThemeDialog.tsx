import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Typography, Box, Stack
} from '@mui/material';
import { Check } from '@mui/icons-material';
import { useAppTheme } from '../context/ThemeContext';
import { useSession } from '../context/SessionContext';
import '../App.css';

interface CustomThemeDialogProps {
  open: boolean;
  onClose: () => void;
}

const BG_COLORS = ['#E8F0FE', '#FCE8E6', '#F3E5F5', '#E1BEE7', '#FFF9C4'];
const FONTS = [
  { name: 'Inter', desc: 'Clean & Standard' },
  { name: 'Nunito', desc: 'Rounded' },
  { name: 'DM Sans', desc: 'Geometric' },
  { name: 'Open Sans', desc: 'Neutral' },
  { name: 'Roboto', desc: 'Tech Classic' },
  { name: 'IBM Plex Sans', desc: 'Technical' },
];

const CustomThemeDialog = ({ open, onClose }: CustomThemeDialogProps) => {
  const { customTheme, setCustomTheme, setThemeMode } = useAppTheme();
  const { activeSessionId, getSessionName } = useSession();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const sessionDisplayName = activeSessionId 
    ? getSessionName(activeSessionId, `Session: ${activeSessionId.substring(0,8)}...`)
    : 'No Active Session';

  const [selectedColor, setSelectedColor] = useState(customTheme.bgColor);
  const [selectedFont, setSelectedFont] = useState(customTheme.fontFamily);
  const [selectedAvatar, setSelectedAvatar] = useState<string | null>(customTheme.userAvatar);
  const [avatarFileName, setAvatarFileName] = useState("No file chosen");

  useEffect(() => {
    if (open) {
      setSelectedColor(customTheme.bgColor);
      setSelectedFont(customTheme.fontFamily);
      setSelectedAvatar(customTheme.userAvatar);
      setAvatarFileName(customTheme.userAvatar ? "Current Avatar" : "No file chosen");
    }
  }, [open, customTheme]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setSelectedAvatar(reader.result as string); 
        setAvatarFileName(file.name);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSave = () => {
    setCustomTheme({
      bgColor: selectedColor,
      fontFamily: selectedFont,
      userAvatar: selectedAvatar 
    });
    setThemeMode('custom');
    onClose();
  };

  const handleRestore = () => {
    setSelectedColor(BG_COLORS[0]);
    setSelectedFont('Inter');
    setSelectedAvatar(null);
    setAvatarFileName("No file chosen");
  };

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      PaperProps={{ className: 'custom-theme-dialog-paper' }}
    >
      <DialogTitle className="custom-theme-dialog-title">Custom Theme</DialogTitle>
      
      <DialogContent>
        <Stack spacing={3}>
          
          {/* 1. User Avatar Row */}
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="body2" className="dialog-row-label">User Avatar</Typography>
            <Stack direction="row" alignItems="center" spacing={2} className="dialog-row-content">
              <input 
                type="file" 
                hidden 
                accept="image/*" 
                ref={fileInputRef} 
                onChange={handleFileChange} 
              />
              <Button 
                variant="contained" 
                disableElevation 
                className="choose-file-btn"
                onClick={() => fileInputRef.current?.click()} // Trigger input
              >
                Choose File
              </Button>
              <Typography variant="caption" color="text.secondary" sx={{ maxWidth: '150px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {avatarFileName}
              </Typography>
            </Stack>
          </Stack>

          {/* 2. Page Title Row */}
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="body2" className="dialog-row-label">Page Title</Typography>
            <Box className="dialog-row-content">
               <Box className="dialog-pill-input">
                 {sessionDisplayName}
               </Box>
            </Box>
          </Stack>

          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="body2" className="dialog-row-label">Body Background</Typography>
            <Stack direction="row" spacing={1} className="dialog-row-content">
              {BG_COLORS.map((color) => (
                <Box
                  key={color}
                  onClick={() => setSelectedColor(color)}
                  className={`color-swatch ${selectedColor === color ? 'selected' : ''}`}
                  sx={{ bgcolor: color }}
                >
                  {selectedColor === color && <Check fontSize="small" className="color-swatch-check" />}
                </Box>
              ))}
            </Stack>
          </Stack>

          <Box>
            <Typography variant="body2" className="typography-section-header">Typography</Typography>
            <Box className="typography-grid">
              {FONTS.map((font) => {
                const isSelected = selectedFont === font.name;
                return (
                  <Box 
                    key={font.name}
                    className={`font-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => setSelectedFont(font.name)}
                  >
                    {isSelected && <div className="font-card-check"><Check fontSize="small" /></div>}
                    <Typography variant="h4" className="font-card-ag" sx={{ fontFamily: font.name }}>Ag</Typography>
                    <Typography variant="subtitle2" className="font-card-name">{font.name}</Typography>
                    <Typography variant="caption" color="text.secondary" className="font-card-desc">
                      {font.desc}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          </Box>

        </Stack>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2, justifyContent: 'flex-end' }}>
        <Button onClick={handleRestore} className="restore-defaults-btn">Restore Defaults</Button>
        <Button onClick={handleSave} className="save-changes-btn">Save changes</Button>
      </DialogActions>
    </Dialog>
  );
};

export default CustomThemeDialog;