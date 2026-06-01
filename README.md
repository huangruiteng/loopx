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

## Why

Long-running agent work usually fails through drift rather than one bad prompt:
the next action gets lost, stale assumptions survive, project state gets mixed,
or private evidence leaks into public artifacts. Goal Harness makes those
boundaries explicit and repeatable.

Use it when you want an agent to manage:

- a multi-week engineering or research goal,
- several local projects with different adapters,
- Codex-style controller runs that spawn scoped sub-agents,
- recurring heartbeat runs,
- experiment progress and decision gates,
- public/private boundary checks before publishing.

## Quickstart

Install one shared local checkout:

```bash
git clone https://github.com/huangruiteng/goal-harness ~/goal-harness
python3 -m pip install -e ~/goal-harness
```

Connect a project with one command:

```bash
cd /path/to/your-project
goal-harness bootstrap \
  --goal-id your-project-goal \
  --objective "Improve this project through bounded, verified goal segments."
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

Run the contract check:

```bash
goal-harness check --scan-root .
```

Read recent run history:

```bash
goal-harness history --goal-id your-project-goal
```

Append compact operator feedback to the latest run:

```bash
goal-harness reward \
  --goal-id your-project-goal \
  --decision continue_route \
  --reward positive \
  --reason-summary "validation improved and the route is worth extending"
```

See the first-screen status and attention queue:

```bash
goal-harness status
```

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

Run the dashboard shell locally:

```bash
cd ~/goal-harness/apps/dashboard
npm install
npm run build
npm run dev
```

Serve live status JSON from the project you want to inspect, then use the
dashboard `Live` source button:

```bash
goal-harness serve-status --port 8765
```

The endpoint is local by default:

```text
http://127.0.0.1:8765/status.json
```

The dashboard renders the attention queue with a compact run-history drill-down
for recent classifications, controller readiness, validation health, human
reward signals, and artifact availability.

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

For long-running experiment controllers, connect the target only when Goal
Harness can improve on bare Codex goal mode through durable experiment context,
explicit gates, human reward capture, and cross-project queueing. See
[docs/experiment-controller-milestone.md](docs/experiment-controller-milestone.md).

For multi-project control, `goal-harness status` derives a sanitized attention
queue from registry, run history, and contract health. It answers which goals
need user/controller action, which are ready for Codex work, and which are only
watching external evidence. See
[docs/attention-queue.md](docs/attention-queue.md). For dashboards and scripts
that consume `goal-harness --format json status`, see the
[status data contract](docs/status-data-contract.md). For the official
dashboard frontend direction, see
[docs/dashboard-frontend-selection.md](docs/dashboard-frontend-selection.md).
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
