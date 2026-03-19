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
import { render, screen } from '@testing-library/react';
import VegaChart from './VegaChart';
import embed from 'vega-embed';

// Mock vega-embed
vi.mock('vega-embed', () => ({
  __esModule: true,
  default: vi.fn().mockResolvedValue({
    view: {
      finalize: vi.fn()
    }
  })
}));

describe('VegaChart', () => {
  it('should render a container and call vega-embed', async () => {
    const mockSpec = {
      $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
      description: 'A simple bar chart.',
      data: { values: [{a: 'A', b: 28}] },
      mark: 'bar'
    };

    const { container } = render(<VegaChart spec={mockSpec} />);
    
    // The first child is the WorkspaceComponentWrapper (space-y-2)
    expect(container.firstChild).toHaveClass('space-y-2');
    
    // The vega-chart-container should be nested inside
    expect(screen.getByTestId('vega-chart-container')).toHaveClass('vega-chart-container');
    
    // Check if embed was called
    expect(embed).toHaveBeenCalled();
    
    // Verify themed spec was passed (e.g., background transparent)
    const passedSpec = (embed as any).mock.calls[0][1];
    expect(passedSpec.config.background).toBe('transparent');
  });
});
