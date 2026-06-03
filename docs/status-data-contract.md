# Status Data Contract

`goal-harness --format json status` is the stable first-screen data contract for
agents, heartbeat jobs, dashboards, and local UI experiments.

The command is an export: it reads the registry, compact run indexes, and the
public/private contract check, then emits one JSON object. It does not inspect
private run payloads beyond compact index fields and does not mutate files.
The export is agent-facing machine state. A dashboard should consume this
contract and translate it into a human operator view rather than treating raw
CLI fields as product copy.

When a command is run outside a project-local `.goal-harness/registry.json`,
the CLI falls back to the shared local global registry at
`~/.codex/goal-harness/registry.global.json` if it exists. That registry is
maintained automatically by `connect` and `refresh-state` so each project agent
can update its own local state while dashboards still see the multi-project
view.

For local dashboards, the same JSON shape can be served over loopback HTTP:

```bash
goal-harness serve-status --port 8765
```

The default endpoint is `http://127.0.0.1:8765/status.json`. It is intended for
local dashboard development and includes CORS headers so a Vite app on another
localhost port can fetch it.

The same local server exposes `POST /reward/dry-run` for dashboard reward
validation. It accepts the selected `goal_id`, `run_generated_at`, compact
reward fields, and public-safe summary text, then returns a compact validation
result with `appended=false`. It also returns the same coordination fields as
the CLI: `active_state_summary` and `project_agent_visibility`. It does not
mutate the run index and does not return private artifact paths.

## Command

```bash
goal-harness --format json status > goal-status.json
```

By default, `status` scans the Goal Harness install root for public/private
contract health. Use narrow scan paths only when you intentionally want the
status export to check a specific public-safe project surface:

```bash
goal-harness --format json status \
  --scan-path README.md \
  --scan-path docs/ \
  --scan-path examples/
```

For compute allocation, `goal-harness quota status` and
`goal-harness quota plan` derive an agent-facing grouping from this same status
payload. `goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json"
quota should-run --goal-id <goal-id>` derives a per-goal automation guard from
that grouping for project heartbeats. These are read-only views, not a separate
source of truth. Scripts should treat `summary.next_automatic_turn` in the
quota-plan JSON as advisory and still respect the displayed health, operator,
and evidence gates.
For spend accounting, status derives `spent_slots` from compact
`quota_slot_spent` runtime events in the current quota window. The registry
remains the policy source for compute share and window size, not the spend
ledger.
`quota_slot_spent` is status-neutral accounting: it must remain visible in run
history for quota audit, but status and attention queues should use the latest
non-accounting run as the current work state.
In lane terms, `next_automatic_turn` may only name the first eligible goal;
operator-gated, waiting, throttled, paused, and health-blocked goals must stay
out of the eligible lane even when they have a high `quota.compute`.

## Top-Level Shape

```json
{
  "ok": true,
  "registry": ".goal-harness/registry.json",
  "runtime_root": "./runtime",
  "goal_count": 3,
  "run_count": 2,
  "contract": {
    "ok": true,
    "summary": {
      "errors": 0,
      "warnings": 0,
      "checks": 4
    },
    "errors": [],
    "warnings": [],
    "checks": [
      "registry goals checked: 3",
      "runtime indexes checked: 3",
      "run-history goals=3 runs=2",
      "public boundary scan clean: 12 files"
    ]
  },
  "global_registry": {
    "available": true,
    "ok": true,
    "registry": "~/.codex/goal-harness/registry.global.json",
    "current_registry": ".goal-harness/registry.json",
    "current_registry_is_global": false,
    "global_goal_count": 4,
    "current_goal_count": 3,
    "source_registry_count": 2,
    "summary": {
      "high": 0,
      "action": 0,
      "info": 1,
      "checks": 2,
      "findings": 1
    },
    "findings": [],
    "checks": []
  },
  "attention_queue": {
    "available": true,
    "item_count": 2,
    "needs_user_or_controller": 1,
    "needs_controller": 0,
    "needs_codex": 1,
    "watching_external_evidence": 0,
    "items": []
  },
  "run_history": {
    "available": true,
    "goal_count": 3,
    "run_count": 2,
    "goals": [],
    "recent_runs": []
  }
}
```

Consumers should treat unknown fields as additive. Required fields for a
first-screen UI are `ok`, `contract`, and `attention_queue`.

