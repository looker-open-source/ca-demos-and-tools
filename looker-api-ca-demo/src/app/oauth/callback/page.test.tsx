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

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import OAuthCallbackPage from './page';
import { useLookerAuth, LookerAuthProvider } from '@/components/LookerAuthProvider';
import { useRouter } from 'next/navigation';

vi.mock('@/components/LookerAuthProvider', () => ({
  useLookerAuth: vi.fn(),
  LookerAuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
}));

describe('OAuthCallbackPage', () => {
  let mockSetToken: any;
  let mockPush: any;

  beforeEach(() => {
    mockSetToken = vi.fn().mockResolvedValue(undefined);
    mockPush = vi.fn();
    
    (useLookerAuth as any).mockReturnValue({
      sdk: {
        authSession: {
          activeToken: {
            setToken: mockSetToken,
          },
          settings: {
            readConfig: vi.fn().mockReturnValue({
              base_url: 'https://test.looker.com:19999/api/4.0',
              redirect_uri: 'http://localhost:3000/oauth/callback',
              client_id: 'test-client-id'
            })
          }
        },
      },
      checkAuth: vi.fn(),
      isInitialized: true,
    });
    
    (useRouter as any).mockReturnValue({
      push: mockPush,
    });

    // Mock window.location
    delete (window as any).location;
    window.location = {
      ...window.location,
      href: 'http://localhost:3000/oauth/callback?code=test-code',
      search: '?code=test-code',
    } as any;

    // Mock sessionStorage
    const storage: any = {
        'looker_oauth_code_verifier': 'test-verifier'
    };
    Object.defineProperty(window, 'sessionStorage', {
      value: {
        getItem: (key: string) => storage[key],
        removeItem: vi.fn(),
        setItem: vi.fn(),
      },
      writable: true
    });

    // Mock fetch
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: 'new-token' }),
    });
  });

  it('should call fetch and redirect to home on success', async () => {
    render(<OAuthCallbackPage />);
    
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'https://test.looker.com:19999/api/token',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('code=test-code'),
        })
      );
    });
    
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });

  it('should show error message if redemption fails', async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      json: async () => ({ error: 'invalid_grant', error_description: 'Bad code' }),
    });
    
    const { getByText } = render(<OAuthCallbackPage />);
    
    await waitFor(() => {
      expect(getByText(/Bad code/i)).toBeInTheDocument();
    });
  });
});
