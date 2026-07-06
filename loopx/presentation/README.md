# LoopX Presentation Layer

This directory owns the code that turns LoopX state into human-facing display
surfaces. It must not become the control-plane source of truth.

## Layout

| Directory | Owns | Does not own |
| --- | --- | --- |
| `renderers/` | Transport-neutral text or Markdown rendering over already-built LoopX payloads. | Scheduler, quota, todo, or evidence decisions. |
| `sinks/` | External display sinks such as Lark/Feishu tables and cards. | Connector login authority, private reads, or production actions. |
| `projections/` | Future display-specific intermediate read models that join or reshape public-safe LoopX evidence for surfaces. | Persistent control state or benchmark scoring. |

Python code that starts as a user-visible capability may keep a thin facade
under `loopx.capabilities.*`, but the reusable display implementation should
live here.

## Explore Result Layer

Only the display side of software-exploration topology belongs here:

- graph/table/card projections that only reshape public-safe explore state for
  humans may live in `loopx/presentation/projections/explore/`;
- Lark/Feishu table sync and card output live in
  `loopx/presentation/sinks/lark/`;
- the core explore log, findings, and replan briefing inputs remain in the
  explore capability or a future control-plane explore/read-model boundary.

That keeps topology cards, tables, and graph views close to the dashboard
without turning presentation code into the source of evidence for vision and
replan.
