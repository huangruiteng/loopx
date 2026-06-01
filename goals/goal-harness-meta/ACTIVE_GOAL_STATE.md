---
status: active-read-only
owner_mode: goal
objective: "Keep the public Goal Harness repo runnable, understandable, and safe to reuse"
updated_at: 2026-06-01T11:36:00+08:00
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

- Maintain a compact self-health run in the shared runtime, then use it to drive
  the next public product segment: richer status UI/data export, adapter
  templates, or controller/sub-agent coordination examples.

## Validation

- `python3 -m py_compile goal_harness/*.py`
- `python3 -m goal_harness.cli --help`
- `python3 -m goal_harness.cli --format json check --scan-root .`
- Parse all JSON examples in `examples/`.

## Guards

- Do not copy private registry entries, project paths, document links, task ids,
  credentials, or raw run payloads into public examples.
- Keep runtime data local; commit only sanitized docs, source, and examples.
- Prefer small, verified public-facing changes over broad rewrites.
