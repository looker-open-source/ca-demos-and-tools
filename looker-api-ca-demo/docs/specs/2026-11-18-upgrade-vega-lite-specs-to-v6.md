# Spec: Upgrade Incoming Vega-Lite Specs to v6

- **Status:** Implemented
- **Created:** 2026-11-18

## Overview & Problem Statement
The Looker Conversational Analytics API returns `vegaConfig` payloads stamped with Vega-Lite v4 schema URLs (e.g., `https://vega.github.io/schema/vega-lite/v4.17.0.json`), while the application bundles `vega-lite@6.4.2`, `vega@6.2.0`, and `vega-embed@7.1.0`. On render, `vega-embed` detects the version mismatch and logs: `The input spec uses Vega-Lite v4.17.0, but the current version of Vega-Lite is v6.4.2.` Normalizing incoming Vega-Lite specs to v6 in the renderer eliminates this warning and guards against v4→v6 schema differences without downgrading packages or introducing Dependabot/Airlock issues.

> **Living Context Impact:** None. `docs/context/tech-stack.md` already specifies Vega-Lite without a pinned version, and `package.json` dependencies (`vega@6.2.0`, `vega-lite@6.4.2`, `vega-embed@7.1.0`) remain unchanged.

## Functional Requirements
- [ ] **Vega-Lite Schema Normalization Helper:**
  - Create a pure, well-typed helper (`normalizeVegaLiteSpec(spec)` in `src/lib/vega-utils.ts`) that returns a non-mutating copy of `spec`.
  - When `spec.$schema` references an older Vega-Lite schema (`vega-lite/v<major>...` where `<major> < 6`, such as `v4.17.0` or `v5`), rewrite `$schema` to `https://vega.github.io/schema/vega-lite/v6.json`.
  - Leave specs that already target `vega-lite/v6...` or Vega (`vega/v...`) untouched, and leave specs without `$schema` untouched (preserving `vega-embed`'s auto-detection).
- [ ] **Safe v4 → v6 Construct Migration:**
  - If `spec.selection` exists (Vega-Lite v4 interactive selections) and `spec.params` is not already defined, migrate `selection` entries into `params` (converting object map `{ [name]: def }` to `[{ name, select: def }]` as expected in Vega-Lite v5/v6) and omit the deprecated `selection` key.
  - Handle nested `layer`, `hconcat`, `vconcat`, and `concat` sub-specs recursively without mutating the original `payload.vegaConfig`.
- [ ] **Renderer Integration & Error Fallback (`VegaChart.tsx`):**
  - Apply the normalizer in `src/components/VegaChart.tsx` before merging the dark-theme `config` and passing `themedSpec` to `embed(...)`.
  - Keep the raw `payload.vegaConfig` unmodified in Zustand state, `LogDrawer`, and `persistLookerMessages()`.
  - Catch asynchronous rejections from `embed(...)` and render a clean dark-mode error fallback instead of failing silently.

## Non-Functional Requirements
- Keep `vega@6.2.0`, `vega-lite@6.4.2`, and `vega-embed@7.1.0` unchanged in `package.json` (no Dependabot downgrades or Airlock package changes).
- Pure normalization logic with zero side effects and no mutation of `spec` props.
- Consistent with the dark-mode + cyan-accent styling in `docs/context/product-guidelines.md`.

## Acceptance Criteria
- Rendering a Vega-Lite spec with `$schema: "https://vega.github.io/schema/vega-lite/v4.17.0.json"` passes `$schema: "https://vega.github.io/schema/vega-lite/v6.json"` to `vega-embed` and emits zero `"The input spec uses Vega-Lite v4.17.0..."` warnings.
- Legacy `selection` objects in v4 specs are converted to `params` without mutating the input `spec` object.
- Existing `v5`/`v6`, schema-less, and `vega` specs render as before.
- Failed `embed(...)` promises display a clear fallback message in `VegaChart` instead of an unhandled promise rejection.
- `npx tsc --noEmit`, `CI=true npm test`, and `npm run build` pass cleanly.

## Out of Scope
- Modifying the Looker Conversational Analytics API output or Looker SDK serialization.
- Downgrading `vega-lite`, `vega`, or `vega-embed` in `package.json`.
- Altering Recharts table/bar chart rendering in `src/components/DataVisualization.tsx`.

## Implementation Checklist (TDD Phases)

### Phase 1: Vega-Lite Spec Normalizer
- [x] Write failing unit tests covering `v4.17.0` / `v5` `$schema` upgrades, `v6` / `vega` / missing-`$schema` pass-through, `selection` → `params` migration, and immutability (Red)
- [x] Implement `normalizeVegaLiteSpec()` cleanly with JSDoc and explicit TypeScript types (Green)
- [x] Verify `CI=true npm test` and `npx tsc --noEmit`

### Phase 2: `VegaChart.tsx` Integration & Async Error Handling
- [x] Write failing component tests in `src/components/VegaChart.test.tsx` verifying `$schema` normalization on `embed(...)` calls and async `embed(...)` rejection fallback UI (Red)
- [x] Integrate `normalizeVegaLiteSpec()` and `await embed(...)` error state into `src/components/VegaChart.tsx` (Green)
- [x] Verify `CI=true npm test`, `npx tsc --noEmit`, and `npm run build` pass cleanly
