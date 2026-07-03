# Control-Plane Rule Seam Map

This note is the refactor map for shrinking the hot control-plane files without
changing behavior first. It inventories the rule families currently concentrated
in `loopx/quota.py` and `loopx/status.py`, names stable extraction seams, and
defines the parity checks that must stay green while code moves.

## Scope

The first refactor branch should make the control plane easier to reason about,
not smarter. Safe work in this phase is limited to:

- inventorying rule families and ownership boundaries;
- adding characterization or parity checks for current behavior;
- extracting pure functions behind the same public CLI/API fields;
- keeping Markdown active state as the human/agent work surface;
- avoiding canonical storage changes until the event/read path contract is
  separately validated.

Do not combine these seams with scoring changes, benchmark runner changes,
private evidence migration, production actions, or public first-screen copy.

## Current Hot Files

| File | Current responsibility | Refactor risk |
| --- | --- | --- |
| `loopx/quota.py` | Quota eligibility, work-lane routing, agent-lane selection, monitor-poll writeback, scheduler hints, interaction contracts, spend events, and quota markdown. | Policy, projection, writeback, and rendering rules can start depending on each other by accident. |
| `loopx/status.py` | Active-state parsing, todo projections, event projection fallback, attention queue, task graph, project assets, status contract, and status markdown. | Read-model construction and display shaping can blur; Markdown parsing remains flexible but weakly typed. |

## Quota Rule Families

| Family | Current anchors | Target seam | Extraction guard |
| --- | --- | --- | --- |
| Work-lane policy | `_work_lane_contract` | Pure policy module that chooses lane, obligation, monitor policy, and reason codes from compact status inputs. | Parity snapshot for advancement, due monitor, external evidence, and quiet skip cases. |
| Capability and boundary gates | `_capability_gate`, `_side_agent_workspace_guard`, `_automation_prompt_upgrade` | Gate evaluators that return typed decisions without mutating payloads. | Existing quota contract fields and workspace guard failure mode remain stable. |
| Agent-lane selection | `_agent_lane_next_action`, `_agent_lane_frontier_hint` | Agent-scoped selector over normalized todo projections. | Current-agent claimed todos outrank unrelated agents; frontier hints stay diagnostic when no runnable candidate exists. |
| Goal frontier and replan decision | `loopx.policies.goal_frontier`, `build_quota_should_run` adapter | Goal-frontier policy owns completion/replan projection; quota only selects the resulting interaction mode. | Required autonomous replan is decided before monitor quiet or agent-scope wait classification, without growing per-agent vision logic inside quota. |
| Agent vision and goal routing contract | Future goal-route policy/CLI adapter plus `goal_vision_replan_contract_v0` | CLI-enforced bounded vision fields and the vision/replan state machine. | Over-budget vision fails or compacts before status/quota; quota consumes projection only and does not own per-agent vision storage. |
| Quota plan and should-run assembly | `build_quota_plan`, `build_quota_should_run` | Thin orchestration layer that merges status, quota accounting, gates, and policy outputs. | `quota should-run` JSON field names and interaction contract stay compatible. |
| User/agent/CLI split | `_protocol_action_packet`, `_interaction_contract` | Protocol packet builder with no scheduler or writeback side effects. | Operator gate vs bounded delivery payloads keep the same action_required and must_attempt meanings. |
| Scheduler policy | `_scheduler_hint` wrapper plus `loopx/policies/scheduler_hint.py` | Pure scheduler-hint builder fed by final decision state. | RRULE, reset token, and no-spend cadence fields stay stable for Codex App and local loops. |
| Monitor writeback | `_quota_decision_due_monitor_item`, `build_quota_monitor_poll_event`, `record_quota_monitor_poll` | Monitor event/writeback module with idempotent todo lookup and next-due projection. | Due-monitor and external-evidence monitor-poll paths remain no-spend and reject non-monitor todos. |
| Spend accounting | `build_quota_slot_spend_event`, `spend_quota_slot` | Quota accounting module with explicit accountable-run lookup. | Spend only after validated writeback; source enum and slot accounting remain unchanged. |
| Markdown rendering | `render_quota_should_run_markdown` and related renderers | Render-only module over already-built payloads. | JSON decisions do not depend on markdown strings. |

## Status Rule Families

