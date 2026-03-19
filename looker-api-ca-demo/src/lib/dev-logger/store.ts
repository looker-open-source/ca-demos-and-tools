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

import { create } from 'zustand';

export interface DevLogEntry {
  id: string;
  path: string;
  method: string;
  payload?: any;
  status: number | string | 'pending';
  startTime: number;
  endTime?: number;
  chunks?: string[];
}

interface DevLogState {
  logs: DevLogEntry[];
  isExpanded: boolean;
  setIsExpanded: (expanded: boolean) => void;
  addLog: (entry: DevLogEntry) => void;
  updateLog: (id: string, updates: Partial<DevLogEntry>) => void;
  appendChunk: (id: string, chunk: string) => void;
  clearLogs: () => void;
}

export const useDevLogStore = create<DevLogState>((set) => ({
  logs: [],
  isExpanded: true,
  setIsExpanded: (isExpanded) => set({ isExpanded }),
  addLog: (entry) => set((state) => ({ 
    logs: [entry, ...state.logs] 
  })),
  updateLog: (id, updates) => set((state) => ({
    logs: state.logs.map((log) => 
      log.id === id ? { ...log, ...updates } : log
    )
  })),
  appendChunk: (id, chunk) => set((state) => ({
    logs: state.logs.map((log) => 
      log.id === id 
        ? { ...log, chunks: [...(log.chunks || []), chunk] } 
        : log
    )
  })),
  clearLogs: () => set({ logs: [] }),
}));
