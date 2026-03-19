// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';

interface TooltipProps {
  content: React.ReactNode;
  isVisible: boolean;
  children: React.ReactElement;
}

const Portal: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  return mounted ? createPortal(children, document.body) : null;
};

export const Tooltip: React.FC<TooltipProps> = ({ content, isVisible, children }) => {
  const triggerRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  const updateCoords = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setCoords({
        top: rect.top,
        left: rect.right + 8, // 8px margin
      });
    }
  };

  useLayoutEffect(() => {
    if (isVisible) {
      updateCoords();
      // Also update on scroll/resize since the dropdown might move
      window.addEventListener('scroll', updateCoords, true);
      window.addEventListener('resize', updateCoords);
      return () => {
        window.removeEventListener('scroll', updateCoords, true);
        window.removeEventListener('resize', updateCoords);
      };
    }
  }, [isVisible]);

  return (
    <div ref={triggerRef} className="w-full">
      {children}
      {isVisible && (
        <Portal>
          <div 
            className="fixed z-[1000] bg-zinc-950 border border-zinc-800 rounded-lg p-3 shadow-2xl min-w-[250px] max-w-[350px] animate-in fade-in zoom-in-95 duration-200 pointer-events-none"
            style={{ 
              top: `${coords.top}px`, 
              left: `${coords.left}px` 
            }}
          >
            <div className="text-xs text-zinc-300 space-y-2">
              {content}
            </div>
          </div>
        </Portal>
      )}
    </div>
  );
};
