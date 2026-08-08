# global_manager_command_v0

`global_manager_command_v0` is a read-first protocol for operator commands
such as `/loopx-global-summary`, `/loopx-global-gates`,
`/loopx-global-todos`, and `/loopx-global-risks`.

The product goal is to let a user act as a manager across long-running agent
work: ask for the last day of progress, see blocked decisions, compare agent
lanes, and choose the next safe action without reading every thread.

This protocol is not a general chat-command router yet. It defines the
request, allowed sources, response shape, privacy boundary, and action ladder
for Codex hosts, CLI wrappers, or dashboard command palettes. The implemented
CLI wrappers are `loopx global-summary`, which returns the broad compact
`/loopx-global-summary` digest, and `loopx global-gates`, which returns the
focused current-state `/loopx-global-gates` inbox.

## Command Set

Recommended first commands:

| Command | User intent | Default source window |
| --- | --- | --- |
| `/loopx-global-summary <time range>` | Show progress, completed work, active lanes, and next decisions. | 24 hours |
| `/loopx-global-gates` | Show open user/controller gates and what each blocks. | current state |
| `/loopx-global-todos` | Show top runnable, blocked, deferred-ready, and review todos. | current state |
| `/loopx-global-risks` | Show stale runs, public/private boundary warnings, failing checks, and rollback candidates. | 24 hours |
| `/loopx-pr-review` | Walk the current project's or explicit repository's open and merged GitHub PRs one by one with motivation, scope, checks, risks, and review prompts. | current open + merged PRs, optionally bounded by `--since` |
| `/loop-goal-summary <goal id>` | Drill into one goal without scanning unrelated projects. | 24 hours |

`/loopx-global-todos`, `/loopx-global-risks`, and `/loop-goal-summary` remain
host-only manager commands under this protocol; they do not yet have dedicated
CLI wrappers.

Commands are read-only by default. They can propose follow-up actions, but
they do not approve gates, promote suggested todos, spend quota, merge PRs,
pause automations, or run destructive operations.

Legacy `/loop-global-*` forms may be accepted as aliases during migration, but
hosts should canonicalize command packets and user-facing help to the
`/loopx-global-*` names. These are host/slash aliases, not CLI command names:
unknown commands and legacy CLI aliases fail closed with help instead of
falling back to a broader status or summary dump.

| Legacy alias | Canonical command |
| --- | --- |
| `/loop-global-summary` | `/loopx-global-summary` |
| `/loop-global-gates` | `/loopx-global-gates` |
| `/loop-global-todos` | `/loopx-global-todos` |
| `/loop-global-risks` | `/loopx-global-risks` |

Related project-local command: `/loopx <goal text>` is covered by
[`loopx_goal_command_v0`](loopx-goal-command-v0.md). It is not a global manager
command: it starts one project goal, plans ranked todos, writes them in order,
and then enters the quota-gated automation flow.

Related repo-review command: `/loopx-pr-review` is covered by
[`pr_review_command_v0`](pr-review-command-v0.md). It is read-only and helps a
human review open and merged PRs in the caller's current project or an explicit
`--repo owner/repo` target; it does not approve, comment, merge, or spend quota.

## Request Shape

```json
{
  "schema_version": "global_manager_command_request_v0",
  "command": "/loopx-global-summary",
  "legacy_aliases": ["/loop-global-summary"],
  "time_range": "24h",
  "goal_filter": ["loopx-meta"],
  "agent_filter": ["codex-main-control", "codex-side-bypass"],
  "include": ["progress", "gates", "todos", "risks", "next_actions"],
  "privacy_mode": "public_safe_summary",
  "dry_run": true
}
```

Request rules:

- `privacy_mode` defaults to `public_safe_summary`.
- `goal_filter` and `agent_filter` narrow the read; omitted filters mean all
  registered goals or agents visible in the local control plane.
- For `loopx global-gates`, `--agent-id` excludes goals where the selected
  agent is not registered; an unavailable per-goal quota projection is not a
  substitute for agent filtering.
- `dry_run=true` is the default because the first implementation should be a
  report, not an executor.
- Unknown commands must fail closed with a help packet, not a broad status
  dump.

## Source Reads

Implementations may read only compact LoopX control-plane surfaces:

- global registry and project-local registry entries;
- `loopx status` / status JSON;
- `loopx quota plan` and `quota should-run` summaries;
- active-state todo projections;
- run history summaries;
- rollout event log summaries;
- review packets for explicit goal drilldown.

