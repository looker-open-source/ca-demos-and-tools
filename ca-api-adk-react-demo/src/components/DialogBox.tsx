import React from 'react';
import { createPortal } from 'react-dom';

interface DialogBoxProps {
  isOpen: boolean;
  title: string;
  content: React.ReactNode;
  onConfirm?: () => void;
  onCancel: () => void;
  confirmLabel?: string;
  cancelLabel?: string;
  showConfirm?: boolean;
  isConfirmDisabled?: boolean; // <--- New Prop
}

export const DialogBox: React.FC<DialogBoxProps> = ({
  isOpen,
  title,
  content,
  onConfirm,
  onCancel,
  confirmLabel = "Continue",
  cancelLabel = "Cancel",
  showConfirm = true,
  isConfirmDisabled = false // Default to false
}) => {
  if (!isOpen) return null;

  return createPortal(
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog-container" onClick={(e) => e.stopPropagation()}>
        <h2 className="dialog-title">{title}</h2>
        
        <div className="dialog-content">
          {content}
        </div>

        <div className="dialog-actions">
          <button className="dialog-button cancel" onClick={onCancel}>
            {cancelLabel}
          </button>
          {showConfirm && (
            <button 
              className={`dialog-button confirm ${isConfirmDisabled ? 'disabled' : ''}`} 
              onClick={isConfirmDisabled ? undefined : onConfirm}
              disabled={isConfirmDisabled}
              style={isConfirmDisabled ? { cursor: 'not-allowed', color: '#666' } : {}}
            >
              {confirmLabel}
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};