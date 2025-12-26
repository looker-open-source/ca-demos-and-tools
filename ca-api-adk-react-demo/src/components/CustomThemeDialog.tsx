import React, { useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Typography, Box, Stack
} from '@mui/material';
import { Check } from '@mui/icons-material';
import '../App.css';

interface CustomThemeDialogProps {
  open: boolean;
  onClose: () => void;
}

// Mock Data for the UI
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
  const [selectedColor, setSelectedColor] = useState(BG_COLORS[0]);
  const [selectedFont, setSelectedFont] = useState('Inter');

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      PaperProps={{
        className: 'custom-theme-dialog-paper'
      }}
    >
      <DialogTitle className="custom-theme-dialog-title">
        Custom Theme
      </DialogTitle>
      
      <DialogContent>
        <Stack spacing={3}>
          
          {/* 1. User Avatar Row */}
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="body2" className="dialog-row-label">User Avatar</Typography>
            <Stack direction="row" alignItems="center" spacing={2} className="dialog-row-content">
              <Button 
                variant="contained" 
                disableElevation 
                className="choose-file-btn"
              >
                Choose File
              </Button>
              <Typography variant="caption" color="text.secondary">No file chosen</Typography>
            </Stack>
          </Stack>

          {/* 2. Page Title Row */}
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="body2" className="dialog-row-label">Page Title</Typography>
            <Box className="dialog-row-content">
               <Box className="dialog-pill-input">Cases Eng Default Pool</Box>
            </Box>
          </Stack>

          {/* 3. Body Background Row */}
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="body2" className="dialog-row-label">Body Background</Typography>
            <Stack direction="row" spacing={1} className="dialog-row-content">
              {BG_COLORS.map((color) => (
                <Box
                  key={color}
                  onClick={() => setSelectedColor(color)}
                  className={`color-swatch ${selectedColor === color ? 'selected' : ''}`}
                  sx={{ bgcolor: color }} // Dynamic value, keep as inline style or sx
                >
                  {selectedColor === color && <Check fontSize="small" className="color-swatch-check" />}
                </Box>
              ))}
            </Stack>
          </Stack>

          {/* 4. Typography Grid */}
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
                    <Typography variant="h4" className="font-card-ag">Ag</Typography>
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
        <Button onClick={onClose} className="restore-defaults-btn">
          Restore Defaults
        </Button>
        <Button onClick={onClose} className="save-changes-btn">
          Save changes
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default CustomThemeDialog;