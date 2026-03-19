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

'use client';

import React from 'react';
import { useAuthStore } from '@/store/useAuthStore';
import { useLookerAuth } from './LookerAuthProvider';

export const SessionExpiredModal: React.FC = () => {
  const { sessionExpired, setSessionExpired } = useAuthStore();
  const { logout } = useLookerAuth();

  if (!sessionExpired) return null;

  const handleReauthenticate = async () => {
    // Clear state and logout, which will trigger redirect to login
    setSessionExpired(false);
    await logout();
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="bg-zinc-950 border border-red-900/50 rounded-2xl shadow-2xl shadow-red-950/20 max-w-md w-full p-8 text-center animate-in zoom-in-95 duration-300">
        <div className="w-16 h-16 bg-red-950/30 border border-red-900/50 rounded-full flex items-center justify-center mx-auto mb-6">
          <span className="text-3xl">🔑</span>
        </div>
        
        <h2 className="text-2xl font-black italic tracking-tighter text-red-500 uppercase mb-3">
          Session Expired
        </h2>
        
        <p className="text-zinc-400 text-sm leading-relaxed mb-8">
          Your Looker session has expired and could not be automatically refreshed. 
          Please sign in again to continue your data exploration.
        </p>
        
        <button
          onClick={handleReauthenticate}
          className="w-full py-3 px-6 bg-red-600 hover:bg-red-500 text-white font-bold rounded-lg transition-all active:scale-[0.98] shadow-lg shadow-red-600/20"
        >
          Re-authenticate
        </button>
      </div>
    </div>
  );
};