## Global Registry Health

`global_registry` is the local multi-project health surface. It checks the
shared `registry.global.json` even when the current command is pointed at a
project-local registry, so dashboard users can see registry scope problems
before they turn into ghost projects.

Health findings are compact and local-only. They may include local filesystem
paths in a developer machine export, so do not publish a raw local status JSON
outside the machine.

Finding shape:

```json
{
  "kind": "stale_source_registry",
  "severity": "action",
  "goal_id": "project-main-control",
  "message": "`project-main-control` source registry changed after its last global sync",
  "recommended_action": "run `goal-harness sync-global --goal-id project-main-control` from the source project",
  "path": "/path/to/project/.goal-harness/registry.json"
}
```

Current finding kinds:

- `duplicate_goal_id`: the global registry contains more than one entry for the
  same goal id; this is high severity because routing is ambiguous.
- `source_registry_missing`: a global entry points at a source registry that no
  longer exists.
- `stale_source_registry`: the source registry changed after the last recorded
  `synced_at`, so the global entry may be stale.
- `state_file_missing`: the goal's declared active state file no longer exists.
- `state_file_not_declared`: the global entry has no durable active state file.
- `current_registry_scope_excludes_global_goals`: informational reminder that a
  project-local registry view excludes goals that are present in the shared
  global registry.

High and action findings are also lifted into `attention_queue.items` with
`source=global_registry`; informational scope findings stay in the global
registry panel so local project views are not noisy.

## Contract Health

`contract.ok=false` means the UI should show a blocking health state before
encouraging more adapter work.

The summary counters are intentionally small:

- `errors`: boundary or registry problems that should block progress.
- `warnings`: non-blocking issues worth showing in a secondary health panel.
- `checks`: successful observations, useful for audit trails.

`errors`, `warnings`, and `checks` are short strings. Checks should be concrete
enough to support an operator decision without exposing local paths or private
evidence. They must be public-safe before a project exposes this export outside
the local machine.

## Attention Queue

The attention queue is sorted by Goal Harness status logic. A UI should render
it as the primary worklist.

Counters:

- `item_count`: all visible queue items.
- `needs_user_or_controller`: items waiting on either a human user or a target
  controller.
- `needs_controller`: subset waiting on a target controller or adapter
  connection.
- `needs_codex`: items ready for a Codex action.
- `watching_external_evidence`: items that should be monitored but not acted on
  until outside evidence changes.

Item shape:

```json
{
  "goal_id": "complex-project-main-control",
  "status": "ready_for_controller_opt_in",
  "lifecycle_phase": "controller_gated",
  "lifecycle_flags": [
    "controller_gated",
    "adapter_inspected"
  ],
  "waiting_on": "user_or_controller",
  "severity": "action",
  "recommended_action": "先在 Goal Harness 完成 operator 判断；同意后项目 Agent 只执行 read-only map dry-run",
  "project_asset": {
    "owner": "user_or_controller",
    "gate": "operator_question",
    "next_action": "先在 Goal Harness 完成 operator 判断；同意后项目 Agent 只执行 read-only map dry-run",
    "stop_condition": "record aligned eval evidence and one human reward event",
    "user_todos": {
      "open": 1,
      "done": 2,
      "total": 3,
      "next": "Record the owner/SOP conclusion in the review worksheet."
    },
    "agent_todos": {
      "open": 1,
      "done": 0,
      "total": 1,
      "next": "Run the read-only validation map after approval."
    },
    "quota": {
      "compute": 0.5,
      "state": "operator_gate",
      "spent_slots": 0,
      "allowed_slots": 720,
      "reason": "operator gate blocks gated delivery"
    },
    "latest_validation": {
      "generated_at": "2026-06-02T12:00:00+00:00",
      "classification": "ready_for_controller_opt_in",
      "summary": "read-only map available; write-control not approved"
    }
  },
  "operator_question": "是否同意 `complex-project-main-control` 先执行 read-only map opt-in？",
  "agent_command": "goal-harness read-only-map --goal-id complex-project-main-control --dry-run",
  "quota": {
    "compute": 0.5,
    "window_hours": 24,
    "slot_minutes": 1,
    "allowed_slots": 720,
    "spent_slots": 0,
    "state": "operator_gate",
    "reason": "planned goal needs operator opt-in before spending agent turns"
  },
  "source": "latest_run",
  "controller_stage": "ready_for_read_only_not_decision",
  "missing_gates": [
    "human_reward_capture",
    "aligned_eval_decision_evidence"
  ],
  "next_handoff_condition": "record aligned eval evidence and one human reward event"
}
```

