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

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DataVisualization } from './DataVisualization';
import VegaChart from './VegaChart';

// Mock vega-embed for VegaChart tests
vi.mock('vega-embed', () => ({
  __esModule: true,
  default: vi.fn().mockResolvedValue({
    view: {
      finalize: vi.fn()
    }
  })
}));

describe('Data Visibility Constraints', () => {
  const mockData = [
    { name: 'Jan', value: 400 },
    { name: 'Feb', value: 300 },
  ];

  describe('DataVisualization Height Constraints', () => {
    it('should have max-height of 400px and vertical scroll for tables', () => {
      render(<DataVisualization data={mockData} type="table" />);
      const contentWrapper = screen.getByTestId('data-visualization-content-wrapper');
      expect(contentWrapper).toHaveClass('max-h-[400px]');
      expect(contentWrapper).toHaveClass('overflow-y-auto');
    });

    it('should have max-height of 400px for charts', () => {
      render(<DataVisualization data={mockData} type="chart" />);
      const contentWrapper = screen.getByTestId('data-visualization-content-wrapper');
      expect(contentWrapper).toHaveClass('max-h-[400px]');
      expect(contentWrapper).toHaveClass('overflow-y-auto');
    });
  });

  describe('VegaChart Height Constraints', () => {
    it('should have max-height of 400px and vertical scroll', () => {
      const mockSpec = { mark: 'bar', data: { values: [] } };
      render(<VegaChart spec={mockSpec} />);
      const contentWrapper = screen.getByTestId('vega-chart-content-wrapper');
      expect(contentWrapper).toHaveClass('max-h-[400px]');
      expect(contentWrapper).toHaveClass('overflow-y-auto');
    });
  });

  describe('Collapsible Components', () => {
    it('DataVisualization should have a collapse/expand toggle and be expanded by default', () => {
      render(<DataVisualization data={mockData} type="table" />);
      
      const toggleButton = screen.getByRole('button', { name: /collapse/i });
      expect(toggleButton).toBeInTheDocument();
      
      // Content should be visible initially
      const contentWrapper = screen.getByTestId('data-visualization-content-wrapper');
      expect(contentWrapper).not.toHaveClass('hidden');
      expect(contentWrapper).toHaveClass('block');
      
      // Click to collapse
      fireEvent.click(toggleButton);
      expect(contentWrapper).toHaveClass('hidden');
      expect(contentWrapper).not.toHaveClass('block');
      expect(screen.getByRole('button', { name: /expand/i })).toBeInTheDocument();
      
      // Click to expand
      fireEvent.click(screen.getByRole('button', { name: /expand/i }));
      expect(contentWrapper).toHaveClass('block');
      expect(contentWrapper).not.toHaveClass('hidden');
    });

    it('VegaChart should have a collapse/expand toggle and be expanded by default', () => {
      const mockSpec = { mark: 'bar', data: { values: [] } };
      render(<VegaChart spec={mockSpec} />);
      
      const toggleButton = screen.getByRole('button', { name: /collapse/i });
      expect(toggleButton).toBeInTheDocument();
      
      // Vega container wrapper should be visible initially
      const contentWrapper = screen.getByTestId('vega-chart-content-wrapper');
      expect(contentWrapper).not.toHaveClass('hidden');
      expect(contentWrapper).toHaveClass('block');
      
      // Click to collapse
      fireEvent.click(toggleButton);
      expect(contentWrapper).toHaveClass('hidden');
      expect(contentWrapper).not.toHaveClass('block');
      
      // Click to expand
      fireEvent.click(screen.getByRole('button', { name: /expand/i }));
      expect(contentWrapper).toHaveClass('block');
      expect(contentWrapper).not.toHaveClass('hidden');
    });
  });
});
