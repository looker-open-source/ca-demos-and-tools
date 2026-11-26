# Spec: <Feature or Change Title>

- **Status:** Draft | Approved | Implemented
- **Created:** YYYY-MM-DD

## Overview & Problem Statement
What problem are we solving, why does it matter for this reference demo, and who benefits?

## Functional Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## Non-Functional Requirements
- Performance, streaming responsiveness, auth compatibility (`env` and `oauth`), or reference-code clarity constraints.

## Acceptance Criteria
- Concrete, testable behaviors that prove the feature works end-to-end.

## Out of Scope
- Explicit boundaries to prevent scope creep.

## Implementation Checklist (TDD Phases)

### Phase 1: <Core Logic / API / State>
- [ ] Write failing unit tests (`src/.../__tests__/*.test.ts`)
- [ ] Implement minimal code to pass tests
- [ ] Verify `CI=true npm test` and `npx tsc --noEmit`

### Phase 2: <UI & Integration>
- [ ] Write failing component/integration tests (`src/.../__tests__/*.test.tsx`)
- [ ] Implement UI components following `docs/context/product-guidelines.md`
- [ ] Verify `CI=true npm test`, `npm run lint`, and manual browser check (`npm run dev`)
- [ ] Sync `docs/context/` if product capabilities, auth flows, or tech stack changed