| Family | Current anchors | Target seam | Extraction guard |
| --- | --- | --- | --- |
| Active-state parsing | `parse_state_frontmatter`, `parse_active_state_todos`, `structured_todo_item` | Typed active-state projection module that preserves Markdown as the editable workbench. | Existing TODO syntax, priority parsing, `claimed_by`, and metadata fields continue to parse. |
| Event-backed active projection | `active_state_event_projection_fields` | Read-path projection adapter that can fall back to Markdown with explicit warnings. | Event projection warnings remain visible; fallback does not silently hide malformed state. |
| Todo summary/read models | `compact_todo_group`, `todo_item_is_due_monitor`, `apply_resume_conditions` | Todo projection module with explicit runnable, blocked, deferred, due-monitor, and visibility lanes. | Due monitor means `task_class=continuous_monitor` plus `next_due_at<=now`; external evidence watch stays separate. |
| Hygiene and repair signals | `backlog_hygiene_warning`, `build_autonomous_replan_obligation` | Health-signal module consumed by status and quota. | Repair obligations remain machine-readable and cannot be cleared by empty acknowledgements. |
| Project assets | `build_project_asset` | Public-safe asset packer over status and run-history inputs. | Project-asset-backed queue items remain the only authority for owner/gate/stop-condition semantics. |
| Attention queue | `build_attention_queue` | Queue builder over normalized goal status, todos, gates, and project assets. | Queue ordering and truncation limits remain explicit and stable. |
| Task graph projection | `loopx.projections.task_graph.build_task_graph_projection` with `loopx.status.build_task_graph_projection` as the compatibility wrapper | Read-only graph projection module. | Node caps include truncation metadata; full cold-path detail remains outside the hot graph. |
| Status contract assembly | `build_status_contract`, `collect_status` | Thin collector/orchestrator that wires registry, runtime, state, and read models. | CLI status JSON shape remains compatible. |
| Markdown rendering | `render_status_markdown` plus `loopx/renderers/status_markdown.py` | Render-only module/helpers over the status payload. | Rendering cannot become the source of scheduler or quota truth. |

## Proposed Extraction Order

1. Characterize the current behavior.
   Keep `examples/control_plane/control-plane-risk-characterization-smoke.py` green and add
   focused parity fixtures before moving rules.
2. Extract active-state and todo read models.
   This reduces Markdown parsing risk while preserving Markdown as the work
   surface.
3. Extract quota policy functions.
   Move pure work-lane, agent-lane, and scheduler decisions behind the existing
   `build_quota_should_run` API.
4. Extract rendering last.
   Rendering is safest to move after JSON/read-model payloads are stable.
5. Only then revisit write correctness.
   Per-goal locks, idempotency keys, optimistic revision checks, and lease
   projection should land as a separate contract with non-destructive smokes.

## Non-Negotiable Invariants

- `quota should-run` remains the source of truth for automation permission.
- `interaction_contract` remains the source of truth for user/agent/CLI
  responsibilities.
- `agent_lane_next_action` is per-agent runnable routing; `## Next Action` is
  durable goal-level guidance.
- `goal_route_hint` may summarize current, other-agent, and unclaimed lane
  signals for hosts, but it is read-only advisory projection and must preserve
  shared `## Next Action`.
- `goal_frontier_projection` is the small per-goal completion/replan view used
  before lane-local quiet/wait decisions; keep its policy in
  `loopx.policies.goal_frontier` rather than expanding `quota.py`.
- Per-agent vision is a bounded goal-routing contract, not free-form planning
  memory. Enforce its character budget at the CLI/write boundary; store verbose
  rationale as evidence/docs; let replan patch vision only through the bounded
  contract.
- Monitor routing is attribute based, not name based:
  `task_class=continuous_monitor` plus due metadata defines due monitor work,
  while `waiting_on=external_evidence` or
  `waiting_on=external_evidence_observation` defines external evidence watch.
- Hot-path projections may cap expanded detail, but must publish truncation
  metadata and keep full detail available through cold-path surfaces.
- Public docs, examples, and fixtures must not include private links, local
  paths, raw benchmark logs, raw trajectories, credentials, or internal
  operating context.

## Validation Matrix

| Refactor slice | Required validation before push |
| --- | --- |
| Seam-map/docs only | `git diff --check`; `loopx check` on changed docs; public/private boundary scan. |
| Active-state/todo projection extraction | Characterization smoke plus focused parser fixtures and `py_compile` for touched modules. |
| Quota policy extraction | Characterization smoke plus quota-plan/contract smokes, focused policy parity smokes, and `quota should-run` JSON parity fixtures. |
| Status read-model extraction | Characterization smoke plus status/task-graph/cold-path projection smokes. |
| Scheduler/monitor extraction | Monitor cadence CLI smokes, monitor-poll writeback smokes, and no-spend spend-accounting checks. |
| Write correctness contract | Non-destructive lock/idempotency/CAS/lease smokes; no migration of canonical state without owner approval. |

## Stop Conditions

Stop the refactor branch and ask for review when a slice needs to:

- remove or rename a public JSON field consumed by status, quota, dashboard, or
  review packet users;
- change benchmark runner behavior, scoring, or case task semantics;
- migrate canonical todo/history storage;
- alter public first-screen presentation;
- depend on private source material or raw local artifacts.
