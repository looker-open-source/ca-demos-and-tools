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

import { describe, it, expect, beforeEach, afterAll, vi } from 'vitest';
import fs from 'fs';
import { dumpDevLog } from './log-utils';

vi.mock('fs', () => ({
  default: {
    existsSync: vi.fn(),
    mkdirSync: vi.fn(),
    appendFileSync: vi.fn(),
    readdirSync: vi.fn(),
    statSync: vi.fn(),
    unlinkSync: vi.fn(),
  }
}));

describe('log-utils naming', () => {
  const OLD_ENV = process.env;

  beforeEach(() => {
    process.env = { ...OLD_ENV, NODE_ENV: 'development' };
    vi.clearAllMocks();
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-02-24T12:00:00Z'));
    
    // Default mock for statSync to avoid TypeError
    vi.mocked(fs.statSync).mockReturnValue({
      mtime: { getTime: () => Date.now() }
    } as any);
  });

  afterAll(() => {
    process.env = OLD_ENV;
    vi.useRealTimers();
  });

  it('should use <timestamp>_<conversation_id>.jsonl format for new log files', () => {
    vi.mocked(fs.existsSync).mockReturnValue(true);
    vi.mocked(fs.readdirSync).mockReturnValue([]);
    
    dumpDevLog('conv123', 'test', { foo: 'bar' });
    
    expect(fs.appendFileSync).toHaveBeenCalledWith(
      expect.stringMatching(/20260224120000_conv123\.jsonl$/),
      expect.any(String)
    );
  });

  it('should reuse existing log file for the same conversation ID regardless of timestamp', () => {
    vi.mocked(fs.existsSync).mockReturnValue(true);
    const existingFile = '20260224110000_conv123.jsonl';
    vi.mocked(fs.readdirSync).mockReturnValue([existingFile] as any);
    
    dumpDevLog('conv123', 'test', { foo: 'bar' });
    
    expect(fs.appendFileSync).toHaveBeenCalledWith(
      expect.stringContaining(existingFile),
      expect.any(String)
    );
  });
});
