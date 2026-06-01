# Status Data Contract

`goal-harness --format json status` is the stable first-screen data contract for
agents, heartbeat jobs, dashboards, and local UI experiments.

The command is an export: it reads the registry, compact run indexes, and the
public/private contract check, then emits one JSON object. It does not inspect
private run payloads beyond compact index fields and does not mutate files.

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
result with `appended=false`. It does not mutate the run index and does not
return private artifact paths.

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
  "waiting_on": "user_or_controller",
  "severity": "action",
  "recommended_action": "ask the target controller to opt into a read-only map before any mutation",
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
- `waiting_on`: `user_or_controller`, `controller`, `codex`, or
  `external_evidence`.
- `severity`: `high`, `action`, or `watch`.
- `recommended_action`: exactly one next action.
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
  "registry_member": true,
  "legacy_runtime_goal": false,
  "adapter_kind": "complex_project_read_only_map_v0",
  "adapter_status": "connected-read-only",
  "index_exists": true,
  "raw_index_records": 2,
  "unique_runs": 2,
  "latest_runs": []
}
```

Run shape:

```json
{
  "generated_at": "2026-05-31T21:15:00+00:00",
  "goal_id": "complex-project-main-control",
  "classification": "ready_for_controller_opt_in",
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

For `controller_readiness`, the status export keeps only controller-stage
booleans, missing gate names, operator-facing review text, next handoff
condition, and compact gate rows with `id`, `ok`, and `review`. For
`human_reward`, the status export keeps only `recorded_at`, `decision`,
`reward`, `reason_summary`, and `follow_up`; richer evidence belongs in private
run payloads.

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

## Display Model

A first useful UI can be built from the export alone:

- Header: `ok`, `goal_count`, `run_count`, and contract summary.
- Goal directory: all `run_history.goals`, grouped mentally by `domain` and
  enriched with matching attention items when a goal needs action.
- Primary queue: `attention_queue.items`.
- Queue gate hints: show `controller_stage`, `missing_gates`, and
  `next_handoff_condition` directly in queue rows so an operator can see why a
  watched goal is not ready yet without opening the full run payload.
- User lane: items with `waiting_on=user_or_controller` or `controller`.
- Codex lane: items with `waiting_on=codex`.
- Watch lane: items with `waiting_on=external_evidence`.
- Health panel: contract `errors`, `warnings`, and `checks`.
- Run detail panel: selected goal from the attention queue, compact
  classifications, controller readiness, health checks, reward signals, and
  artifact availability.
- Reward CLI draft: selected goal plus latest compact run timestamp should be
  enough to generate a local `goal-harness reward --dry-run` command. The
  dashboard should not append feedback directly until the local-only evidence
  boundary is explicitly implemented.
- Reward dry-run check: when the dashboard is loaded from a loopback status
  server, it may validate the same draft through `POST /reward/dry-run` and
  display the compact result. This is still a validation path, not a browser
  write path.

Browser-side reward append is intentionally outside the default status server.
If a future local server enables it, it must follow the explicit opt-in boundary
in [dashboard-reward-write-boundary.md](dashboard-reward-write-boundary.md).

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
