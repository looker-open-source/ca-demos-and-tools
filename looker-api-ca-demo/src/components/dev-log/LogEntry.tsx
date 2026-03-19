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

import React, { useState } from 'react';
import { DevLogEntry } from '@/lib/dev-logger/store';

interface LogEntryProps {
  entry: DevLogEntry;
}

export const LogEntry: React.FC<LogEntryProps> = ({ entry }) => {
  const [isOpen, setIsOpen] = useState(false);
  
  const statusColor = typeof entry.status === 'number' || entry.status === '200 (Done)'
    ? ((typeof entry.status === 'number' ? entry.status : 200) < 400 ? 'text-green-400' : 'text-red-400')
    : (entry.status === 'pending' ? 'text-yellow-400' : 'text-zinc-500');

  const duration = entry.endTime ? `${entry.endTime - entry.startTime}ms` : '...';

  return (
    <div className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/30 transition-colors">
      <div 
        className="flex items-center p-2 cursor-pointer gap-3 text-[10px] font-mono"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className={`w-3 text-center transition-transform ${isOpen ? 'rotate-90' : ''}`}>▶</span>
        <span className="w-10 font-bold text-zinc-400">{entry.method}</span>
        <span className={`w-8 font-bold ${statusColor}`}>{entry.status}</span>
        <span className="flex-1 truncate text-zinc-300" title={entry.path}>{entry.path}</span>
        <span className="w-16 text-right text-zinc-500">{duration}</span>
      </div>

      {isOpen && (
        <div className="p-3 bg-zinc-950/50 space-y-3 animate-in fade-in slide-in-from-top-1 duration-200">
          {entry.payload && (
            <div>
              <p className="text-[9px] uppercase tracking-widest font-bold text-zinc-600 mb-1">Request Payload</p>
              <pre className="p-2 bg-black/40 border border-zinc-800 rounded text-[9px] text-zinc-400 overflow-x-auto whitespace-pre">
                <code>{JSON.stringify(entry.payload, null, 2)}</code>
              </pre>
            </div>
          )}
          
          {entry.chunks && entry.chunks.length > 0 && (
            <div>
              <p className="text-[9px] uppercase tracking-widest font-bold text-zinc-600 mb-1">Response Chunks ({entry.chunks.length})</p>
              <div className="p-2 bg-black/40 border border-zinc-800 rounded text-[9px] text-cyan-500/80 font-mono max-h-32 overflow-y-auto space-y-1">
                {entry.chunks.map((chunk, i) => (
                  <div key={i} className="border-b border-zinc-900/50 last:border-0 pb-1 mb-1">
                    <span className="text-zinc-700 mr-2">[{i}]</span>
                    {chunk}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
