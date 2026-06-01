# Goal Harness

Goal Harness is a small control plane for long-running agent goals. It helps a
Codex or Claude-style agent keep durable goal state, inspect recent runs, and
check project boundaries before the next goal-mode tick.

It is not another agent framework. It sits above your existing app, CLI,
heartbeat, or goal-mode workflow and gives it a shared structure:

- a project-local goal state file,
- a project-local registry that says where the goal lives,
- a shared runtime directory for run history,
- a contract check that catches missing state and obvious private-data leaks.

The core design boundary is the state interaction between the durable goal, the
Codex App executor, the human operator, and the dashboard. See
[docs/state-interaction-model.md](docs/state-interaction-model.md) before
adding new controller, reward, or dashboard capabilities.

## Why

Long-running agent work usually fails through drift rather than one bad prompt:
the next action gets lost, stale assumptions survive, project state gets mixed,
or private evidence leaks into public artifacts. Goal Harness makes those
boundaries explicit and repeatable.

Use it when you want an agent to manage:

- a multi-week engineering or research goal,
- several local projects with different adapters,
- local compute quota across projects and agent turns,
- Codex-style controller runs that spawn scoped sub-agents,
- recurring heartbeat runs,
- experiment progress and decision gates,
- public/private boundary checks before publishing.

## Quickstart

Install one shared local checkout:

```bash
git clone https://github.com/huangruiteng/goal-harness ~/goal-harness
~/goal-harness/scripts/install-local.sh
goal-harness doctor
```

The install script creates `~/.local/bin/goal-harness`, adds that directory to
your shell profile when needed, and installs the `goal-harness-project` Codex
skill into `~/.codex/skills`. This keeps the CLI available from any project
folder and teaches future Codex sessions on the same machine how to connect,
refresh, and sync project goals correctly.
If a project shell cannot find or run the command, `goal-harness doctor`
reports the PATH, wrapper, symlink, and Python import state.

Connect a project with one command:

```bash
cd /path/to/your-project
goal-harness bootstrap \
  --goal-id your-project-goal \
  --objective "Improve this project through bounded, verified goal segments." \
  --goal-doc GOAL.md
```

If you already have a project folder and a goal document, use
[docs/new-project-codex-prompt.md](docs/new-project-codex-prompt.md) as the
copy-paste prompt for the Codex session that will connect the project.
You can generate the prompt from the CLI:

```bash
goal-harness new-project-prompt \
  --project /path/to/your-project \
  --goal-doc /path/to/your-project/GOAL.md
```

For a Codex controller goal that may spawn scoped child agents:

```bash
goal-harness bootstrap \
  --goal-id your-controller-goal \
  --spawn-allowed \
  --allowed-domain docs-map \
  --allowed-domain validation-map \
  --write-scope "docs/**"
```

`connect` is an alias for `bootstrap`:

```bash
goal-harness connect --goal-id your-project-goal
```

The command creates or connects:

```text
your-project/
  .goal-harness/registry.json
  .codex/goals/your-project-goal/ACTIVE_GOAL_STATE.md

~/.codex/goal-harness/
  goals/<goal-id>/runs/
```

When `--goal-doc` is provided, Goal Harness records it as a primary authority
source in both the registry and the initial active goal state.

If your goal state contains private evidence, add these paths to the project
`.gitignore`:

```gitignore
.goal-harness/
.codex/goals/
```

## Daily Use

Inspect the project registry:

```bash
goal-harness registry
```

Diagnose local CLI installation:

```bash
goal-harness doctor
```

Run the contract check:

```bash
goal-harness check --scan-root .
```

Read recent run history:

```bash
goal-harness history --goal-id your-project-goal
```

Append a state-only refresh run after updating active state, ledger, or docs
without running a project adapter:

```bash
goal-harness refresh-state --goal-id your-project-goal
```

By default the refresh run uses the first public-safe item from the active
state's `## Next Action` as its compact `recommended_action`, joining wrapped
continuation lines so dashboards can show the actual next move instead of a
truncated refresh notice. Use
`--recommended-action` when the state contains only private or overly detailed
next-action text.

Append a generic read-only project map for a connected project:

```bash
goal-harness read-only-map --goal-id your-project-goal
```

