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

import React, { useEffect, useRef } from 'react';
import embed from 'vega-embed';
import { WorkspaceComponentWrapper } from './WorkspaceComponentWrapper';

interface VegaChartProps {
  spec: any;
  title?: string;
}

const VegaChart: React.FC<VegaChartProps> = ({ spec, title }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Apply high-contrast dark theme defaults to the spec
    const themedSpec = {
      ...spec,
      config: {
        ...spec.config,
        background: 'transparent',
        axis: {
          domainColor: '#555',
          gridColor: '#333',
          labelColor: '#999',
          tickColor: '#555',
          titleColor: '#bbb',
          labelFont: 'monospace',
          titleFont: 'monospace',
        },
        legend: {
          labelColor: '#999',
          titleColor: '#bbb',
          labelFont: 'monospace',
          titleFont: 'monospace',
        },
        view: { stroke: 'transparent' },
        mark: { color: '#0891b2' }, // Default cyan-600
      },
      width: 'container',
      height: 300,
      autosize: { type: 'fit', contains: 'padding' }
    };

    let resultPromise: any;
    
    const renderChart = async () => {
        try {
            resultPromise = embed(containerRef.current!, themedSpec, {
                actions: false,
            });
        } catch (error) {
            console.error('Vega rendering error:', error);
        }
    };

    renderChart();

    return () => {
      if (resultPromise) {
        resultPromise.then((res: any) => res.view.finalize());
      }
    };
  }, [spec]);

  return (
    <WorkspaceComponentWrapper title={title} testId="vega-chart">
        <div 
            ref={containerRef}
            data-testid="vega-chart-container"
            className="vega-chart-container w-full h-[350px] bg-zinc-950 border border-zinc-900 rounded-lg p-4 overflow-hidden"
        >
        {/* Vega will inject the canvas/svg here */}
        </div>
    </WorkspaceComponentWrapper>
  );
};

export default VegaChart;
