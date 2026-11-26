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

/** Target Vega-Lite v6 schema URL matching the installed vega-lite package. */
export const VEGA_LITE_V6_SCHEMA = 'https://vega.github.io/schema/vega-lite/v6.json';

const VEGA_LITE_SCHEMA_PATTERN = /\/schema\/vega-lite\/v(\d+)(?:\.\d+)*\.json$/i;
const SUBSPEC_ARRAY_KEYS = ['layer', 'hconcat', 'vconcat', 'concat'] as const;
const SUBSPEC_OBJECT_KEYS = ['spec'] as const;

type VegaSpecRecord = Record<string, unknown>;

function isPlainRecord(value: unknown): value is VegaSpecRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function upgradeSchemaUrl(schema: unknown): unknown {
  if (typeof schema !== 'string') {
    return schema;
  }
  const match = schema.match(VEGA_LITE_SCHEMA_PATTERN);
  if (!match) {
    return schema;
  }
  const majorVersion = Number(match[1]);
  return majorVersion < 6 ? VEGA_LITE_V6_SCHEMA : schema;
}

function migrateSelectionDefinition(definition: unknown): unknown {
  if (!isPlainRecord(definition)) {
    return definition;
  }
  // Vega-Lite v5/v6 unified v4 'single' and 'multi' selections into 'point'.
  if (definition.type === 'single' || definition.type === 'multi') {
    return { ...definition, type: 'point' };
  }
  return { ...definition };
}

function migrateSelections(selection: unknown): Array<{ name: string; select: unknown }> {
  if (!isPlainRecord(selection)) {
    return [];
  }
  return Object.entries(selection).map(([name, def]) => ({
    name,
    select: migrateSelectionDefinition(def),
  }));
}

function normalizeSubSpec(spec: VegaSpecRecord): VegaSpecRecord {
  const normalized: VegaSpecRecord = { ...spec };

  if (normalized.selection !== undefined && normalized.params === undefined) {
    normalized.params = migrateSelections(normalized.selection);
    delete normalized.selection;
  }

  for (const key of SUBSPEC_ARRAY_KEYS) {
    const children = normalized[key];
    if (Array.isArray(children)) {
      normalized[key] = children.map((child) =>
        isPlainRecord(child) ? normalizeSubSpec(child) : child
      );
    }
  }

  for (const key of SUBSPEC_OBJECT_KEYS) {
    const child = normalized[key];
    if (isPlainRecord(child)) {
      normalized[key] = normalizeSubSpec(child);
    }
  }

  return normalized;
}

export interface NormalizedVegaSpec extends VegaSpecRecord {
  $schema?: string;
  params?: unknown[];
}

/**
 * Normalizes an incoming Vega or Vega-Lite specification to be compatible with
 * the bundled Vega-Lite v6 runtime without mutating the original object.
 */
export function normalizeVegaLiteSpec(spec: VegaSpecRecord): NormalizedVegaSpec {
  const normalized = normalizeSubSpec(spec) as NormalizedVegaSpec;

  if ('$schema' in normalized) {
    normalized.$schema = upgradeSchemaUrl(normalized.$schema) as string | undefined;
  }

  return normalized;
}
