# Spec: Fix TypeScript, Module Import, and Test Suite Errors

- **Status:** Implemented
- **Created:** 2026-11-18

## Overview & Problem Statement
The repository currently fails `npx tsc --noEmit` (11 errors across 6 test files), fails `CI=true npm test` (13 of 46 test files / 38 tests failing due to outdated mocks after OAuth and `useRouter` updates), and imports `@looker/sdk` / `@looker/sdk/lib/4.0/*` directly despite `@looker/sdk` only being installed transitively via `@looker/sdk-node`. Resolving these issues restores clean IDE type resolution (including `next/navigation` in `src/app/page.tsx` and `@looker/sdk/lib/4.0/models` in `src/lib/looker-conversation.ts`), green TypeScript checks, and a passing Vitest suite as a reliable reference codebase.

> **Living Context Impact:** If `@looker/sdk` (`26.4.0`) is added as an explicit direct dependency in `package.json`, `docs/context/tech-stack.md` will be updated to note `@looker/sdk` alongside `@looker/sdk-node` and `@looker/sdk-rtl`.

## Functional Requirements
- [ ] **Direct Looker SDK Dependency & Import Audit:**
  - Audit all imports from `@looker/sdk` and `@looker/sdk/lib/4.0/*` across `src/lib/` (`src/lib/looker-conversation.ts`, `src/lib/looker-agent.ts`, `src/lib/looker-sdk.ts`, and any remaining callers).
  - Declare `@looker/sdk` (`^26.4.0`, already present in Airlock via `@looker/sdk-node`) directly in `package.json` (and `package-lock.json`) or import via `@looker/sdk-node` where exported, so module resolution never relies on transitive npm hoisting.
  - Verify `next/navigation` type declarations resolve cleanly in `src/app/page.tsx` under `tsconfig.json`.
- [ ] **Fix All `npx tsc --noEmit` Errors (11 errors in 6 files):**
  - `src/app/api/agents/route.test.ts`: Pass a properly typed mock `NextRequest` (with `headers.get`) to `GET(req)`.
  - `src/app/api/conversations/[id]/messages/route.test.ts`: Replace `{} as Request` with a typed `NextRequest` mock containing `headers`.
  - `src/app/api/conversations/[id]/route.test.ts`: Replace `{} as Request` and `as any` request mocks with typed `NextRequest` mocks containing `headers`.
  - `src/lib/dev-logger/__tests__/store.test.ts`: Supply required `method` and `startTime` fields to `addLog(...)` matching `DevLogEntry`.
  - `src/lib/log-utils.test.ts`: Replace read-only `process.env.NODE_ENV = ...` assignments with `vi.stubEnv('NODE_ENV', ...)` and `vi.unstubAllEnvs()`.
  - `src/store/useAuthStore.test.ts`: Import `afterEach` from `'vitest'`.
- [ ] **Fix Failing Vitest Runtime Tests Across Remaining Test Files:**
  - `src/app/api/conversations/search/route.test.ts`: Provide `NextRequest` mocks with `headers.get` and `nextUrl.searchParams` as expected by `GET(req)`.
  - Home page test suites (`src/app/page.test.tsx`, `src/app/agent-caching.test.tsx`, `src/app/conversation-selection.test.tsx`, `src/app/data-viz-rendering.test.tsx`, `src/app/initial-load.test.tsx`, `src/app/layout-constraints.test.tsx`): Provide `next/navigation` (`useRouter`) and `useLookerAuth` (`authConfig`) mocks aligned with `src/app/page.tsx`.
  - Update outdated mocks/assertions in `src/components/LookerAuthProvider.test.tsx`, `src/components/ChatWindow.test.tsx`, and `src/store/useChatStore.test.ts`.

## Non-Functional Requirements
- Maintain strict TypeScript (`"strict": true` in `tsconfig.json`) without suppressing errors via `@ts-ignore`, `@ts-expect-error`, or excluding test files from `tsconfig.json`.
- Keep all Conversational Analytics interactions routed through `@looker/sdk-node` / `@looker/sdk` (never directly to `geminidataanalytics.googleapis.com`).
- Ensure any dependency change in `package.json` / `package-lock.json` remains compatible with the current Airlock npm cache (`next@16.4.1`, `@looker/sdk@26.4.0`).
- Preserve existing behavior for both Service Account (`env`) and User OAuth 2.0 PKCE (`oauth`) authentication modes.

## Acceptance Criteria
- `npx tsc --noEmit` exits `0` with zero errors (including clean resolution of `next/navigation` and `@looker/sdk/lib/4.0/models`).
- `CI=true npm test` exits `0` with all 46 test files / 165 tests passing and zero skipped tests.
- `npm run lint` exits `0` with zero errors.
- `npm run build` exits `0`.
- `docs/context/tech-stack.md` is synced if `@looker/sdk` is added as a direct dependency in `package.json`.

## Out of Scope
- Upgrading `next` to `16.4.5` (pending Airlock availability).
- Changing runtime application behavior, UI layout, or API contracts beyond what is required for type-safe imports and accurate test mocks.
- Refactoring shared test harnesses across unrelated passing test files.

## Implementation Checklist (TDD Phases)

### Phase 1: Dependencies, Module Imports & API Route Type/Test Fixes
- [x] Audit `@looker/sdk` / `@looker/sdk/lib/4.0/*` imports in `src/lib/` and declare `@looker/sdk` directly in `package.json` (syncing `docs/context/tech-stack.md` if modified)
- [x] Confirm `npx tsc --noEmit` fails on the 11 known test errors (Red)
- [x] Fix TypeScript and `NextRequest`/`headers` mock issues in `src/app/api/**/route.test.ts`, `src/lib/dev-logger/__tests__/store.test.ts`, `src/lib/log-utils.test.ts`, and `src/store/useAuthStore.test.ts`
- [x] Verify `npx tsc --noEmit` passes (`0` errors) and all API route & store/lib tests pass in Vitest (Green)

### Phase 2: Home Page & Component Test Alignment + Full Quality Gates
- [x] Update `useRouter` (`next/navigation`) and `useLookerAuth` (`authConfig`) mocks in `src/app/*.test.tsx` and update outdated assertions in `src/components/LookerAuthProvider.test.tsx`, `src/components/ChatWindow.test.tsx`, and `src/store/useChatStore.test.ts`
- [x] Verify `CI=true npm test` passes across all 46 test files
- [ ] Verify `npx tsc --noEmit`, `npm run lint`, and `npm run build` all pass cleanly (`npx tsc --noEmit` and `npm run build` pass; `npm run lint` failed due to Next.js 16 removing `next lint` and `npx eslint src/` flagged pre-existing React 19 `set-state-in-effect` / `react/no-unescaped-entities` errors in untouched UI components)
