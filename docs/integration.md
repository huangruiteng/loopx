# Integration Guide

Goal Harness should be used as a shared local base, not copied into every
project.

## Local Base

Clone or symlink one copy:

```bash
git clone <repo-url> ~/goal-harness
~/goal-harness/scripts/install-local.sh
goal-harness doctor
```

The installer links the repository wrapper into `~/.local/bin/goal-harness`,
adds that bin directory to the current shell profile when it is missing from
`PATH`, and installs the `goal-harness-project` Codex skill into
`~/.codex/skills` so future project agents use the same connection workflow.
Use `goal-harness doctor` from any project folder to inspect the resolved
command path, symlink target, wrapper script, and Python import health.

Then projects can call:

```bash
goal-harness --registry <private-registry> registry
goal-harness --registry <private-registry> history
goal-harness --registry <private-registry> status
goal-harness --registry <private-registry> check --scan-root <project-root>
goal-harness doctor
```

## One-Command Project Connect

For a new project, start with:

```bash
cd /path/to/project
goal-harness bootstrap \
  --goal-id project-goal \
  --objective "Improve this project through bounded, verified goal segments." \
  --goal-doc GOAL.md
```

`goal-harness connect` is an alias for the same operation. The command is
safe to rerun: by default it keeps an existing state file and existing registry
entry; pass `--force` only when you intentionally want to replace them.

The default files are:

```text
.goal-harness/registry.json
.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md
```

## Multiple Goals In One Repository

One repository may hold a main lane, a side bypass, and other independent goals
at the same time. Connect each lane with a distinct stable `goal_id`:

```bash
cd /path/to/project
goal-harness connect \
  --goal-id main-control \
  --objective "Run the main project control lane." \
  --adapter-kind read_only_project_map_v0 \
  --adapter-status connected-read-only

goal-harness connect \
  --goal-id side-bypass \
  --objective "Run the low-conflict side bypass lane." \
  --adapter-kind read_only_project_map_v0 \
  --adapter-status connected-read-only
```

Both entries live in the same `.goal-harness/registry.json`, but each goal must
own its own active state under `.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`.
Sharing the same `state_file` across two goal ids is treated as a registry
health error because it lets one lane overwrite or summarize the other's state.

Use `--goal-id` on every status-changing command:

```bash
goal-harness read-only-map --goal-id main-control
goal-harness read-only-map --goal-id side-bypass --dry-run
goal-harness quota should-run --goal-id side-bypass
```

`read-only-map` is goal-aware for same-repo setups. In addition to the generic
project inventory, it reports whether the selected goal has a local project
registry, a `.codex/goals/<goal-id>/` state directory, and the declared active
state file. A missing side-lane state directory produces
`project_goal_state_dir_not_detected:<goal-id>` plus the legacy
`project_local_goal_state_not_detected` risk, while a healthy main lane in the
same repo does not mask that problem.

If `--goal-doc` is provided, the document path is recorded as a primary
authority source. The receiving Codex should inspect that document first before
choosing a next action.

If another Codex session should perform the connection from a project folder
and a goal document, use [new-project-codex-prompt.md](new-project-codex-prompt.md)
as the handoff prompt.

You can generate that handoff prompt:

```bash
goal-harness new-project-prompt \
  --project /path/to/project \
  --goal-doc /path/to/project/GOAL.md
```

If the connected project should later run through a recurring Codex App
heartbeat, generate the heartbeat task body instead of hand-copying the quota
guard and spend protocol:

```bash
goal-harness heartbeat-prompt \
  --goal-id project-goal \
  --active-state /path/to/project/.codex/goals/project-goal/ACTIVE_GOAL_STATE.md
```

For live Codex App automations, use the compact form after reviewing the full
contract:

```bash
goal-harness heartbeat-prompt --compact \
  --goal-id project-goal \
  --active-state /path/to/project/.codex/goals/project-goal/ACTIVE_GOAL_STATE.md
```

Copy the generated task body into the heartbeat automation. The timer only
wakes Codex; the task body asks Goal Harness whether the goal should spend
delivery compute on that tick. The compact body is preferred for recurring
heartbeats because it preserves the same quota, gate, blocker-push,
recommendation, steering-audit, writeback, refresh, and spend lifecycle without
copying the full audit prompt into every run context.

The Codex App visible goal text can stay short, such as
`按 ACTIVE_GOAL_STATE.md，基于 Goal Harness 体系，推进项目`. It is only a label for
the human and the executor. The recurring automation prompt should use the
generated heartbeat body above, so every project shares the same quota, gate,
steering-audit, writeback, refresh, and spend lifecycle.
Project-specific behavior should live in the registry, active-state sections,
adapter output, or narrow boundary rules. Do not hand-edit one-off automation
prompt branches for a single project; when a lifecycle rule is broadly useful,
add it to `goal-harness heartbeat-prompt` and its smoke contract.
The quota guard's `heartbeat_recommendation` covers the common onboarding
cases: `run_first_read_only_map` for a newly connected read-only goal, and
`mapped_noop_if_unchanged` for an already mapped goal with no new instruction,
owner evidence, agent todo, stale source, or safe handoff.
That lifecycle treats routine public commit, push, and PR creation as
autonomous after validation and a clean public/private boundary scan; private or
company-internal material, credentials, destructive git, production actions, and
repo rules that explicitly require review still stop on a gate.

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

Project-local registries should also sync into the shared global registry:

```text
~/.codex/goal-harness/registry.global.json
```

`goal-harness connect` and `goal-harness refresh-state` do this automatically.
The global registry is local-private because it contains project paths, but it
strips raw authority-source details and keeps only enough information for
multi-project status. If a command is run outside any project registry, Goal
Harness falls back to the global registry when it exists.