Item fields:

- `goal_id`: stable goal identifier from registry or runtime.
- `status`: adapter classification or derived status.
- `lifecycle_phase`: derived state-interaction phase for first-screen
  visualization.
- `lifecycle_flags`: all compact phases that apply to the latest state.
- `waiting_on`: `user_or_controller`, `controller`, `codex`, or
  `external_evidence`.
- `severity`: `high`, `action`, or `watch`.
- `recommended_action`: exactly one next action.
- `project_asset`: a compact control-plane projection derived from the same
  item. It must carry `owner`, `gate`, `next_action`, and `stop_condition`, and
  may include compact `user_todos`, `agent_todos`, `quota`, and
  `latest_validation` summaries. This is the first-screen project asset surface
  for agents and dashboards; it lets consumers avoid reconstructing owner,
  gate, next action, stop condition, todo counts, compute state, and latest
  validation from scattered fields. Markdown renderers should include the first
  unfinished user and agent todo here when available, so hot-path readers do not
  need to scan the detailed todo sections. The richer top-level `user_todos`,
  `agent_todos`, and `quota` fields remain available for detailed views.
- Current routing authority: consumers should choose the current owner, gate,
  waiting party, and next action from `attention_queue.items` and its
  `project_asset`. `run_history.latest_runs` is an evidence and drill-down
  surface; it may be limited by status command limits or filters, so consumers
  must not use it as the sole source for deciding whether a gate is still
  pending or already approved.
- `operator_question`: optional human-facing gate to show in the Goal Harness
  operator view. This is the canonical place for user/controller judgment.
- `agent_command`: optional command or instruction for the target project agent
  after the operator gate is approved. Dashboard consumers should not treat it
  as approval by itself.
- `quota`: optional compact compute-quota state. It should summarize the
  compute share (`1.0`, `0.5`, `0.3`, or `0`), eligibility, recent spend, and
  a public-safe reason without exposing private evidence. See
  [quota-allocation.md](quota-allocation.md).
- `user_todos`: optional checkbox summary parsed from the active state's
  `## User Todo ...` / `## Owner Review Reading Queue` section. Dashboard
  consumers should render the first unfinished item as the human-facing next
  step, while keeping `recommended_action` as routing context.
- `agent_todos`: optional checkbox summary parsed from `## Agent Todo`,
  `## Codex Todo`, or `## Project Agent Todo`. Agent-facing consumers may use
  it to choose implementation work after gates and quota allow execution; it is
  not a user approval signal.
- `todo_state_file`: optional local path to the active state file that produced
  `user_todos` / `agent_todos`.
- `source`: `contract`, `registry`, `run_history`, or `latest_run`.
- `controller_stage`: optional compact controller-readiness classification from
  the latest run.
- `missing_gates`: optional public-safe gate ids that explain why a goal cannot
  advance to the next controller stage yet.
- `next_handoff_condition`: optional public-safe condition for advancing the
  controller handoff.

`status=unregistered_runtime_goal` is emitted when runtime has an actionable
goal that is not present in the registry. Dashboard consumers should show this
as controller work: register the goal if it is active, or archive the runtime
record if it is old. Watch-only legacy records remain visible in run history
without entering the queue.

`status=state_refreshed` is emitted for registered goals when the latest compact
run came from `goal-harness refresh-state`. Dashboard consumers should show it
as Codex-ready work: the controller state changed, and the next agent turn
should inspect the refreshed active state before continuing.
If the refresh command was run without `--recommended-action`, the compact
`recommended_action` should be the first public-safe item from the refreshed
active state's `## Next Action`, including wrapped continuation lines;
otherwise it falls back to a generic refresh notice.

