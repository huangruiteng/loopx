---
name: goal-harness-project
description: Use when connecting a repository or project goal document to Goal Harness, maintaining project-local goal state, refreshing stale dashboard status, syncing local projects into the shared global registry, or diagnosing Goal Harness CLI/PATH/status/history issues across multiple repos.
---

# Goal Harness Project Workflow

Use this skill when the task mentions Goal Harness, goal-harness, a project goal
document, multi-project dashboard/status, stale latest run,
`.goal-harness/registry.json`, `.codex/goals`, `refresh-state`,
`sync-global`, or connecting a new repo.

Goal Harness has two layers:

- **Project-local state**: each repo owns `.goal-harness/registry.json` and
  `.codex/goals/<goal-id>/ACTIVE_GOAL_STATE.md`.
- **Shared local control plane**: `~/.codex/goal-harness` stores run history and
  `registry.global.json` for multi-project status.

Do not manually copy one project's registry entry into another project. Local
`connect` and `refresh-state` should sync into the shared global registry
automatically.

## Preflight

From the target project shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
goal-harness doctor
```

If `goal-harness` is not on PATH:

```bash
install_script="$HOME/goal-harness/scripts/install-local.sh"
if [ -x "$install_script" ]; then
  "$install_script"
  export PATH="$HOME/.local/bin:$PATH"
fi
goal-harness doctor
```

If this still fails, report the exact missing piece and do not fake a successful
connection.

## Before Spending Automatic Compute

Before a heartbeat, scheduled tick, long-running adapter, or autonomous project
agent spends another delivery turn, ask Goal Harness whether this goal is
eligible:

```bash
goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" quota should-run --goal-id <STABLE_GOAL_ID>
```

If the response has `state=operator_gate`, treat it as a user/controller
interaction, not a silent skip. Read `gate_prompt`, `operator_question`,
`recommended_action`, `next_handoff_condition`, `missing_gates`, and
`user_todo_summary` and `agent_todo_summary` when present, then ask the concrete gate in Chinese unless
the same unresolved question was already surfaced in the recent visible thread.
If `user_todo_summary.open_count > 0`, list those existing open user todos in
the notification even when there are no newly discovered user actions; do not
summarize the turn as "no new user action". Do not run `agent_command`,
adapter work, write-control, production actions, or the gated path while asking.

If the response has `should_run=false` and not `safe_bypass_allowed=true`, do
not run implementation or adapter work for that goal in this turn. Quietly
report or record the public-safe `reason` only when there is no operator gate to
ask. If the command exits non-zero, fail closed: run `goal-harness doctor` /
`goal-harness status` and fix status collection before spending compute.

If the response has `state=operator_gate` and `safe_bypass_allowed=true`, the
gate blocks only the gated delivery path. After the gate has already been
surfaced, you may still read the active state and do one bounded safe-bypass
step from the Priority Stack, such as read-only steering analysis,
documentation, or another P0/P1 item that does not depend on that gate. If that
safe-bypass step actually spends automatic compute, validate it, write back
progress/critic/next action, optionally refresh state, and append one quota
spend event. If `user_todo_summary.open_count > 0`, the safe-bypass report must
include those existing open user todos and must not say there is "no new user
action". If `agent_todo_summary.open_count > 0`, use it as the project agent's
safe follow-up checklist instead of mining chat history or an overlong Next
Action.

This guard is only a compute-allocation check. It does not grant write
permission, bypass operator gates, or replace run-bound human reward. Operator
gates block the gated delivery path, not unrelated safe steering work.
Use the shared global registry for this guard so the project agent reads the
same operator gates, user todos, agent todos, and quota state as the dashboard. This does
not mean all project work is global: `todo add`, `refresh-state`, adapter runs,
and project-file reads still use the project-local state/registry and then sync
the public-safe projection back into the global control plane. If two projects
share a `goal_id`, treat that as a registry health bug and fix the id/source
mapping.

If `should_run=true`, do not simply continue the nearest previous TODO. Read the
active state's Priority Stack, recent progress, and critic, then run a short
steering audit before choosing work: list at least three plausible next-action
candidates across different P0/P1/P2 lanes when useful; if the same topic has
consumed several recent delivery slices, apply a continuation check and state
why continuing still wins; keep compute quota separate from focus quota; record
any losing high-value candidate that should not be forgotten. Then choose
exactly one bounded, verifiable step from that audit.

## Set Up Recurring Heartbeats

When a user or controller wants a recurring Codex App heartbeat for a connected
goal, prefer the generator instead of hand-copying the quota lifecycle:

```bash
goal-harness heartbeat-prompt \
  --goal-id <STABLE_GOAL_ID> \
  --active-state <ACTIVE_GOAL_STATE_PATH>
