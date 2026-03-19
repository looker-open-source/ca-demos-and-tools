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

import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DataVisualization } from './DataVisualization';

describe('DataVisualization', () => {
  it('should render a message when no data is provided', () => {
    render(<DataVisualization data={[]} />);
    expect(screen.getByText(/No data available/i)).toBeInTheDocument();
  });

  it('should render a table when data is provided', () => {
    const data = [
      { name: 'Jan', value: 400 },
      { name: 'Feb', value: 300 },
    ];
    render(<DataVisualization data={data} type="table" />);
    expect(screen.getByText('Jan')).toBeInTheDocument();
    expect(screen.getByText('400')).toBeInTheDocument();
  });

  it('should render a chart when data is provided and type is chart', () => {
    const data = [
      { name: 'Jan', value: 400 },
    ];
    const { container } = render(<DataVisualization data={data} type="chart" />);
    // Recharts renders as SVG
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument();
  });

  it('should render formatted header and SQL toggle when payload is provided', () => {
    const data = [{ a: 1 }];
    const payload = {
      formattedHeader: "Here's the query result for Test Name",
      sql: "SELECT * FROM test"
    };

    render(<DataVisualization data={data} payload={payload} />);

    expect(screen.getByText("Here's the query result for Test Name")).toBeInTheDocument();
    
    const toggleButton = screen.getByText(/View Looker SQL/i);
    expect(toggleButton).toBeInTheDocument();

    // SQL should be hidden initially
    expect(screen.queryByText("SELECT * FROM test")).not.toBeInTheDocument();

    // Toggle SQL visibility
    fireEvent.click(toggleButton);
    expect(screen.getByText("SELECT * FROM test")).toBeInTheDocument();
    expect(screen.getByText(/Hide Looker SQL/i)).toBeInTheDocument();
  });
});
