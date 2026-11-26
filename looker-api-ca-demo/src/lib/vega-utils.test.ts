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
import { normalizeVegaLiteSpec, VEGA_LITE_V6_SCHEMA } from './vega-utils';

describe('normalizeVegaLiteSpec', () => {
  it('upgrades Vega-Lite v4.17.0 $schema to v6', () => {
    const input = {
      $schema: 'https://vega.github.io/schema/vega-lite/v4.17.0.json',
      mark: 'bar',
      data: { values: [{ a: 'A', b: 1 }] },
    };

    const result = normalizeVegaLiteSpec(input);

    expect(result.$schema).toBe(VEGA_LITE_V6_SCHEMA);
    expect(input.$schema).toBe('https://vega.github.io/schema/vega-lite/v4.17.0.json');
  });

  it('upgrades Vega-Lite v5 $schema to v6', () => {
    const input = {
      $schema: 'https://vega.github.io/schema/vega-lite/v5.20.1.json',
      mark: 'line',
    };

    const result = normalizeVegaLiteSpec(input);

    expect(result.$schema).toBe(VEGA_LITE_V6_SCHEMA);
  });

  it('preserves Vega-Lite v6, Vega schemas, and schema-less specs', () => {
    const v6Spec = {
      $schema: 'https://vega.github.io/schema/vega-lite/v6.4.2.json',
      mark: 'bar',
    };
    const vegaSpec = {
      $schema: 'https://vega.github.io/schema/vega/v5.json',
      marks: [],
    };
    const noSchemaSpec = {
      mark: 'point',
    };

    expect(normalizeVegaLiteSpec(v6Spec).$schema).toBe('https://vega.github.io/schema/vega-lite/v6.4.2.json');
    expect(normalizeVegaLiteSpec(vegaSpec).$schema).toBe('https://vega.github.io/schema/vega/v5.json');
    expect(normalizeVegaLiteSpec(noSchemaSpec).$schema).toBeUndefined();
  });

  it('migrates v4 selection object to v6 params array without mutating input', () => {
    const input = {
      $schema: 'https://vega.github.io/schema/vega-lite/v4.17.0.json',
      mark: 'point',
      selection: {
        brush: { type: 'interval', encodings: ['x'] },
        highlight: { type: 'single', on: 'mouseover' },
      },
    };

    const result = normalizeVegaLiteSpec(input);

    expect(result.selection).toBeUndefined();
    expect(result.params).toEqual([
      { name: 'brush', select: { type: 'interval', encodings: ['x'] } },
      { name: 'highlight', select: { type: 'point', on: 'mouseover' } },
    ]);
    expect(input.selection).toBeDefined();
  });

  it('migrates selection inside nested layer/concat sub-specs', () => {
    const input = {
      $schema: 'https://vega.github.io/schema/vega-lite/v4.17.0.json',
      layer: [
        {
          mark: 'bar',
          selection: {
            pts: { type: 'multi' },
          },
        },
        {
          mark: 'line',
        },
      ],
    };

    const result = normalizeVegaLiteSpec(input);
    const layers = result.layer as Array<Record<string, unknown>>;

    expect(layers[0].selection).toBeUndefined();
    expect(layers[0].params).toEqual([
      { name: 'pts', select: { type: 'point' } },
    ]);
    expect(layers[1]).toEqual({ mark: 'line' });
  });
});