`read-only-map` is the first standard run for projects connected with
`adapter.kind=read_only_project_map_v0` or a compatible `*_read_only_map_v0`
adapter. It reads the registry, active state, and a small file-existence
inventory, then writes a compact `read_only_project_map` run without mutating
the project. The output includes a compact `residual_risks` list so project
agents can report the same risk vocabulary instead of inferring it from raw
inventory rows.

For a high-complexity goal whose adapter is still `planned`, use
`goal-harness read-only-map --goal-id ... --dry-run` as the opt-in preview.
That preview reads the same bounded surfaces and reports `opt_in_required=true`,
but appending a map run still requires the adapter to move to
`read-only-map-ready`, `connected-read-only`, or `connected`.
In multi-project status, planned opt-in goals keep the human decision in the
Goal Harness operator view: `recommended_action` asks for the operator gate,
while `agent_command` carries the dry-run command for the target project agent
after approval.

Record that operator answer before handing the command to a project agent:

```bash
goal-harness operator-gate \
  --goal-id your-project-goal \
  --decision approve \
  --reason-summary "operator approved read-only map opt-in" \
  --dry-run
```

Remove `--dry-run` only when the operator intentionally wants the approval,
rejection, or deferral appended as a compact `operator_gate_*` run.

`connect` and `refresh-state` automatically merge the project registry into the
shared local global registry at `~/.codex/goal-harness/registry.global.json`.
If a command is run outside any project registry, Goal Harness falls back to
that global registry so dashboards and controller ticks can see all synced
projects.

Manually resync a project registry when needed:

```bash
goal-harness sync-global
```

Preview cleanup for an obsolete runtime-only goal:

```bash
goal-harness archive-runtime --goal-id old-experiment-goal
goal-harness archive-runtime --goal-id old-experiment-goal --execute
```

Append compact operator feedback to the latest run:

```bash
goal-harness reward \
  --goal-id your-project-goal \
  --decision continue_route \
  --reward positive \
  --reason-summary "validation improved and the route is worth extending"
```

Use `--dry-run` first when turning a dashboard review into durable feedback.
The command returns a Chinese `active_state_summary` and a
`project_agent_visibility.history_command` so Codex can update active state as a
summary while project agents read the run-bound reward from history.
After the operator explicitly approves the write, add
`--write-active-state-summary` to also append that summary to the goal state's
`Progress Ledger`. With `--dry-run`, the same flag previews the state write but
does not mutate the run index or active state.

See the first-screen status and attention queue:

```bash
goal-harness status
```

For agent-facing compute allocation, read the quota grouping that is derived
from the same status contract:

```bash
goal-harness quota status
goal-harness quota plan
goal-harness quota should-run --goal-id <goal-id>
```

`quota status` shows every registered goal by quota state. `quota plan` keeps
the same read-only inputs but emphasizes the non-empty groups and the next
automatic turn. `quota should-run` is the per-goal automation guard: it returns
`should_run=true` only when the goal is eligible for the next automatic turn,
otherwise it returns `should_run=false` with the gate, evidence, health, or
quota reason. These commands do not mutate registry, run history, rewards, or
gates.

`status` and `serve-status` default their public/private contract scan to the
Goal Harness install root, not the shell's current project directory. Pass
`--scan-root` or `--scan-path` only when you intentionally want to scan a
specific public-safe project surface.

Use JSON output from scripts, heartbeats, or pre-tick adapters:

```bash
goal-harness --format json check --scan-root .
```

Render a static local dashboard from status JSON:

```bash
goal-harness --format json status > /tmp/goal-status.json
python3 ~/goal-harness/examples/render-status-dashboard.py /tmp/goal-status.json /tmp/goal-status.html
```

The Python renderer is a diagnostic fallback. The planned product dashboard is
a React/Vite app with typed routes, tables, charts, and a more polished
control-plane UI. See
[docs/dashboard-frontend-selection.md](docs/dashboard-frontend-selection.md).
The dashboard should follow the actor and state-store model in
[docs/state-interaction-model.md](docs/state-interaction-model.md): read the
derived agent-facing status surface by default, translate it into a
human-facing operator view, show user/controller and Codex-ready lanes
separately, and keep browser-side writes behind an explicit local write
boundary.

Run the dashboard shell locally:

