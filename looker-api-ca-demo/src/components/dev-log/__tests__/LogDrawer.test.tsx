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
import { LogDrawer } from '../LogDrawer';
import { useDevLogStore } from '@/lib/dev-logger/store';

// Mock the store
vi.mock('@/lib/dev-logger/store', () => ({
  useDevLogStore: vi.fn(),
}));

describe('LogDrawer', () => {
  const mockClearLogs = vi.fn();
  const mockSetIsExpanded = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useDevLogStore as any).mockReturnValue({
      logs: [],
      clearLogs: mockClearLogs,
      isExpanded: true,
      setIsExpanded: mockSetIsExpanded,
    });
  });

  it('should render the drawer header', () => {
    render(<LogDrawer />);
    expect(screen.getByText(/LOOKER SDK LOGS/i)).toBeInTheDocument();
  });

  it('should show "No logs captured yet" when logs are empty', () => {
    render(<LogDrawer />);
    expect(screen.getByText(/No logs captured yet/i)).toBeInTheDocument();
  });

  it('should render logs when provided', () => {
    (useDevLogStore as any).mockReturnValue({
      logs: [
        { id: '1', method: 'GET', path: '/api/test', status: 200, startTime: Date.now() },
      ],
      clearLogs: mockClearLogs,
      isExpanded: true,
      setIsExpanded: mockSetIsExpanded,
    });

    render(<LogDrawer />);
    expect(screen.getByText('/api/test')).toBeInTheDocument();
    expect(screen.getByText('GET')).toBeInTheDocument();
    expect(screen.getByText('200')).toBeInTheDocument();
  });

  it('should call setIsExpanded when header is clicked', () => {
    render(<LogDrawer />);
    const header = screen.getByText(/LOOKER SDK LOGS/i).parentElement?.parentElement;
    if (header) {
        fireEvent.click(header);
        expect(mockSetIsExpanded).toHaveBeenCalledWith(false);
    }
  });

  it('should call clearLogs when Clear button is clicked', () => {
    render(<LogDrawer />);
    const clearButton = screen.getByText(/Clear/i);
    fireEvent.click(clearButton);
    expect(mockClearLogs).toHaveBeenCalled();
  });
});
