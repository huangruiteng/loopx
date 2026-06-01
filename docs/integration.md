# Integration Guide

Goal Harness should be used as a shared local base, not copied into every
project.

## Local Base

Clone or symlink one copy:

```bash
git clone <repo-url> ~/goal-harness
python3 -m pip install -e ~/goal-harness
```

Then projects can call:

```bash
goal-harness --registry <private-registry> registry
goal-harness --registry <private-registry> history
goal-harness --registry <private-registry> status
goal-harness --registry <private-registry> check --scan-root <project-root>
```

## One-Command Project Connect

For a new project, start with:

```bash
cd /path/to/project
goal-harness bootstrap \
  --goal-id project-goal \
  --objective "Improve this project through bounded, verified goal segments."
```

`goal-harness connect` is an alias for the same operation. The command is
safe to rerun: by default it keeps an existing state file and existing registry
entry; pass `--force` only when you intentionally want to replace them.

The default files are:

```text
.goal-harness/registry.json
.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md
```

If another Codex session should perform the connection from a project folder
and a goal document, use [new-project-codex-prompt.md](new-project-codex-prompt.md)
as the handoff prompt.

In most real projects these files should be private. If they contain current
work state or local evidence, add them to `.gitignore`:

```gitignore
.goal-harness/
.codex/goals/
```

## Project Adapter

A project adapter should be thin and project-specific. It may read:

- active goal state,
- git status,
- test or experiment status,
- cheap health checks,
- project-specific guards.

It should output:

- `classification`,
- exactly one `recommended_action`,
- relevant warnings,
- hard guards,
- optional run log paths.

By default it should be read-only. Launching jobs, stopping jobs, syncing docs,
or editing production state requires explicit user approval.

The bootstrap command does not create a domain adapter. It creates the minimum
registry and state contract so the first adapter can be added deliberately.

For a large project, prefer a read-only adapter map before any writes. The map
should identify authority sources, work clusters, validation surfaces, proposed
sub-agent scopes, boundary findings, and a short controller handoff packet. See
[complex-project-readonly-adapter.md](complex-project-readonly-adapter.md).

## Controller / Sub-Agent Coordination

Some Codex goal runs should use multiple sub-agents. Goal Harness should keep
that parallelism explicit:

- child runs declare `work_scope` before acting;
- overlapping write scopes require parent arbitration;
- children default to read-only unless the registry grants a write scope;
- only the controller can mark the main goal complete;
- child final reports include changed files, validation, residual risk, and
  next handoff;
- the controller performs final merge, public/private scan, and state writeback.

Minimal registry fields for this pattern are:

```json
{
  "role": "controller",
  "parent_goal_id": null,
  "spawn_policy": {
    "allowed": true,
    "max_children": 3,
    "allowed_domains": ["docs-map", "validation-map"]
  },
  "coordination": {
    "write_scope": ["docs/**", "examples/**"],
    "claim_ttl_minutes": 30,
    "requires_parent_approval": ["write", "publish", "production-action"]
  }
}
```

These fields are a public contract, not a runtime lock manager. A future version
can add claim files, stale-claim detection, and overlap warnings.

## Shared Runtime

All adapters should save compact run history under:

```text
~/.codex/goal-harness/goals/<goal-id>/runs/index.jsonl
```

This gives the app, CLI, heartbeats, and future UI one place to inspect goal
history.

## Human Reward Overlays

When an operator judges a run, append a compact reward overlay instead of
editing the run JSON by hand:

```bash
goal-harness reward \
  --goal-id project-goal \
  --decision continue_route \
  --reward positive \
  --reason-summary "comparable validation improved and the route is worth extending" \
  --follow-up "promote to the next longer-window check"
```

By default the command attaches feedback to the latest compact run for the
goal. Pass `--run-generated-at <timestamp>` to target an older run. The writer
appends a JSONL overlay to the same `index.jsonl`; it does not mutate private
run payloads. `goal-harness status` exports only the compact `human_reward`
fields, so raw evidence should stay in private artifacts.

## First-Screen Status

Use `goal-harness status` as the entrypoint for the next controller tick or UI
refresh:

```bash
goal-harness status --scan-path README.md --scan-path docs/
goal-harness --format json status
```

For the React dashboard, serve that same status contract over loopback HTTP:

```bash
goal-harness serve-status --port 8765
```

Then load `http://127.0.0.1:8765/status.json` from the dashboard source
control. The command binds to `127.0.0.1` by default and is meant for local
operator dashboards, not public hosting.

The same loopback server exposes `POST /reward/dry-run` so the dashboard can
validate a selected goal/run reward draft before any write path exists. The
dry-run response is compact and does not append to `index.jsonl`; recording a
real reward still uses the `goal-harness reward` CLI command.

A browser append endpoint would be a separate explicit opt-in capability. Do
not infer write permission from running the dashboard or status server; follow
[dashboard-reward-write-boundary.md](dashboard-reward-write-boundary.md) before
adding any browser-side reward writer.

The status command combines contract health and run history into an attention
queue. Each queue item says which goal needs attention, who it is waiting on,
how severe the item is, and exactly one recommended action.

For dashboards, heartbeat summaries, or any script that reads JSON output, use
the [status data contract](status-data-contract.md).

Keep adapter output sanitized before it enters the compact index. The status
queue is meant for control-plane display, not for raw private evidence.

## Public Repo vs Project Repo

Put generic code here:

- registry and history readers,
- contract checker,
- generic schema and docs,
- sanitized adapter examples,
- controller/sub-agent lifecycle examples.

Keep in the project repo:

- project-specific adapter code,
- active goal state,
- private registry,
- domain-specific health checks.

This split lets many local projects share one stable Goal Harness base while
keeping their real evidence and safety policies local.