```

Copy the generated task body into the Codex App heartbeat automation. It already
contains the pre-turn `quota should-run` guard, operator-gate notification,
quiet non-gate `should_run=false` skip, bounded work, validation/writeback,
optional `refresh-state`, and exactly one post-turn
`quota spend-slot --source heartbeat --execute` event. The generated guard and
spend commands explicitly use the shared global registry so project heartbeats
read the same operator gates and user todos as the dashboard, regardless of
their current repo. Quota slots are minute-granularity by default: minute
heartbeats spend `--slots 1`, while
coarser fixed-interval automations should spend the scheduler minutes consumed
by that completed turn.

Keep the Codex App visible goal text short, for example
`按 ACTIVE_GOAL_STATE.md，基于 Goal Harness 体系，推进项目`. Do not use that short
text as the automation body. Across projects, the automation body should be the
same generated lifecycle prompt with only `goal_id`, `active_state`, and narrow
project boundary rules changed.

## Generate A Review Packet

When a project agent, controller thread, or local shell needs the current
operator packet, prefer the CLI packet over asking the user to find a dashboard
copy button:

```bash
goal-harness review-packet --goal-id <STABLE_GOAL_ID>
```

For machine-readable inspection, put the global format flag before the
subcommand:

```bash
goal-harness --format json review-packet --goal-id <STABLE_GOAL_ID>
```

This command is read-only. It packages the current status into the same Review
Packet shape as the dashboard; it does not append human reward, append an
operator gate, refresh state, grant write-control, or authorize production
actions.

Read the packet in order:

- `人只需判断`: the user or controller decides in the dashboard/operator view or
  trusted local shell. A target project agent cannot self-approve this section.
- `用户本地 Gate 记录草稿`: a local preview for the user/controller. The target
  project agent must not run this draft as its own command.
- `给项目 Agent`: the executable handoff context only after the packet's
  forwarding condition is already satisfied. If its stop condition fires, stop
  and report the exact blocker instead of continuing.

## Connect A New Project

1. Read the project goal document and inspect the repo narrowly.
2. Extract a stable `goal_id`, one-line `objective`, `domain`, authority
   sources, validation surfaces, first safe action, and public/private
   boundary.
3. Run `connect` from the project root. Prefer read-only until the goal doc
   explicitly authorizes mutation:

```bash
goal-harness connect \
  --goal-id <STABLE_GOAL_ID> \
  --objective "<OBJECTIVE_FROM_GOAL_DOC>" \
  --domain <DOMAIN> \
  --goal-doc <GOAL_DOC_PATH> \
  --adapter-kind read_only_project_map_v0 \
  --adapter-status connected-read-only
```

`connect` should create or update the local registry/state and auto-sync the
public-safe entry into `~/.codex/goal-harness/registry.global.json`.

If the goal state or registry contains private evidence, add `.goal-harness/`
and `.codex/goals/` to that project's `.gitignore`.

For a generic read-only connection, create the first non-generic map run:

```bash
goal-harness read-only-map --goal-id <STABLE_GOAL_ID>
```

This reads registry metadata, the active state, and a bounded project-file
inventory, then appends a `read_only_project_map` run. Use it before writing a
project-specific adapter when the dashboard would otherwise stay on
`state_refreshed` or `connected_without_run`.

For a planned high-complexity adapter, preview the same bounded map before
controller opt-in:

```bash
goal-harness read-only-map --goal-id <STABLE_GOAL_ID> --dry-run
```

If the adapter status is `planned`, only the `--dry-run` preview is allowed and
the result should include `opt_in_required=true`. Do not append a real map until
the user or target controller has moved the adapter to `read-only-map-ready`,
`connected-read-only`, or `connected`. Relay the returned `residual_risks`
labels directly; do not invent a separate free-form risk summary.

When the user or target controller answers the opt-in gate, record that answer
before handing the command to another project agent:

```bash
goal-harness operator-gate \
  --goal-id <STABLE_GOAL_ID> \
  --decision approve \
  --reason-summary "<PUBLIC_SAFE_CHINESE_REASON>" \
  --dry-run
