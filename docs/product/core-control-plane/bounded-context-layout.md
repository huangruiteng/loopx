# Bounded Context Layout

LoopX control-plane code is moving from a flat collection of status/quota helper
modules toward bounded contexts. The goal is to keep the open-source kernel
readable: source parsing, policy selection, projection shaping, and rendering
should not all accumulate in one generic namespace.

## Package Shape

New control-plane code should live under `loopx.control_plane`:

| Context | Responsibility |
| --- | --- |
| `work_items` | Attention items, work-item selection, work-item read models, lifecycle and delivery signals. |
| `goals` | Goal state, active-state sections, registry health, and goal-level planning surfaces. |
| `todos` | Todo parsing summaries, todo-derived attention helpers, and todo handoff summaries. |
| `agents` | Agent-scope filtering, lane recommendation, capability gates, and subagent activity. |
| `quota` | Quota-specific control-plane helpers. |
| `scheduler` | Scheduler-facing monitor display and cadence helpers. |
| `runtime` | Runtime/session projections and run-compaction helpers. |
| `handoff` | Handoff readiness, handoff state, and handoff-run classification. |

The legacy `loopx.projections` namespace remains available as a compatibility
shim for existing examples and external imports, but implementation code should
not be added there by default.

## Projection Boundary

A projection is a derived read model with a stable consumer contract. It should
be:

- deterministic from public-safe source state;
- side-effect free;
- small enough for hot status/quota/dashboard surfaces;
- consumed through a named contract rather than copied across renderers.

Not every extracted helper is a projection. Selection rules belong near the
domain policy, parser helpers belong near the state they parse, and renderer
formatting belongs in the sink. If a module is moved only because a source file
is too long, choose the bounded context first and the `projection.py` name only
when it really exposes a read model contract.

## Migration Rule

When moving an existing module:

1. Move the implementation into the owning bounded context.
2. Update LoopX runtime imports to the new context path.
3. Keep a thin `loopx.projections.<module>` compatibility shim when public
   examples, docs, or downstream callers already import it.
4. Add or keep a focused smoke that exercises both the runtime path and the
   compatibility path.
5. Remove the shim only in a deliberate compatibility-breaking release.

This keeps the kernel architecture clean without forcing every downstream
consumer to migrate in the same PR.
