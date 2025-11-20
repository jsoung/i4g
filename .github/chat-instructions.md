---
applyTo: "**/*.ts,**/*.tsx"
---
# Project coding standards for TypeScript and React

Apply the [general coding guidelines](./general-coding.instructions.md) to all code.

## TypeScript Guidelines
- Use TypeScript for all new code (the Next.js console under `apps/web/` is typed end-to-end).
- Favor functional programming patterns: pure utility helpers, composable hooks, and data transformations without side effects.
- Model data with interfaces or type aliases that mirror the FastAPI payloads (see `proto` `/reviews` schemas for source of truth).
- Prefer immutable data (`const`, `readonly`) and express intent with discriminated unions when branching on statuses.
- Use optional chaining (`?.`) and nullish coalescing (`??`) for defensive access, especially around API responses.

## React Guidelines
- Use functional components with hooks; follow React hook rules (no conditional hooks, consistent dependency arrays).
- Type components with `React.FC` only when children are required; otherwise prefer explicit prop types for clarity.
- Keep components small and focused—move derived state into custom hooks under `apps/web/src/hooks/` when logic grows.
- Style via CSS modules or the shared design tokens (`@i4g/ui-kit`); avoid inline styles except for dynamic values.
- Snapshot backend interactions in Storybook/Playwright fixtures so UI regressions can be validated without live API calls.
