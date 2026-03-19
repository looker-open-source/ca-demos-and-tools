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

import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';
import VegaChart from './VegaChart';
import { WorkspaceComponentWrapper } from './WorkspaceComponentWrapper';

interface DataVisualizationProps {
  data: any[];
  type?: 'table' | 'chart';
  payload?: {
    formattedHeader?: string;
    sql?: string;
    vegaConfig?: any;
    isChart?: boolean;
  };
}

export const DataVisualization: React.FC<DataVisualizationProps> = ({ 
  data, 
  type = 'table',
  payload
}) => {
  const [showSql, setShowSql] = useState(false);

  // If we have a vegaConfig, prioritize rendering the VegaChart
  if (payload?.vegaConfig) {
    return (
      <VegaChart 
        spec={payload.vegaConfig} 
        title={payload.formattedHeader} 
      />
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-500 italic">
        No data available to display.
      </div>
    );
  }

  // Infer columns from data keys
  const columns = Object.keys(data[0]);

  const renderContent = () => {
    if (type === 'table') {
      return (
        <div className="overflow-x-auto border border-zinc-800 rounded-lg">
          <table className="min-w-full divide-y divide-zinc-800 bg-zinc-950 text-sm">
            <thead className="bg-zinc-900">
              <tr>
                {columns.map((col) => (
                  <th key={col} className="px-4 py-2 text-left font-semibold text-cyan-400 uppercase tracking-wider">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {data.map((row, idx) => (
                <tr key={idx} className="hover:bg-zinc-900 transition-colors">
                  {columns.map((col) => (
                    <td key={col} className="px-4 py-2 text-zinc-300 whitespace-nowrap">
                      {String(row[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    return (
      <div className="h-[300px] w-full bg-zinc-950 border border-zinc-800 rounded-lg p-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis 
              dataKey={columns[0]} 
              stroke="#999" 
              tick={{ fill: '#999' }} 
            />
            <YAxis 
              stroke="#999" 
              tick={{ fill: '#999' }} 
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#111', borderColor: '#333', color: '#fff' }}
              itemStyle={{ color: '#22d3ee' }}
            />
            <Legend />
            <Bar dataKey={columns[1]} fill="#0891b2" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  return (
    <WorkspaceComponentWrapper 
      title={payload?.formattedHeader} 
      testId="data-visualization"
    >
      <div className="space-y-4">
        {payload?.sql && (
          <div className="px-2">
            <button
              onClick={() => setShowSql(!showSql)}
              className="text-[10px] uppercase tracking-widest font-bold text-zinc-500 hover:text-cyan-400 transition-colors mb-2"
            >
              {showSql ? 'Hide Looker SQL' : 'View Looker SQL'}
            </button>
            {showSql && (
              <pre className="p-3 bg-zinc-900 border border-zinc-800 rounded text-xs text-zinc-400 font-mono overflow-x-auto whitespace-pre-wrap animate-in fade-in slide-in-from-top-1 duration-200">
                {payload.sql}
              </pre>
            )}
          </div>
        )}

        {renderContent()}
      </div>
    </WorkspaceComponentWrapper>
  );
};