```

Use `approve`, `reject`, or `defer`. The dry-run writes nothing; the real append
creates an `operator_gate_*` compact run so `goal-harness status` and the
dashboard can tell whether the project agent may run the approved command. This
is not a human reward signal and does not grant write-control.

## Refresh State After Non-Adapter Work

If the agent updated `ACTIVE_GOAL_STATE.md`, a progress ledger, a planning doc,
or external coordination state without producing a new adapter run, append a
state-only refresh:

```bash
goal-harness refresh-state --goal-id <STABLE_GOAL_ID>
```

This fixes stale dashboards where the latest run still shows an old
`ready_for_controller_opt_in` or similar state. It also auto-syncs the project
entry into the global registry. If you do not pass `--recommended-action`, the
refresh run should publish the first public-safe item from `## Next Action` as
the compact dashboard action, including wrapped continuation lines; keep raw
evidence and private links in the state file, not in that action item.

For complex projects, do not pack a whole user reading queue into
`## Next Action`. Keep the first Next Action item as one routing sentence, then
use the CLI to write explicit checkbox sections instead of hand-editing section
names:

```bash
goal-harness todo add \
  --goal-id <STABLE_GOAL_ID> \
  --role user \
  --text "Read the short review packet before approving delivery."

goal-harness todo add \
  --goal-id <STABLE_GOAL_ID> \
  --role agent \
  --text "Build the next read-only worksheet after the user decision is recorded."
```

The CLI creates the canonical section when needed and avoids duplicate exact
todo text. The resulting Markdown shape is:

```md
## User Todo / Owner Review Reading Queue

- [ ] Read the short review packet.
- [ ] Record the owner decision in the worksheet.

## Agent Todo

- [ ] Build the next read-only worksheet after the user decision is recorded.
```

`goal-harness status` lifts those sections into `user_todos` and `agent_todos`.
The dashboard uses `user_todos` for the first-screen human checklist; project
agents should read `agent_todos` only after health, operator gates, evidence,
and quota allow execution.

## Record Human Reward

When the user gives a clear reward judgment for an exact run, first validate
the overlay and active-state writeback:

```bash
goal-harness reward \
  --goal-id <STABLE_GOAL_ID> \
  --run-generated-at <RUN_GENERATED_AT> \
  --decision <DECISION_LABEL> \
  --reward positive \
  --reason-summary "<PUBLIC_SAFE_CHINESE_REASON>" \
  --follow-up "<PUBLIC_SAFE_NEXT_ACTION>" \
  --write-active-state-summary \
  --dry-run
```

Only after the user has explicitly approved recording the reward, rerun without
`--dry-run`. The durable source of truth is still the run-bound
`human_reward` overlay. The active-state writeback is a `Progress Ledger`
summary for future agents; project agents should read the reward through the
returned `project_agent_visibility.history_command`.

## Multi-Project Status

Inside a project:

```bash
goal-harness status
```

Outside a project, `goal-harness status` should fall back to:

```text
~/.codex/goal-harness/registry.global.json
```

Use explicit sync only for diagnosis or recovery:

```bash
goal-harness sync-global
```

If status shows `unregistered_runtime_goal`:

- If the project is active, run `goal-harness sync-global` or reconnect from
  that project's local registry.
- If the runtime record is obsolete, preview cleanup with
  `goal-harness archive-runtime --goal-id <GOAL_ID>` and only execute cleanup
  when that is clearly intended.

## Validation

After connect or refresh, run the smallest useful set:

```bash
goal-harness registry
goal-harness status
goal-harness check --scan-path <PUBLIC_SAFE_FILE_OR_DIR>
```

For multi-project UI updates, refresh the dashboard status JSON from the global
registry:

```bash
goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" \
  --format json status > <dashboard>/public/status.local.json
```

## Reporting

Report in Chinese when the user is reviewing:

- changed files and whether they are public or local-private;
- validation commands and results;
- how the goal appears in dashboard or attention queue;
- the next safe action;
- any missing gates before decision-advisor or write-controller behavior.

Never include credentials, private docs, raw internal links, production task
ids, or raw local evidence in public repo docs or examples.
