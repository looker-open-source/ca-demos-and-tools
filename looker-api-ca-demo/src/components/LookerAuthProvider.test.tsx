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

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { LookerAuthProvider, useLookerAuth } from './LookerAuthProvider';

// Create a mock login function to track calls
const mockLogin = vi.fn();
const mockLogout = vi.fn();
const mockIsAuthenticated = vi.fn().mockReturnValue(false);

// Mock Looker SDK
vi.mock('@looker/sdk-rtl', () => {
  const OAuthSession = vi.fn(function() {
    return {
      isAuthenticated: mockIsAuthenticated,
      login: mockLogin,
      logout: mockLogout,
    };
  });
  const BrowserServices = vi.fn(function() {
    return {};
  });
  const ApiSettings = vi.fn(function() {
    return {
      readConfig: vi.fn().mockReturnValue({}),
    };
  });
  const ValueSettings = vi.fn().mockImplementation((vals) => ({
    ...vals,
    readConfig: () => vals,
  }));
  return {
    OAuthSession,
    BrowserServices,
    ApiSettings,
    ValueSettings,
  };
});

vi.mock('@looker/sdk', () => {
  const Looker40SDK = vi.fn(function(session) {
    return {
      authSession: session,
    };
  });
  return {
    Looker40SDK,
  };
});

const TestComponent = () => {
  const { isAuthenticated, login, logout, isLoggingIn } = useLookerAuth();
  return (
    <div>
      <div data-testid="auth-status">{isAuthenticated ? 'Authenticated' : 'Not Authenticated'}</div>
      <div data-testid="login-status">{isLoggingIn ? 'Logging In' : 'Idle'}</div>
      <button onClick={login}>Login</button>
      <button onClick={logout}>Logout</button>
    </div>
  );
};

describe('LookerAuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_LOOKER_OAUTH_CLIENT_ID = 'test-client-id';
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_LOOKER_OAUTH_CLIENT_ID;
  });

  it('should provide authentication status', () => {
    render(
      <LookerAuthProvider>
        <TestComponent />
      </LookerAuthProvider>
    );
    
    expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated');
  });

  it('should call login on the sdk when login is called', async () => {
    render(
      <LookerAuthProvider>
        <TestComponent />
      </LookerAuthProvider>
    );
    
    const loginButton = screen.getByText('Login');
    fireEvent.click(loginButton);
    
    expect(mockLogin).toHaveBeenCalled();
  });

  it('should call logout on the sdk when logout is called', async () => {
    render(
      <LookerAuthProvider>
        <TestComponent />
      </LookerAuthProvider>
    );
    
    const logoutButton = screen.getByText('Logout');
    fireEvent.click(logoutButton);
    
    expect(mockLogout).toHaveBeenCalled();
  });

  it('should throw error if useLookerAuth is used outside of provider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<TestComponent />)).toThrow('useLookerAuth must be used within a LookerAuthProvider');
    consoleSpy.mockRestore();
  });
});
