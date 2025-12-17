// components/DialogBox.tsx
import React from 'react';
import { createPortal } from 'react-dom';

interface DialogBoxProps {
  isOpen: boolean;
  title: string;
  content: string;
  onConfirm?: () => void;
  onCancel: () => void;
  confirmLabel?: string;
  cancelLabel?: string;
  showConfirm?: boolean;
}

export const DialogBox: React.FC<DialogBoxProps> = ({
  isOpen,
  title,
  content,
  onConfirm,
  onCancel,
  confirmLabel = "Continue",
  cancelLabel = "Cancel",
  showConfirm = true
}) => {
  if (!isOpen) return null;

  return createPortal(
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog-container" onClick={(e) => e.stopPropagation()}>
        <h2 className="dialog-title">{title}</h2>
        <p className="dialog-content">{content}</p>
        <div className="dialog-actions">
          <button className="dialog-button cancel" onClick={onCancel}>
            {cancelLabel}
          </button>
          {showConfirm && (
            <button className="dialog-button confirm" onClick={onConfirm}>
              {confirmLabel}
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};