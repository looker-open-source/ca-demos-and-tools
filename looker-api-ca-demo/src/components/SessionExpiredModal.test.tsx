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

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SessionExpiredModal } from './SessionExpiredModal';
import { useAuthStore } from '@/store/useAuthStore';
import { useLookerAuth } from './LookerAuthProvider';

vi.mock('@/store/useAuthStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('./LookerAuthProvider', () => ({
  useLookerAuth: vi.fn(),
}));

describe('SessionExpiredModal', () => {
  const mockLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useLookerAuth as any).mockReturnValue({
      logout: mockLogout,
    });
  });

  it('should not render anything if session is not expired', () => {
    (useAuthStore as any).mockReturnValue({
      sessionExpired: false,
      setSessionExpired: vi.fn(),
    });

    render(<SessionExpiredModal />);
    expect(screen.queryByText(/Session Expired/i)).not.toBeInTheDocument();
  });

  it('should render the modal if session is expired', () => {
    (useAuthStore as any).mockReturnValue({
      sessionExpired: true,
      setSessionExpired: vi.fn(),
    });

    render(<SessionExpiredModal />);
    expect(screen.getByText(/Session Expired/i)).toBeInTheDocument();
    expect(screen.getByText(/Your Looker session has expired and could not be automatically refreshed/i)).toBeInTheDocument();
  });

  it('should call logout when Re-authenticate button is clicked', () => {
    (useAuthStore as any).mockReturnValue({
      sessionExpired: true,
      setSessionExpired: vi.fn(),
    });

    render(<SessionExpiredModal />);
    const button = screen.getByRole('button', { name: /Re-authenticate/i });
    fireEvent.click(button);

    expect(mockLogout).toHaveBeenCalled();
  });
});
