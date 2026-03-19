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

import { describe, it, expect } from 'vitest';
import { mapLookerError } from './error-mapping';

describe('error-mapping', () => {
  it('should map ACTION_GENERATION error to user-friendly message', () => {
    const error = { code: 500, message: 'ACTION_GENERATION: failed due to INTERNAL error' };
    const mapped = mapLookerError(error);
    expect(mapped).toContain('I encountered an internal error while trying to process your request');
  });

  it('should return a generic message for unknown errors', () => {
    const error = { code: 500, message: 'SOME_RANDOM_ERROR' };
    const mapped = mapLookerError(error);
    expect(mapped).toContain('Something went wrong on the server');
  });

  it('should handle null or undefined errors', () => {
    expect(mapLookerError(null)).toContain('An unexpected error occurred');
  });
});