```bash
cd ~/goal-harness/apps/dashboard
npm install
npm run build
npm run dev
```

Serve live status JSON for the current registry/global-registry view, then use
the dashboard `Live` source button:

```bash
goal-harness serve-status --port 8765
```

The endpoint is local by default:

```text
http://127.0.0.1:8765/status.json
```

The dashboard renders the attention queue with a compact run-history drill-down
for recent classifications, controller readiness, validation health, human
reward signals, and artifact availability. Raw CLI classifications remain
secondary details; the first screen should answer what the user needs to judge,
what an agent can do, and what is waiting on evidence.

For a fully static fallback, export current local state into the dashboard
public folder and load `/status.local.json` from the dashboard source control:

```bash
goal-harness --format json status > apps/dashboard/public/status.local.json
```

For a project with many unrelated files, scan only the public files you intend
to publish:

```bash
goal-harness check \
  --scan-path README.md \
  --scan-path docs/goal-harness-contract.md \
  --scan-path scripts/project-pre-tick.py
```

## Mental Model

```text
project goal state
  + project registry
  + optional project adapter
        |
        v
shared runtime root
        |
        v
goal-harness registry / history / check
        |
        v
Codex goal mode / heartbeat / future UI
```

The public package should contain generic control-plane logic. Project-specific
adapters can read local evidence such as tests, experiment boards, TODO files,
or production-safe status summaries.

For Codex-style parallel work, the same model extends to controller/sub-agent
runs: the controller owns the goal, merge decision, and final writeback; each
sub-agent owns a scoped probe, implementation slice, or validation surface. See
[docs/codex-subagent-orchestration.md](docs/codex-subagent-orchestration.md).

For large repos with many docs, TODOs, run reports, branches, and validation
surfaces, start with a read-only adapter map before allowing edits. See
[docs/complex-project-readonly-adapter.md](docs/complex-project-readonly-adapter.md).
For the reusable patterns behind complex-project maps, experiment boards,
authority registries, and gated handoff packets, see
[docs/field-derived-patterns.md](docs/field-derived-patterns.md).

For long-running experiment controllers, connect the target only when Goal
Harness can improve on bare Codex goal mode through durable experiment context,
explicit gates, human reward capture, and cross-project queueing. See
[docs/experiment-controller-milestone.md](docs/experiment-controller-milestone.md).

For multi-project control, `goal-harness status` derives a sanitized attention
queue from registry, run history, and contract health. It answers which goals
need user/controller action, which are ready for Codex work, and which are only
watching external evidence. If a runtime-only goal becomes actionable, status
surfaces it as `unregistered_runtime_goal`; register it if active, or use
`goal-harness archive-runtime` to move obsolete run history out of the active
runtime list. See
[docs/attention-queue.md](docs/attention-queue.md). For dashboards and scripts
that consume `goal-harness --format json status`, see the
[status data contract](docs/status-data-contract.md). For the official
dashboard frontend direction, see
[docs/dashboard-frontend-selection.md](docs/dashboard-frontend-selection.md).
Goal Harness should also own simple compute quota across projects, rather than
making automation cadence the only way to express priority. See
[docs/quota-allocation.md](docs/quota-allocation.md).
For background exploration, memory consolidation, and refactor-warning work
that should not interrupt active project agents, see
[docs/dreaming-exploration-lane.md](docs/dreaming-exploration-lane.md).
Browser-side reward writes are intentionally not part of the default dashboard;
the opt-in safety boundary is described in
[docs/dashboard-reward-write-boundary.md](docs/dashboard-reward-write-boundary.md).

## Public / Private Boundary

Safe to publish:

- registry schema,
- runtime layout,
- adapter lifecycle,
- generic validation commands,
- sanitized examples.

Keep private:

- real local paths,
- task ids,
- production logs,
- internal document links,
- credentials,
- user-specific active goal state,
- raw experiment metrics.

See [docs/public-private-boundary.md](docs/public-private-boundary.md).

## Current Status

Goal Harness is early. The first milestone is not a full agent platform; it is
a useful shared substrate for local goal state, run history, and contract
checks across multiple projects. The next milestones are stronger project
adapters, safer controller/sub-agent coordination, and a small UI for
multi-project goal status.
