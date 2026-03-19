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

import React from "react";

interface LoadingOverlayProps {
  isVisible: boolean;
}

const LoadingOverlay: React.FC<LoadingOverlayProps> = ({ isVisible }) => {
  if (!isVisible) return null;

  return (
    <div
      data-testid="loading-overlay"
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-black/90 backdrop-blur-sm transition-opacity duration-500"
    >
      <div className="relative">
        {/* Neon Glow Pulse */}
        <div
          data-testid="loading-pulse"
          className="w-24 h-24 rounded-full bg-cyan-400 blur-2xl animate-pulse opacity-40"
        ></div>
        
        {/* Inner Core */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-12 h-12 border-4 border-cyan-400/20 border-t-cyan-400 rounded-full animate-spin"></div>
        </div>
      </div>
      
      <div className="mt-8 text-center">
        <h2 className="text-cyan-400 font-black italic text-xl tracking-tighter animate-bounce">
          INITIALIZING AGENTS
        </h2>
        <p className="text-zinc-500 font-mono text-[10px] uppercase tracking-[0.3em] mt-2">
          Syncing with Looker Conversational Analytics
        </p>
      </div>
    </div>
  );
};

export default LoadingOverlay;
