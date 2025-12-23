import { Box, Typography, IconButton, Stack } from '@mui/material';
import '../App.css'; 

interface RightPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const RightPanel = ({ isOpen, onClose }: RightPanelProps) => {
  
  return (
    <Box className={`right-panel-container ${isOpen ? 'open' : ''}`}>
      
      {/* Header */}
      <Stack 
        direction="row" 
        alignItems="center" 
        justifyContent="space-between" 
        className="right-panel-header"
      >
      </Stack>
      
      <Box className="right-panel-content">
        <div className="empty-state-container">
                 <img 
                    src="/Icon.png" 
                    alt="No Invocations" 
                    className="empty-state-icon" 
                    style={{ width: '157.91px', height: '143.09px', objectFit: 'contain' }}
                 />
            <Typography variant="subtitle1" sx={{ fontWeight: 500, mb: 1 }}>
                No invocations found
            </Typography>
            <Typography variant="body2" color="text.secondary">
                Try again in sometime
            </Typography>
        </div>
      </Box>
      
    </Box>
  );
};

export default RightPanel;