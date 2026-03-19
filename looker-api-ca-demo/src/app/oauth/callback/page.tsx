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

import React, { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useLookerAuth } from '@/components/LookerAuthProvider';
import { useAuthStore } from '@/store/useAuthStore';

export default function OAuthCallbackPage() {
  const { sdk, checkAuth } = useLookerAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const redeemingRef = useRef(false);

  useEffect(() => {
    const redeemCode = async () => {
      if (sdk && !redeemingRef.current) {
        const params = new URLSearchParams(window.location.search);
        const code = params.get('code');
        if (!code) return;

        redeemingRef.current = true;
        try {
          const config = (sdk.authSession as any).settings.readConfig();
          const verifier = window.sessionStorage.getItem('looker_oauth_code_verifier');
          
          console.log('[Callback] Manual Token Exchange Start');

          if (!verifier) {
            throw new Error('Code verifier missing from session storage');
          }

          // Manually perform the exchange
          const tokenUrl = `${config.base_url.replace(/\/api\/4\.0\/?$/, '')}/api/token`;
          const body = new URLSearchParams({
            client_id: config.client_id,
            code: code,
            code_verifier: verifier,
            grant_type: 'authorization_code',
            redirect_uri: config.redirect_uri,
          });

          const response = await window.fetch(tokenUrl, {
            method: 'POST',
            mode: 'cors',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
              'Accept': 'application/json',
            },
            body: body.toString(),
          });

          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.error_description || data.error || 'Token exchange failed');
          }

          console.log('[Callback] Token exchange successful, updating session...');
          
          // Manual persistence to ensure it survives refreshes better than the SDK's default
          const tokenData = {
            ...data,
            expiry_at: Date.now() + (data.expires_in * 1000)
          };
          window.localStorage.setItem('looker_sdk_40_token', JSON.stringify(tokenData));
          
          // Update global auth store
          useAuthStore.getState().setAuthToken(data);
          
          // Update the session with the new token
          await (sdk.authSession as any).activeToken.setToken(data);
          
          // Sync the authentication state in the context
          checkAuth();
          
          console.log('[Callback] Redirecting to home...');
          router.push('/');
        } catch (err: any) {
          console.error('[Callback] OAuth redemption failed:', err);
          setError(err.message || 'Authentication failed');
        }
      }
    };

    redeemCode();
  }, [sdk, router, checkAuth]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-black text-white p-10">
        <div className="bg-red-950 border border-red-900 text-red-400 p-6 rounded-xl max-w-md text-center">
          <h1 className="text-xl font-bold mb-4">Authentication Failed</h1>
          <p className="mb-6 font-mono text-sm">{error}</p>
          <button 
            onClick={() => {
              redeemingRef.current = false;
              router.push('/login');
            }}
            className="bg-red-600 hover:bg-red-500 text-white px-6 py-2 rounded font-bold transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-black text-white">
      <div className="flex flex-col items-center space-y-4">
        <div className="w-12 h-12 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
        <h1 className="text-xl font-mono uppercase tracking-widest text-cyan-400">
          Authenticating with Looker...
        </h1>
        <p className="text-zinc-500 text-sm">Finishing the OAuth handshake.</p>
      </div>
    </div>
  );
}