Registry entries may override first-screen attention with optional public-safe
fields: `waiting_on`, `attention_status`, `recommended_action`,
`operator_question`, and `next_handoff_condition`. Status respects this before
classifying the latest run, so a goal with a fresh `state_refreshed` record can
still remain in `waiting_on=user_or_controller` when the active state says a
human or target controller decision is the real next gate. This is intended for
state-truth corrections, not for granting project-agent execution. Global
registry sync preserves an existing attention override when a different later
source for the same goal omits these fields, so a controller-authored gate is
not accidentally lost during ordinary project sync. When the same source
registry syncs again and omits these fields, that source is treated as
authoritative and the stale override is cleared. A syncing registry entry can
also set `clear_attention_override=true` to clear an override explicitly.

Todo extraction is independent of attention overrides. A goal can stay in the
operator lane because the registry says `waiting_on=user_or_controller`, while
the active state exposes a more concrete user checklist. This is the preferred
shape for complex project review: keep `recommended_action` short enough to
route the queue, and put ordered user work in checkbox sections the dashboard
can summarize.

For registered planned high-complexity goals with a compatible
`*_read_only_map_v0` adapter and no run yet, status keeps the queue item in
`waiting_on=user_or_controller`, emits an `operator_question` for the Goal
Harness operator view, and puts the dry-run preview in `agent_command`. The
preview should report `opt_in_required=true` and append nothing; dashboard
consumers must not treat the command as controller opt-in or a durable map run.
The human-readable Markdown status view may also render an
`operator_gate_dry_run` helper before `agent_command`; that helper is a
user-owned gate recording preview, not a JSON contract field or project-agent
command.
Executor-facing guards are stricter than status display: `quota should-run`
must keep these planned items at `should_run=false`, `state=operator_gate`, and
must not include `agent_command` until an approved operator-gate run makes the
goal eligible. This keeps a preview command from becoming an automatic project
agent handoff. When the quota payload includes `agent_todo_summary`, the target
project agent can use it as the safe follow-up checklist for its own next action
instead of re-reading chat history. When the quota payload includes
`safe_bypass_allowed=true`, that permission only covers independent read-only
steering or analysis from the active state's priority stack; it still must not
execute the gated preview command, adapter work, write-control, or production
actions. When the payload also includes `gate_prompt`, `operator_question`,
`user_todo_summary`, or `agent_todo_summary`, the executor should ask that
concrete gate in the visible thread with `NOTIFY` unless the same unresolved
gate was already asked recently; the guard should not collapse a user decision
into a silent skip.

Review Packet source-of-truth rule:

- the dashboard/operator view owns the human decision;
- the copied Review Packet is a bridge from that decision surface to a local
  operator preview and a target project-agent instruction;
- `goal-harness review-packet --goal-id <goal-id>` may generate the same
  packet from the status contract for CLI-facing agents, but it is still a
  read-only packaging command;
- `goal-harness review-packet --goal-id <goal-id> --handoff-only` is the
  copy-minimal form for an already selected or approved target-agent relay: it
  prints only the `project_agent_handoff` text in markdown output, while JSON
  output still keeps the full payload and adds `handoff_text`;
- the local `operator_gate_dry_run` preview belongs to the user or controller,
  not the target project agent;
- the project-agent command is only the after-approval dry-run execution path.

For controller opt-in packets, the operator question must appear before any
local gate preview, and the local gate preview must appear before any
project-agent command. A dashboard, script, or agent must not infer approval,
reward, write-control, or a real map run from the presence of a copied packet,
review URL, selected `goal_id`, or `agent_command`.

The project-agent section of a Review Packet should be short and operational:
name the current context source, the forwarding condition, the execution
boundary, and the stop condition before showing any command. The context source
rule keeps agent handoffs from bloating: the packet carries only the minimal
current instruction; if the target agent needs more context, it reads the
current active state, status, history, and command output instead of rebuilding
truth from old chats or old packets. For controller opt-in, that means the
section is only forwarded after an explicit human/controller agreement, the
agent only runs the read-only or dry-run project path, and it must stop if it
needs a real approval, write-control, run-history append, production action, or
if the command fails. This keeps the packet easy for target agents to follow
while preserving the dashboard as the human decision surface and the archival
evidence trail as the cold path.

`status=read_only_project_map` is emitted when the latest compact run came from
`goal-harness read-only-map`. Dashboard consumers should show it as Codex-ready
work with a map-specific badge or drill-down: the project is connected and has
a read-only map run, but the next useful action still needs a controller or
agent to use that map. Compact run records may include a public-safe
`project_map` object:

```json
{
  "adapter_kind": "read_only_project_map_v0",
  "adapter_status": "connected-read-only",
  "authority_source_count": 1,
  "authority_registry_declared": true,
  "authority_registry_path_exists": true,
  "authority_registry_default_entry_count": 2,
  "authority_registry_default_entries_present": 2,
  "topic_authority_count": 8,
  "authority_registry_conflict_risk": "low",
  "guard_count": 3,
  "sections_found": 4,
  "sections_checked": 7,
  "files_present": 4,
  "files_checked": 9,
  "residual_risk_count": 1
}
```

The full run payload may also include `residual_risks`, a compact public-safe
list such as `planned_adapter_requires_controller_opt_in` or
`project_local_goal_state_not_detected`. If an optional authority registry is
declared, missing registry files, missing default entries, deprecated sources,
or medium/high conflict risk are reported with stable `authority_registry_*`
labels. Project agents should relay that list directly rather than inventing a
free-form risk summary.

The CLI cleanup path is `goal-harness archive-runtime --goal-id <goal-id>`. It
defaults to dry-run and requires `--execute` before moving the runtime directory
under `<runtime-root>/archived-goals/`.

## Run History

`run_history` is a compact, public-safe drill-down surface for the dashboard.
It mirrors the compact run index, but strips local artifact paths. UIs should
show artifact availability with `json_exists` and `markdown_exists` instead of
linking directly to local files.

Goal shape:

```json
{
  "id": "complex-project-main-control",
  "domain": "complex-project-control",
  "status": "active-read-only",
  "lifecycle_phase": "controller_gated",
  "lifecycle_flags": [
    "controller_gated",
    "adapter_inspected"
  ],
  "registry_member": true,
  "legacy_runtime_goal": false,
  "adapter_kind": "complex_project_read_only_map_v0",
  "adapter_status": "connected-read-only",
  "authority_registry": {
    "declared": true,
    "path": "docs/meta/DOC_REGISTRY.yaml",
    "path_exists": true,
    "default_entry_count": 3,
    "default_entries_checked": 3,
    "default_entries_present": 3,
    "topic_authority_count": 8,
    "deprecated_source_count": 0,
    "conflict_risk": "low"
  },
  "quota": {
    "compute": 0.5,
    "window_hours": 24,
    "slot_minutes": 1,
    "allowed_slots": 720,
    "spent_slots": 0,
    "state": "operator_gate",
    "reason": "operator gate blocks gated delivery; safe non-gated steering may continue",
    "blocked_action_scope": "gated_delivery",
    "safe_bypass_allowed": true
  },
  "index_exists": true,
  "raw_index_records": 2,
  "unique_runs": 2,
  "latest_runs": []
}
```

`authority_registry` on the goal comes from the registry and stays visible even
when the latest run is an operator gate or reward overlay rather than a fresh
project map. Dashboard consumers should translate it into one human-facing line
such as "default entries 3/3, topic 8, risk low" before asking for operator
decisions.

`quota` on the goal comes from the registry and defaults to `compute=1.0` when
not declared. In v0.1, status derives only a compact product state from hard
gates and attention ownership: `eligible`, `throttled`, `waiting`,
`operator_gate`, `paused`, or `blocked_health`. It is not a permission signal
and does not replace human reward, operator gates, write approval, or
production-action authorization.

Run shape:

```json
{
  "generated_at": "2026-05-31T21:15:00+00:00",
  "goal_id": "complex-project-main-control",
  "classification": "ready_for_controller_opt_in",
  "lifecycle_phase": "controller_gated",
  "lifecycle_flags": [
    "controller_gated",
    "adapter_inspected"
  ],
  "recommended_action": "ask the target controller to opt into a read-only map before any mutation",
  "health_check": "8/8",
  "controller_readiness": {
    "classification": "ready_for_read_only_not_decision",
    "read_only_observer_ready": true,
    "decision_advisor_ready": false,
    "write_controller_ready": false,
    "missing_gates": [
      "human_reward_capture",
      "aligned_eval_decision_evidence"
    ],
    "review_judgment": "safe to connect read-only observation, but not decision advice",
    "next_handoff_condition": "record aligned eval evidence and one human reward event",
    "gates": [
      {
        "id": "durable_goal_context",
        "ok": true,
        "review": "goal state and run history are available"
      },
      {
        "id": "human_reward_capture",
        "ok": false,
        "review": "no operator reward has been recorded yet"
      }
    ]
  },
  "human_reward": {
    "recorded_at": "2026-06-01T00:05:00+00:00",
    "decision": "continue_route",
    "reward": "positive",
    "reason_summary": "operator accepted the route because the comparable metric improved and validation was aligned",
    "follow_up": "promote the route to a longer-window check"
  },
  "json_exists": true,
  "markdown_exists": true
}
```

