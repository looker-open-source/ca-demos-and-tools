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

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useLookerAuth } from '@/components/LookerAuthProvider';

export default function LoginPage() {
  const { login, isAuthenticated, isLoggingIn } = useLookerAuth();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, router]);

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-black text-white p-10">
      <div className="max-w-2xl w-full text-center space-y-8">
        <div className="space-y-4">
          <h1 className="text-4xl font-mono uppercase tracking-[0.2em] text-cyan-400">
            LOOKER CONVERSATIONAL ANALYTICS API
          </h1>
          <p className="text-zinc-500 font-mono text-sm tracking-widest uppercase">
            Reference Implementation
          </p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 p-12 rounded-2xl space-y-8 shadow-2xl">
          <div className="space-y-2">
            <h2 className="text-xl font-semibold">User Authentication Required</h2>
            <p className="text-zinc-400 text-sm">
              This application is currently running in OAuth mode. 
              Please log in with your Looker account to continue.
            </p>
          </div>

          <button
            onClick={() => login()}
            disabled={isLoggingIn}
            className="w-full bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white py-4 rounded-xl font-bold text-lg transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-cyan-900/20 flex items-center justify-center space-x-2"
          >
            {isLoggingIn ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                <span>Connecting...</span>
              </>
            ) : (
              <span>Login with Looker</span>
            )}
          </button>
          
          <div className="pt-4 border-t border-zinc-800">
            <p className="text-zinc-500 text-xs italic">
              All data access will be governed by your Looker user permissions.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
