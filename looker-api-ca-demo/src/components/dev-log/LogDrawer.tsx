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

import React from 'react';
import { useDevLogStore } from '@/lib/dev-logger/store';
import { LogEntry } from './LogEntry';

export const LogDrawer: React.FC = () => {
  const { logs, clearLogs, isExpanded, setIsExpanded } = useDevLogStore();

  return (
    <div 
      className={`bg-zinc-950 border-t border-zinc-800 transition-all duration-300 flex flex-col shrink-0 z-50 ${
        isExpanded ? 'h-64' : 'h-8'
      }`}
    >
      {/* Header / Toggle */}
      <div 
        className="flex items-center justify-between px-4 py-1 bg-zinc-900 cursor-pointer hover:bg-zinc-800 transition-colors shrink-0"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center space-x-3">
          <span className="text-[10px] font-black italic tracking-tighter text-cyan-400">
            LOOKER SDK LOGS
          </span>
          <span className="text-[9px] bg-zinc-800 text-zinc-500 px-1.5 py-0.5 rounded font-mono">
            {logs.length}
          </span>
        </div>
        
        <div className="flex items-center space-x-4">
          <button 
            onClick={(e) => {
              e.stopPropagation();
              clearLogs();
            }}
            className="text-[9px] text-zinc-500 hover:text-red-400 uppercase tracking-widest font-bold transition-colors"
          >
            Clear
          </button>
          <span className={`text-zinc-500 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`}>
            ▲
          </span>
        </div>
      </div>

      {/* Log List */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800 bg-black/20">
        {logs.length === 0 ? (
          <div className="h-full flex items-center justify-center text-zinc-700 text-[10px] uppercase tracking-widest font-bold">
            No logs captured yet
          </div>
        ) : (
          logs.map((log) => (
            <LogEntry key={log.id} entry={log} />
          ))
        )}
      </div>
    </div>
  );
};