Optional compact fields such as `active_task_count`, `active_priorities`, and
`cache_check` may appear when an adapter records them. Experiment-controller
adapters may also include compact `controller_readiness` and `human_reward`
summaries.

`lifecycle_phase` is derived by the status layer so the dashboard can separate
state interaction stages from adapter-specific classifications:

- `connected`: the goal is registered with a connected adapter but has no run.
- `mapped`: the latest run is a generic `read_only_project_map`.
- `refreshed`: the latest run is a state-only `state_refreshed` update.
- `adapter_inspected`: a project adapter produced a compact run.
- `reward_judged`: a human reward overlay is attached to the run.
- `operator_approved`: an operator gate was approved and the approved
  `agent_command` may be handed to the target project agent.
- `operator_gated`: an operator gate was rejected or deferred, so the goal stays
  gated.
- `controller_gated`: controller readiness evidence is present, but the goal is
  still missing a gate such as human reward or comparable evidence.
- `controller_ready`: decision-advisor or write-controller readiness is present.
- `planned`, `registered`, and `run_recorded`: fallback phases for goals that
  are not yet connected or have an unclassified run.

`lifecycle_flags` may contain more than one phase. For example, a run can be
both `adapter_inspected` and `reward_judged`, both `adapter_inspected` and
`operator_approved`, or both `adapter_inspected` and `controller_gated`. UIs
should show the primary phase first and use flags as secondary badges.

For `controller_readiness`, the status export keeps only controller-stage
booleans, missing gate names, operator-facing review text, next handoff
condition, and compact gate rows with `id`, `ok`, and `review`. For
`human_reward`, the status export keeps only `recorded_at`, `decision`,
`reward`, `reason_summary`, and `follow_up`. For `operator_gate`, the status
export keeps only `recorded_at`, `gate`, `decision`, `operator_question`,
`reason_summary`, `follow_up`, and `agent_command`; richer evidence belongs in
private run payloads.

Operator gate decisions answer "may the project agent cross this gate?" and are
separate from reward signals. Use them for approvals such as read-only map
opt-in:

```bash
goal-harness operator-gate \
  --goal-id complex-project-main-control \
  --decision approve \
  --reason-summary "同意先执行 read-only map opt-in"
```

The dry-run form appends nothing. A real append writes an
`operator_gate_approved`, `operator_gate_rejected`, or
`operator_gate_deferred` compact run. Approved gates are surfaced as
Codex-ready with the approved `agent_command`; rejected/deferred gates stay in
the user/controller lane with the recorded reason.

Operators can append `human_reward` with the CLI:

```bash
goal-harness reward \
  --goal-id example-experiment-goal \
  --decision continue_route \
  --reward positive \
  --reason-summary "comparable validation improved and the route is worth extending"
```

The command appends a compact overlay row to the goal's `index.jsonl`. History
loading merges later rows with the same run key, so feedback can be added
without rewriting the original run JSON or Markdown payload.

Both dry-run and append responses include:

```json
{
  "active_state_summary": "dry-run：将记录目标 `example-experiment-goal` ...",
  "project_agent_visibility": {
    "source_of_truth": "run_bound_human_reward_overlay",
    "history_command": "goal-harness history --goal-id example-experiment-goal --limit 3",
    "active_state_role": "summary_only",
    "review_packet_role": "optional_handoff_only"
  }
}
```

Agents should treat `history_command` as the standard visibility path. Active
state can repeat the summary and next action for context, but it is not the
durable reward store.

When `goal-harness status` renders Markdown, a latest run with `human_reward`
should expand the compact reward fields under `Run History` and repeat the same
project-agent history lookup. This keeps the dashboard as the operator surface
while making CLI status sufficient for project agents that only need to notice
and inspect a recorded reward.

The Markdown response should also show a short `Write Effect` section near the
top so the operator can see the selected run, whether the overlay was actually
appended or only previewed, whether active-state writeback would happen, and
the one project-agent history lookup.

