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

import React, { createContext, useContext, useEffect, useState, useMemo, useCallback } from 'react';
import { Looker40SDK } from '@looker/sdk';
import { BrowserServices, OAuthSession } from '@looker/sdk-rtl';
import { useAuthStore } from '@/store/useAuthStore';

interface LookerAuthContextType {
  sdk: Looker40SDK | null;
  isAuthenticated: boolean;
  login: () => Promise<void>;
  logout: () => void;
  isLoggingIn: boolean;
  checkAuth: () => boolean;
  isInitialized: boolean;
  authConfig: {
    authMode: string;
    baseUrl: string;
    lookerUrl: string;
    oauthClientId: string;
  };
}

const LookerAuthContext = createContext<LookerAuthContextType | null>(null);

// Global singleton
let globalAuthSession: OAuthSession | null = null;
let globalSdk: Looker40SDK | null = null;

const TOKEN_STORAGE_KEY = 'looker_sdk_40_token';
const VERIFIER_STORAGE_KEY = 'looker_oauth_code_verifier';

export const LookerAuthProvider: React.FC<{ 
  children: React.ReactNode,
  initialConfig?: {
    authMode?: string;
    baseUrl?: string;
    oauthClientId?: string;
  }
}> = ({ children, initialConfig }) => {
  const [sdk, setSdk] = useState<Looker40SDK | null>(globalSdk);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);

  // Resolution order: Props (runtime) > Build-time Env > Defaults
  const authConfig = useMemo(() => {
    const authMode = initialConfig?.authMode || process.env.NEXT_PUBLIC_LOOKER_AUTH_MODE || 'env';
    const baseUrl = (initialConfig?.baseUrl || process.env.NEXT_PUBLIC_LOOKER_BASE_URL || '').replace(/\/api\/4\.0\/?$/, '');
    const oauthClientId = initialConfig?.oauthClientId || process.env.NEXT_PUBLIC_LOOKER_OAUTH_CLIENT_ID || '';
    const lookerUrl = baseUrl.replace(/:\d+$/, '');

    return { authMode, baseUrl, lookerUrl, oauthClientId };
  }, [initialConfig]);

  // Synchronously check storage for initial state to prevent redirect flicker
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    if (typeof window !== 'undefined') {
      // If we don't know the auth mode yet, don't assume SA mode
      if (initialConfig?.authMode === 'env' || process.env.NEXT_PUBLIC_LOOKER_AUTH_MODE === 'env') {
          return true;
      }
      return !!window.localStorage.getItem(TOKEN_STORAGE_KEY);
    }
    return false;
  });

  const sdkConfig = useMemo(() => {
    if (typeof window === 'undefined') return null;

    if (authConfig.authMode === 'env' || !authConfig.oauthClientId || authConfig.oauthClientId === 'your-client-id') {
      return null;
    }

    const redirectUri = `${window.location.origin}/oauth/callback`;

    return {
      base_url: `${authConfig.baseUrl}/api/4.0`,
      looker_url: authConfig.lookerUrl,
      client_id: authConfig.oauthClientId,
      redirect_uri: redirectUri,
      verify_ssl: true,
      timeout: 120,
      agentTag: 'TS-SDK-Demo',
    };
  }, [authConfig]);

  const checkAuth = useCallback(() => {
    if (globalAuthSession) {
      const isAuth = globalAuthSession.isAuthenticated();
      
      // Persistence fallback
      if (!isAuth && typeof window !== 'undefined') {
        const storedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
        if (storedToken) {
          try {
            const tokenData = JSON.parse(storedToken);
            (globalAuthSession as any).activeToken.setToken(tokenData);
            const verifiedAuth = globalAuthSession.isAuthenticated();
            setIsAuthenticated(verifiedAuth);
            return verifiedAuth;
          } catch (e) {
            console.error('Failed to load stored token', e);
          }
        }
      }
      
      setIsAuthenticated(isAuth);
      return isAuth;
    }
    return false;
  }, []);

  useEffect(() => {
    // If authMode is 'env', we are always initialized and authenticated
    if (authConfig.authMode === 'env') {
      setIsInitialized(true);
      setIsAuthenticated(true);
      return;
    }

    if (!sdkConfig) {
      setIsInitialized(true);
      return;
    }

    if (!globalAuthSession) {
      const settings = {
        ...sdkConfig,
        isConfigured: () => !!sdkConfig.base_url && !!sdkConfig.client_id,
        readConfig: () => sdkConfig,
      };

      try {
        const services = new BrowserServices({ settings: settings as any });
        globalAuthSession = new OAuthSession(services);
        globalSdk = new Looker40SDK(globalAuthSession);
      } catch (err) {
        console.error('Failed to initialize Looker SDK singleton:', err);
      }
    }

    if (globalSdk) {
      setSdk(globalSdk);
      // Initialize the global auth store
      useAuthStore.getState().initialize();
      checkAuth();
    }
    setIsInitialized(true);
  }, [sdkConfig, authConfig.authMode, checkAuth]);

  // Subscribe to auth store changes to keep SDK session in sync
  useEffect(() => {
    if (authConfig.authMode === 'env') return;

    const unsub = useAuthStore.subscribe((state) => {
      if (state.token && globalAuthSession) {
        // If the token in the store changed, update the SDK session
        const currentToken = (globalAuthSession as any).activeToken.accessToken;
        if (state.token !== currentToken) {
          console.log('[Auth] Syncing SDK session with refreshed token');
          const storedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
          if (storedToken) {
            try {
              const data = JSON.parse(storedToken);
              (globalAuthSession as any).activeToken.setToken(data);
              setIsAuthenticated(true);
            } catch (e) {
              console.error('Failed to sync refreshed token to SDK', e);
            }
          }
        }
      } else if (!state.token && isAuthenticated) {
        setIsAuthenticated(false);
      }
    });
    return unsub;
  }, [authConfig.authMode, isAuthenticated]);

  const login = async () => {
    if (sdk && !isLoggingIn) {
      setIsLoggingIn(true);
      try {
        await sdk.authSession.login();
        checkAuth();
      } catch (err: any) {
        if (err.message?.includes('no OAuth code parameter found')) {
           const authUrl = await (sdk.authSession as any).createAuthCodeRequestUrl('api', 'TS-SDK');
           window.location.href = authUrl;
        }
      } finally {
        setIsLoggingIn(false);
      }
    }
  };

  const logout = async () => {
    if (sdk) {
      try {
        await sdk.authSession.logout();
      } catch (err) {
        console.warn('[Auth] Server-side logout failed.');
      } finally {
        window.localStorage.removeItem(TOKEN_STORAGE_KEY);
        window.sessionStorage.removeItem(VERIFIER_STORAGE_KEY);
        window.sessionStorage.removeItem('looker_oauth_code_verifier');
        window.sessionStorage.removeItem('looker_oauth_return_url');
        
        // Clear the global auth store
        useAuthStore.getState().clearToken();

        if (globalAuthSession) {
            (globalAuthSession as any).activeToken?.reset();
        }
        
        checkAuth();
      }
    }
  };

  return (
    <LookerAuthContext.Provider value={{ sdk, isAuthenticated, login, logout, isLoggingIn, checkAuth, isInitialized, authConfig }}>
      {children}
    </LookerAuthContext.Provider>
  );
};

export const useLookerAuth = () => {
  const context = useContext(LookerAuthContext);
  if (!context) {
    throw new Error('useLookerAuth must be used within a LookerAuthProvider');
  }
  return context;
};
