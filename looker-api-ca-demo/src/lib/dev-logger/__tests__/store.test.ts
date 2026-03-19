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

import { describe, it, expect, beforeEach } from 'vitest';
import { useDevLogStore } from '../store';

describe('useDevLogStore', () => {
  beforeEach(() => {
    // Reset store state before each test if it exists
    try {
        useDevLogStore.getState().clearLogs();
    } catch (e) {
        // Store not implemented yet
    }
  });

  it('should initialize with an empty logs array', () => {
    const state = useDevLogStore.getState();
    expect(state.logs).toEqual([]);
  });

  it('should add a log entry', () => {
    const { addLog } = useDevLogStore.getState();
    const entry = {
      id: '1',
      path: '/api/chat',
      method: 'POST',
      payload: { text: 'hello' },
      status: 'pending',
      startTime: Date.now(),
    };
    
    addLog(entry);
    
    const state = useDevLogStore.getState();
    expect(state.logs).toHaveLength(1);
    expect(state.logs[0]).toEqual(entry);
  });

  it('should update an existing log entry', () => {
    const { addLog, updateLog } = useDevLogStore.getState();
    const entry = {
      id: '1',
      path: '/api/chat',
      method: 'POST',
      payload: { text: 'hello' },
      status: 'pending',
      startTime: Date.now(),
    };
    
    addLog(entry);
    updateLog('1', { status: 200, endTime: Date.now() });
    
    const state = useDevLogStore.getState();
    expect(state.logs[0].status).toBe(200);
    expect(state.logs[0].endTime).toBeDefined();
  });

  it('should append chunks to a log entry', () => {
    const { addLog, appendChunk } = useDevLogStore.getState();
    const entry = {
      id: '1',
      path: '/api/chat',
      method: 'POST',
      payload: { text: 'hello' },
      status: 'pending',
      startTime: Date.now(),
      chunks: [],
    };
    
    addLog(entry);
    appendChunk('1', 'chunk 1');
    appendChunk('1', 'chunk 2');
    
    const state = useDevLogStore.getState();
    expect(state.logs[0].chunks).toEqual(['chunk 1', 'chunk 2']);
  });

  it('should clear all logs', () => {
    const { addLog, clearLogs } = useDevLogStore.getState();
    addLog({ id: '1', path: '/api/test', status: 'pending' });
    clearLogs();
    
    expect(useDevLogStore.getState().logs).toHaveLength(0);
  });
});