The CLI can also preview or perform the active-state summary write when the
operator explicitly asks for it:

```bash
goal-harness reward \
  --goal-id example-experiment-goal \
  --decision continue_route \
  --reward positive \
  --reason-summary "comparable validation improved and the route is worth extending" \
  --write-active-state-summary
```

That response includes `active_state_update`, for example:

```json
{
  "active_state_update": {
    "requested": true,
    "section": "Progress Ledger",
    "would_write": false,
    "written": true,
    "already_present": false
  }
}
```

The loopback dashboard write path is opt-in. By default `serve-status` exposes
only `POST /reward/dry-run`; when started with `--enable-reward-write-api` on a
loopback host, it also exposes `POST /reward/append`. The append request must
reuse the `preview_id` returned by the dry-run response, so a changed payload,
changed selected run, or changed raw index count forces the operator to preview
again. The compact browser response does not expose index paths, state file
paths, or raw private evidence.

## Display Model

A first useful UI can be built from the export alone:

- Header: operator actions and selected-action sharing should be above
  auxiliary source controls, metrics, and raw drill-down, because the
  dashboard is a user decision surface rather than an agent CLI mirror.
- Metrics: `ok`, `goal_count`, `run_count`, and contract summary.
- Compute quota summary: goals eligible for the next agent turn, throttled
  goals, waiting goals, paused goals, and operator-gated goals should be
  visible on the first screen once quota fields are present. Automation cadence
  should be treated as execution detail, not the only priority signal.
- User action summary: first-screen cards should derive from the same selected
  operator decision and reward-default logic, grouping reward gates, controller
  opt-ins, evidence watches, Codex handoffs, and blocking health items before
  raw goal detail. Cards may show the matching safe CLI path label or command
  plus the reward-draft decision/reward hint, but those are affordances over
  the agent-facing status export, not browser-side writes. The dashboard can
  derive local action-kind filters from these cards, such as reward,
  controller, Codex, evidence, and health, without adding new status fields.
  Persisting that focus in a URL search parameter is dashboard UI state; it
  does not change the status contract or durable goal truth.
- Selected goal detail: the dashboard may persist the selected `goal_id` in
  URL search state so a review link can reopen the same run-history detail.
  This selected-goal state is not part of the status export and must not be
  treated as an approval, reward, or controller signal.
- Review link: the dashboard may copy a browser URL that includes local
  `actionKind`, selected `goalId`, source `statusUrl`, `lane`, and `severity`
  search state. That link is a user review affordance over this export; it
  must not add fields to the status contract or mutate goal runtime state.
- Review Packet: the dashboard should expose one canonical copy affordance for
  the selected action card rather than separate link, reply, handoff, and agent
  prompt buttons. The packet may include the review link, Chinese
  agree/disagree/reason/next-step prompt, project-agent instructions, safe local
  path, reward/default hint, and local dry-run preview. For reward actions, the
  project-agent section should point to the run history lookup, not ask the
  target project agent to append or dry-run user reward on the user's behalf.
  For controller opt-in actions, the packet must keep this order: human
  question, user/controller-owned local gate dry-run preview, then
  project-agent dry-run instruction. The dashboard/operator view owns the human
  decision; the project-agent command is only the after-approval dry-run
  execution path.
  It is still browser UI state and must not be parsed as durable reward,
  approval, controller opt-in, or write-control.
- Goal directory: all `run_history.goals`, grouped mentally by `domain` and
  enriched with matching attention items and lifecycle phase badges when a
  goal needs action.
- User review map: counts for connected, mapped, refreshed,
  adapter-inspected, reward-judged, and controller-ready goals, written as
  operator-facing states rather than raw adapter statuses. Goals with
  controller evidence but missing gates should be shown as controller-gated,
  not controller-ready.
- Primary queue: `attention_queue.items`.
- First-screen action cards: when a queue item carries `operator_question`, show
  that question as the primary operator prompt before `recommended_action`.
  `recommended_action` remains context; `agent_command` is displayed as the safe
  target-agent command only after the operator question has been answered.
- Queue gate hints: show `controller_stage`, `missing_gates`, and
  `next_handoff_condition` directly in queue rows so an operator can see why a
  watched goal is not ready yet without opening the full run payload.
