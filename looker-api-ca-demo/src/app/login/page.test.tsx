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
import { render, screen, fireEvent } from '@testing-library/react';
import LoginPage from './page';
import { useLookerAuth } from '@/components/LookerAuthProvider';
import { useRouter } from 'next/navigation';

vi.mock('@/components/LookerAuthProvider', () => ({
  useLookerAuth: vi.fn(),
  LookerAuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
}));

describe('LoginPage', () => {
  let mockLogin: any;
  let mockPush: any;

  beforeEach(() => {
    mockLogin = vi.fn().mockResolvedValue(undefined);
    mockPush = vi.fn();
    
    (useLookerAuth as any).mockReturnValue({
      login: mockLogin,
      isAuthenticated: false,
      checkAuth: vi.fn(),
      isInitialized: true,
    });
    
    (useRouter as any).mockReturnValue({
      push: mockPush,
    });
  });

  it('should render the login page with a login button', () => {
    render(<LoginPage />);
    expect(screen.getByText(/Login with Looker/i)).toBeInTheDocument();
  });

  it('should call login when button is clicked', () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByText(/Login with Looker/i));
    expect(mockLogin).toHaveBeenCalled();
  });

  it('should redirect if already authenticated', () => {
    (useLookerAuth as any).mockReturnValue({
      login: mockLogin,
      isAuthenticated: true,
    });
    
    render(<LoginPage />);
    expect(mockPush).toHaveBeenCalledWith('/');
  });
});
