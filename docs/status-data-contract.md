# Status Data Contract

`goal-harness --format json status` is the stable first-screen data contract for
agents, heartbeat jobs, dashboards, and local UI experiments.

The command is an export: it reads the registry, compact run indexes, and the
public/private contract check, then emits one JSON object. It does not inspect
private run payloads beyond compact index fields and does not mutate files.

## Command

```bash
goal-harness --format json status > goal-status.json
```

Use narrow scan paths when a project contains unrelated private files:

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
    "warnings": []
  },
  "attention_queue": {
    "available": true,
    "item_count": 2,
    "needs_user_or_controller": 1,
    "needs_controller": 0,
    "needs_codex": 1,
    "watching_external_evidence": 0,
    "items": []
  }
}
```

Consumers should treat unknown fields as additive. Required fields for a
first-screen UI are `ok`, `contract`, and `attention_queue`.

## Contract Health

`contract.ok=false` means the UI should show a blocking health state before
encouraging more adapter work.

The summary counters are intentionally small:

- `errors`: boundary or registry problems that should block progress.
- `warnings`: non-blocking issues worth showing in a secondary health panel.
- `checks`: successful observations, useful for audit trails.

`errors` and `warnings` are short strings. They must be public-safe before a
project exposes this export outside the local machine.

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
  "source": "latest_run"
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

## Display Model

A first useful UI can be built from the export alone:

- Header: `ok`, `goal_count`, `run_count`, and contract summary.
- Primary queue: `attention_queue.items`.
- User lane: items with `waiting_on=user_or_controller` or `controller`.
- Codex lane: items with `waiting_on=codex`.
- Watch lane: items with `waiting_on=external_evidence`.
- Health panel: contract `errors`, `warnings`, and recent check count.

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
`active_task_count`, or `active_priorities`. Raw logs, prompts, private metrics,
workspace paths, and internal document links belong in private run payloads, not
in compact index records.

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
- Consumers should treat `contract.ok=false` as a stronger signal than an empty
  attention queue.