- User lane: items with `waiting_on=user_or_controller` or `controller`.
- Codex lane: items with `waiting_on=codex`.
- Watch lane: items with `waiting_on=external_evidence`.
- Health panel: contract `errors`, `warnings`, and `checks`.
- Run detail panel: selected goal from the attention queue, compact
  classifications, authority coverage, controller readiness, health checks,
  reward signals, and artifact availability.
- Reward CLI draft: selected goal plus latest compact run timestamp should be
  enough to generate a local `goal-harness reward --dry-run` command. Draft
  fields should default from the selected operator decision and missing gates,
  while remaining editable before validation. The dashboard should append
  feedback only when the live loopback status server explicitly exposes the
  reward write API.
- Reward dry-run check: when the dashboard is loaded from a loopback status
  server, it may validate the same draft through `POST /reward/dry-run` and
  display the compact result, including the Chinese active-state summary and
  project-agent history command. The response includes `preview_id`.
- Reward append: when the same loopback server is started with
  `--enable-reward-write-api`, the dashboard may send that exact preview to
  `POST /reward/append`. A successful append writes one run-bound
  `human_reward` overlay, refreshes status, and makes the next project-agent
  automation able to see the feedback through `goal-harness status` or
  `goal-harness history`.
- Reward source of truth: durable user reward belongs in a run-bound
  `human_reward` overlay appended through `goal-harness reward`. Active goal
  state can summarize that such a reward was recorded, and the Review Packet can
  be forwarded to another project agent for immediate coordination through the
  returned history lookup, but neither replaces the compact run overlay as the
  multi-agent reward signal.
- Operator decision: selected goal detail should translate `waiting_on`,
  `severity`, `lifecycle_phase`, `missing_gates`, and `recommended_action`
  into a human stance such as review/authorize, let Codex continue, wait for
  evidence, or fix health first. Raw classifications remain drill-down
  details.
- Safe CLI path: selected goal detail should also show the next safe local
  command class for that stance: status/history inspection, read-only-map or
  refresh-state dry-run, or reward dry-run through the Reward CLI Draft. This
  is a dashboard-to-agent bridge; it must not imply browser-side approval,
  reward append, or write-controller execution.

Browser-side reward append is outside the default status server behavior. If a
local server enables it, it must follow the explicit opt-in boundary in
[dashboard-reward-write-boundary.md](dashboard-reward-write-boundary.md).

Suggested badge mapping:

- `severity=high`: blocking.
- `severity=action`: needs a decision or bounded work segment.
- `severity=watch`: no immediate action; wait for evidence.

## Static Dashboard Demo

The repository includes a no-dependency renderer that turns any status JSON
export into a static HTML dashboard:

```bash
goal-harness --format json status > /tmp/goal-status.json
python3 examples/render-status-dashboard.py /tmp/goal-status.json /tmp/goal-status.html
```

The generated page groups queue items into user/controller, Codex-ready, and
external-evidence lanes. It is a small demo for local inspection and UI
prototyping; it is not the product dashboard.

The official dashboard direction is a React/Vite control-plane app that can
render this same JSON contract with typed routes, filters, tables, charts, and
drill-down pages. See
[dashboard-frontend-selection.md](dashboard-frontend-selection.md).

## Adapter Responsibilities

Adapters should write compact run index records that include:

- `generated_at`
- `goal_id`
- `classification`
- `recommended_action`
- `json_path`
- `markdown_path`

Project adapters may add compact public-safe fields such as `health_check`,
`active_task_count`, `active_priorities`, or a compact `human_reward` summary.
Raw logs, prompts, private metrics, workspace paths, and internal document
links belong in private run payloads, not in compact index records.

## Boundary

The JSON export is safe to feed to a local dashboard only if the registry ids,
adapter classifications, and recommended actions are sanitized. Before sharing
an export publicly, verify that it contains no:

- local absolute user paths,
- private document links,
- credentials,
- raw production logs,
- internal task ids,
- private metric values.

The public examples under `examples/` are sanitized and can be used for demos.

## Compatibility Rules

- Additive fields are allowed.
- Existing field meanings should remain stable across minor versions.
- Consumers should ignore unknown fields.
- Consumers should handle missing `attention_queue.items` as an empty queue.
- Consumers should handle missing `run_history` as unavailable.
- Consumers should treat `contract.ok=false` as a stronger signal than an empty
  attention queue.
