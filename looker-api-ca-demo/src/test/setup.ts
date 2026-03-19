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

import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Polyfills for Node.js environments
import { TextEncoder, TextDecoder } from 'util';
global.TextEncoder = TextEncoder as any;
global.TextDecoder = TextDecoder as any;

// Mock scrollTo for JSDOM
Element.prototype.scrollTo = vi.fn();

// Mock ResizeObserver for Recharts - MUST be a class/constructor
global.ResizeObserver = class ResizeObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
};

// Simple global fetch mock to prevent "Failed to parse URL" errors during component rendering
global.fetch = vi.fn().mockImplementation((url: string) => {
  if (url === '/api/agents') {
    return Promise.resolve({
      ok: true,
      json: async () => ({ agents: [], defaultAgentId: null }),
    });
  }
  return Promise.resolve({
    ok: true,
    json: async () => ({}),
  });
});

