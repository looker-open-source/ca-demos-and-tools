# Repository Agent Guide (Context- & Spec-Driven Development)

This repository follows **Context- and Spec-Driven Development** (*"Measure twice, code once"*). Treat project context and feature specs as living artifacts alongside code.

## 1. Living Context Map
Before designing or modifying features, read the relevant context documents:
- **Product Definition:** [docs/context/product.md](docs/context/product.md) — Goals, target audience, and key features.
- **Product Guidelines:** [docs/context/product-guidelines.md](docs/context/product-guidelines.md) — Reference-code prose, dark-mode + neon-cyan UX, and streaming-first principles.
- **Tech Stack & Architecture:** [docs/context/tech-stack.md](docs/context/tech-stack.md) — Next.js App Router, Looker SDK (`@looker/sdk-node` 26.4+), OAuth PKCE, Zustand, Vitest.
- **Feature Specs:** `docs/specs/` (template at [docs/specs/TEMPLATE.md](docs/specs/TEMPLATE.md)).

## 2. Development Workflow
1. **Context First:** Review `docs/context/*.md` and relevant files in `src/` before proposing changes.
2. **Spec & Plan Before Code:** For new features or non-trivial changes, clarify requirements and align on a spec/plan before editing `src/`:
   - Use `/new-spec` to scaffold a committed spec in `docs/specs/<YYYY-MM-DD>-<slug>.md`.
   - Use `/grill-me` to resolve design ambiguities and `/plan` for technical approval.
3. **Test-First Implementation:** Follow TDD (Red -> Green -> Refactor) with Vitest (`CI=true npm test`). Use `/goal` for large multi-phase executions.
4. **Verify & Review:** Run tests, lint, and type checks; use `/review-agent` to audit diffs against specs and `.agents/rules/`.
5. **Sync Living Context:** Propose updates to `docs/context/product.md` or `docs/context/tech-stack.md` whenever user-facing features, auth flows, or dependencies change (and update `docs/context/tech-stack.md` *before* introducing new libraries).

## 3. Architectural Guardrails
- **Looker SDK Only:** Route all Conversational Analytics interactions through `@looker/sdk-node` (`26.4+`), **never** directly to `geminidataanalytics.googleapis.com`.
- **Explicit History Persistence:** Preserve post-stream Looker conversation persistence (`persistLookerMessages()` in `src/lib/looker-conversation.ts`).
- **Dual-Mode Auth:** Maintain compatibility with both Service Account (`NEXT_PUBLIC_LOOKER_AUTH_MODE=env`) and User OAuth 2.0 PKCE (`oauth` + `/api/token/refresh`) flows.
- **Silent Query Cancellation:** Agent switches and session resets must abort active streams cleanly without surfacing cancellation noise in the UI.

## 4. Standard Commands
```bash
npm install               # Install dependencies
npm run dev               # Start Next.js dev server (http://localhost:3000)
CI=true npm test          # Run Vitest unit/component test suite once
npm run lint              # Run ESLint (eslint-config-next)
npx tsc --noEmit          # Run TypeScript type check
npm run build             # Production Next.js build
```
