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

describe('log-utils', () => {
  const OLD_ENV = process.env;

  beforeEach(() => {
    process.env = { ...OLD_ENV };
    vi.clearAllMocks();
  });

  afterAll(() => {
    process.env = OLD_ENV;
  });

  it('should not dump logs if not in development mode', () => {
    process.env.NODE_ENV = 'production';
    dumpDevLog('conv123', 'test', { foo: 'bar' });
    expect(fs.appendFileSync).not.toHaveBeenCalled();
  });

  it('should dump logs in development mode using append', () => {
    process.env.NODE_ENV = 'development';
    vi.mocked(fs.existsSync).mockReturnValue(true);
    vi.mocked(fs.readdirSync).mockReturnValue([]);
    
    dumpDevLog('conv123', 'test', { foo: 'bar' });
    
    expect(fs.appendFileSync).toHaveBeenCalledWith(
      expect.stringMatching(/\d{14}_conv123\.jsonl$/),
      expect.stringContaining('"foo":"bar"')
    );
  });

  it('should create log directory if it does not exist', () => {
    process.env.NODE_ENV = 'development';
    vi.mocked(fs.existsSync).mockReturnValue(false);
    vi.mocked(fs.readdirSync).mockReturnValue([]);

    dumpDevLog('conv123', 'test', { foo: 'bar' });

    expect(fs.mkdirSync).toHaveBeenCalledWith(expect.stringContaining('.ca_logs'));
  });
});
