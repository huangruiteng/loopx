---
status: active-read-only
owner_mode: goal
objective: "Keep the public Goal Harness repo runnable, understandable, and safe to reuse"
updated_at: 2026-06-01T11:59:59+08:00
---

# Goal Harness Meta Goal

## Objective

Keep the public Goal Harness project healthy enough that another local Codex
thread can bootstrap a goal, inspect registry and run history, check public
boundary safety, and render a first-screen status queue without relying on any
private project context.

## Current Scope

- Keep `goal-harness bootstrap`, `goal-harness check`, and `goal-harness status`
  runnable from a fresh clone.
- Keep docs and examples aligned with the current CLI surface.
- Keep public examples sanitized: no local user paths, private documents,
  credentials, raw logs, or internal task identifiers.
- Treat project-specific adapters as private until their contract is generic
  enough to document publicly.

## Next Action

- Scaffold `apps/dashboard` with Vite + React + TypeScript + shadcn/ui +
  TanStack Router/Table, then render `examples/status.example.json` as the
  first real control-plane screen.

## Recent Progress

- 2026-06-01T11:43:29+08:00: Added `docs/status-data-contract.md`,
  linked it from README / architecture / attention queue / integration docs,
  pushed the public commit, and saved a compact self-health run with
  `health_check=22/22`.
- 2026-06-01T11:48:36+08:00: Added
  `examples/render-status-dashboard.py`, documented the static dashboard demo,
  and validated that `examples/status.example.json` renders to a local HTML
  dashboard with user/controller, Codex-ready, and external-evidence lanes.
- 2026-06-01T11:59:59+08:00: Added
  `docs/dashboard-frontend-selection.md`, reframed the single-file HTML
  renderer as a diagnostic fallback, and selected a React/Vite/shadcn/TanStack
  stack for the product dashboard after benchmarking observability and
  orchestration consoles.

## Validation

- `python3 -m py_compile goal_harness/*.py`
- `python3 -m goal_harness.cli --help`
- `python3 -m goal_harness.cli --format json check --scan-root .`
- Parse all JSON examples in `examples/`.
- `python3 -m goal_harness.cli --format json check --scan-path README.md --scan-path docs/dashboard-frontend-selection.md --scan-path docs/status-data-contract.md`

## Guards

- Do not copy private registry entries, project paths, document links, task ids,
  credentials, or raw run payloads into public examples.
- Keep runtime data local; commit only sanitized docs, source, and examples.
- Prefer small, verified public-facing changes over broad rewrites.