Use the explicit sync command only for diagnosis or recovery:

```bash
goal-harness sync-global
```

If a controller updates `ACTIVE_GOAL_STATE.md`, a progress ledger, or an
external planning section without running a project adapter, append a
state-only refresh run so status and dashboards do not keep showing the older
adapter run:

```bash
goal-harness refresh-state --goal-id project-goal
```

The command reads the registered state file, writes a private JSON/Markdown
refresh payload under the shared runtime root, and appends a compact
`state_refreshed` index record. The compact index should contain only
public-safe classification, action, health-check, and artifact pointers; raw
evidence belongs in the project-local state file or private runtime payload.
When `--recommended-action` is omitted, the command derives the compact action
from the first public-safe item in the active state's `## Next Action`, joining
wrapped continuation lines and falling back to a generic refresh action if that
item contains private-looking content.

For a newly connected read-only project, append a generic map run before
building a custom adapter:

```bash
goal-harness read-only-map --goal-id project-goal
```

The command accepts goals whose adapter kind is `read_only_project_map_v0` or a
compatible `*_read_only_map_v0` variant, and whose adapter status is connected
for read-only work. It inspects only registry metadata, the active state
sections, and a bounded file-existence inventory. The compact run index records
`classification=read_only_project_map`, public-safe `recommended_action`,
artifact availability, map counts, and compact `residual_risks`; raw project
evidence stays in the local private runtime payload.

For planned high-complexity adapters, `read-only-map --dry-run` is allowed as
the opt-in preview path. It returns `opt_in_required=true` and appends nothing,
so a controller can inspect the bounded map shape before moving the adapter to
`read-only-map-ready`, `connected-read-only`, or `connected`. Running the same
command without `--dry-run` still fails until that opt-in status change happens.

Record the operator's answer as a durable gate decision before treating the
handoff as approved:

```bash
goal-harness operator-gate \
  --goal-id project-goal \
  --decision approve \
  --reason-summary "同意先执行 read-only map opt-in" \
  --dry-run
```

The dry-run writes nothing. A real append creates an `operator_gate_approved`,
`operator_gate_rejected`, or `operator_gate_deferred` compact run with JSON and
Markdown artifacts. Approval makes the goal Codex-ready and exposes the
approved `agent_command`; reject/defer keeps the goal gated with the recorded
reason. This records operator gate decisions separately from `human_reward`,
which remains reserved for judging an exact run or route outcome.

After approval, use the minimal handoff form when the only remaining action is
to relay the target project-agent instruction:

```bash
goal-harness review-packet --goal-id project-goal --handoff-only
```

This is still read-only packaging. It strips the human decision wrapper from
markdown output so the receiving agent sees only the goal guard, forwarding
condition, execution boundary, stop condition, and command. It does not append a
gate decision, refresh state, spend quota, grant write-control, or authorize
production action.

If a runtime directory belongs to an old goal that is no longer in the registry,
preview archive cleanup before changing anything:

```bash
goal-harness archive-runtime --goal-id old-experiment-goal
```

The command defaults to dry-run. After review, pass `--execute` to move the
directory into `<runtime-root>/archived-goals/`. Goals still present in the
registry are protected by default; archiving one requires the explicit
`--allow-registered` flag.

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

`goal-harness reward --dry-run` and the real append response both include two
coordination fields:

- `active_state_summary`: a short Chinese summary Codex can copy into the
  active goal state after the operator judgment is recorded.
- `project_agent_visibility`: the standard way another project agent should
  find the reward, including the `goal-harness history --goal-id ... --limit 3`
  command.

The run-bound `human_reward` overlay remains the source of truth. Active state
is only the human-readable pointer and next-action summary; a dashboard Review
Packet is only an immediate handoff artifact.

The Markdown output includes a `Write Effect` section that summarizes the
selected run, run-overlay write or preview state, active-state writeback state,
and the project-agent history lookup before the detailed reward fields.

When the operator has explicitly approved recording the reward, Codex can close
the durable loop in one CLI call:

```bash
goal-harness reward \
  --goal-id project-goal \
  --decision continue_route \
  --reward positive \
  --reason-summary "comparable validation improved and the route is worth extending" \
  --follow-up "promote to the next longer-window check" \
  --write-active-state-summary
```

The state write is opt-in. With `--dry-run --write-active-state-summary`, the
command reports `active_state_update.would_write=true` but does not append the
reward overlay or edit the active state. Without `--write-active-state-summary`,
the command records only the run-bound reward overlay.

## First-Screen Status

Use `goal-harness status` as the entrypoint for the next controller tick or UI
refresh:

```bash
goal-harness --format json status
goal-harness status --scan-path README.md --scan-path docs/
```

The default contract scan uses the Goal Harness install root, so running status
from a private project directory does not accidentally scan local `.local`
state. Pass `--scan-root` or `--scan-path` for a project only when that path is
intended to be public-safe.

For the React dashboard, serve that same status contract over loopback HTTP:

```bash
goal-harness serve-status --port 8765
```

Then load `http://127.0.0.1:8765/status.json` from the dashboard source
control. The command binds to `127.0.0.1` by default and is meant for local
operator dashboards, not public hosting.

The same loopback server exposes `POST /reward/dry-run` so the dashboard can
validate a selected goal/run reward draft. The dry-run response is compact and
does not append to `index.jsonl`; it returns a `preview_id` for the exact
goal/run/reward payload and current raw index count.

Direct dashboard reward submission is an explicit opt-in capability. Start the
status server with `--enable-reward-write-api` to expose `POST /reward/append`
on loopback only. The dashboard can then submit the dry-run `preview_id`; a
successful append writes one run-bound `human_reward` overlay and refreshes
status, so future project agents can discover the feedback through
`goal-harness status` or `goal-harness history`.

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