`loopx global-gates` reads the compact status projection. Status internally
consumes compact run-history state to build its current attention queue, but
the gates builder does not issue a second history read or expose history items
in its response.

They must not include raw transcripts, raw benchmark logs, raw connector
payloads, credentials, local absolute paths, or private source bodies.

## Response Shape

`global_manager_command_response_v0`:

```json
{
  "schema_version": "global_manager_command_response_v0",
  "request": {
    "command": "/loopx-global-summary",
    "time_range": "24h"
  },
  "generated_at": "2026-06-24T00:00:00Z",
  "summary": {
    "headline": "Three active goals advanced; one user decision is open.",
    "progress_count": 3,
    "open_gate_count": 1,
    "runnable_todo_count": 4,
    "risk_count": 2
  },
  "lanes": [
    {
      "goal_id": "loopx-meta",
      "agent_id": "codex-product-capability",
      "status": "eligible",
      "top_todo_id": "todo_example",
      "last_event_id": "event_example",
      "next_safe_action": "Review and merge the public-safe protocol PR."
    }
  ],
  "gates": [
    {
      "gate_id": "gate_example",
      "owner": "user",
      "blocks": ["todo_example"],
      "question": "Approve promoting the candidate todo?",
      "next_safe_action": "Wait for explicit approval."
    }
  ],
  "risks": [
    {
      "kind": "public_boundary_warning",
      "severity": "high",
      "evidence_refs": ["check_public_boundary"],
      "next_safe_action": "Run the public/private boundary scan before merge."
    }
  ],
  "actions": [
    {
      "action_id": "act_review_pr",
      "kind": "review",
      "requires_user_approval": false,
      "requires_executor_separation": true,
      "target_agent_id": "codex-reviewer",
      "preview": "Assign protocol review to the selected registered peer."
    }
  ],
  "omissions": [
    "Raw logs and private connector payloads were intentionally omitted."
  ]
}
```

Focused gate responses follow these relation rules:

- a formal user gate comes from the interaction contract or a formal open
  user-gate todo, not merely from the count of all open user todos;
- `blocks` uses the gate todo's `unblocks_todo_id` when present, then a verified
  decision-scope relation, and otherwise falls back to the goal scope rather
  than guessing from the selected runnable todo;
- `waiting_on=user_or_controller` is routing metadata, not a new gate-owner
  enum; gate owners continue to use the protocol's user, controller,
  registered-agent, or external-system owner classes.

## Action Ladder

Responses may include actions, but each action must declare its authority:

| Action kind | Default authority |
| --- | --- |
| `read_more` | Agent may run another read-only compact command. |
| `review` | Use an ordinary claim or independent handoff; declare executor separation only when required. |
| `promote_todo` | Requires user/controller approval before `loopx todo add`. |
| `ask_user` | User-facing question; no delivery on blocked path until answered. |
| `pause_or_resume` | Requires explicit operator approval. |
| `merge_or_publish` | Requires repository policy, clean validation, and any explicit review or operator gate. |
| `rollback_or_history_rewrite` | Requires a `rollback_packet_v0` and explicit approval. |

The protocol should make it obvious when the user is being asked to decide,
when an explicit peer review is required, and when the current peer can safely continue.

## Privacy Boundary

Every response must include or imply these boundary facts:

```json
{
  "raw_logs_recorded": false,
  "raw_transcripts_recorded": false,
  "raw_connector_payloads_recorded": false,
  "credential_values_recorded": false,
  "absolute_paths_recorded": false,
  "private_source_bodies_recorded": false
}
```

If a useful summary needs private material, the command should return a gate
or omission, not the material itself.

## Acceptance Checks

A first implementation is acceptable when:

- command responses are read-only by default;
- `loopx global-summary` and `loopx global-gates` emit their matching canonical
  command responses, while the remaining manager commands stay host-only;
- each command names its compact LoopX source surfaces;
- gates name owner, formally related blocked todo or goal scope, question, and
  next safe action;
- agent filtering excludes goals where the selected agent is not registered;
- unknown commands and legacy CLI aliases fail closed with help;
- actions declare approval and ownership requirements;
- risks carry public-safe evidence refs;
- no raw logs, transcripts, credentials, local paths, or private source bodies
  are recorded;
- `python3 examples/project/global-manager-command-protocol-smoke.py` passes.
