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

import React, { useEffect, useRef, useState } from 'react';
import embed from 'vega-embed';
import { normalizeVegaLiteSpec } from '@/lib/vega-utils';
import { WorkspaceComponentWrapper } from './WorkspaceComponentWrapper';

interface VegaChartProps {
  spec: Record<string, unknown>;
  title?: string;
}

const VegaChart: React.FC<VegaChartProps> = ({ spec, title }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let isCancelled = false;
    let embeddedView: { finalize: () => void } | null = null;

    const normalizedSpec = normalizeVegaLiteSpec(spec);
    const existingConfig =
      typeof normalizedSpec.config === 'object' && normalizedSpec.config !== null
        ? (normalizedSpec.config as Record<string, unknown>)
        : {};

    // Apply high-contrast dark theme defaults to the normalized spec
    const themedSpec = {
      ...normalizedSpec,
      config: {
        ...existingConfig,
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
      autosize: { type: 'fit', contains: 'padding' },
    };

    const renderChart = async () => {
      try {
        const result = await embed(containerRef.current!, themedSpec as any, {
          actions: false,
        });
        if (isCancelled) {
          result?.view?.finalize();
          return;
        }
        embeddedView = result?.view ?? null;
        setRenderError(null);
      } catch (error) {
        if (!isCancelled) {
          console.error('Vega rendering error:', error);
          setRenderError(
            error instanceof Error ? error.message : 'Unknown visualization error'
          );
        }
      }
    };

    void renderChart();

    return () => {
      isCancelled = true;
      embeddedView?.finalize();
    };
  }, [spec]);

  return (
    <WorkspaceComponentWrapper title={title} testId="vega-chart">
      {renderError && (
        <div
          role="alert"
          className="w-full p-4 bg-zinc-950 border border-red-900/60 rounded-lg text-sm text-red-400 font-mono"
        >
          Unable to render chart: {renderError}
        </div>
      )}
      <div
        ref={containerRef}
        data-testid="vega-chart-container"
        className={
          renderError
            ? 'hidden'
            : 'vega-chart-container w-full h-[350px] bg-zinc-950 border border-zinc-900 rounded-lg p-4 overflow-hidden'
        }
      >
        {/* Vega will inject the canvas/svg here */}
      </div>
    </WorkspaceComponentWrapper>
  );
};

export default VegaChart;
