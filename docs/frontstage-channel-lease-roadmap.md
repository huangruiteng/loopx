# Frontstage Channel And Lease Roadmap

LoopX should not become a chat product. Its durable value is the
backstage control plane: registry, active state, append-only event history,
quota, gates, leases, and auditable recovery. The missing product layer is a
frontstage projection that lets people understand and coordinate that control
plane without reading raw CLI dumps.

This note frames the product direction as:

```text
frontstage channel UX + backstage LoopX ledger
```

The channel is a view. The ledger is truth.

## Product Boundary

LoopX should borrow collaboration language without moving the source of
truth into chat history:

- A **goal can project as a channel**: one timeline with latest state, next
  action, user todos, agent todos, gates, artifacts, quota, and run events.
- An **agent can project as a workspace member**: controller, executor,
  reviewer, monitor, critic, or dreaming/planning proposer, each with scope and
  last action.
- A **task claim should be a per-todo lease**: explicit ownership of one
  `todo_id` with TTL, write scope, idempotency key, and conflict policy.
- A **chat or channel thread is a projection**: useful for human collaboration,
  but never the only durable authority.

The key product lesson is not "add Slack-like chat". It is that humans think in
channels, members, tasks, and approvals, while agents need registry, state,
history, quota, gates, and leases.

## Minimal Schemas

### `goal_channel_projection_v0`

This is a read-only, human-facing projection over existing LoopX state.
It lets a frontstage render a goal as a channel without making the channel a
new source of truth. The append-only run ledger, active state, and registry
remain authoritative; the projection only carries compact source references and
freshness metadata.

```json
{
  "schema_version": "goal_channel_projection_v0",
  "goal_id": "loopx-meta",
  "display_name": "LoopX Meta",
  "generated_at": "2026-06-20T00:00:00Z",
  "source_refs": {
    "status_generated_at": "2026-06-20T00:00:00Z",
    "active_state_updated_at": "2026-06-20T00:00:00Z",
    "latest_run_generated_at": "2026-06-19T23:55:00Z",
    "review_packet_generated_at": null
  },
  "waiting_on": "codex",
  "latest_status": "terminal_bench_case_running",
  "next_action": "compact-poll the active benchmark job",
  "decision_frame": {
    "user_action_required": false,
    "agent_action_required": true,
    "quiet_noop_allowed": false
  },
  "quota": {
    "state": "eligible",
    "reason": "1 compute quota",
    "spend_policy": "spend after validated writeback"
  },
  "user_todos": [
    {
      "todo_id": "todo_user_1",
      "title": "Review the bounded delivery packet.",
      "status": "open",
      "priority": "P0"
    }
  ],
  "agent_todos": [
    {
      "todo_id": "todo_agent_1",
      "title": "Advance the first executable safe side path.",
      "status": "open",
      "priority": "P1",
      "claimed_by": "codex-side-bypass"
    }
  ],
  "open_gates": [
    {
      "gate_id": "gate_owner_decision",
      "kind": "operator_gate",
      "status": "waiting_on_user",
      "blocks": ["todo_user_1"]
    }
  ],
  "artifacts": [
    {
      "kind": "doc",
      "label": "latest public review packet",
      "path": "docs/showcases/README.md"
    }
  ],
  "active_leases": [
    {
      "todo_id": "todo_agent_1",
      "owner_agent": "codex-side-bypass",
      "lease_until": "2026-06-20T00:30:00Z",
      "write_scope": ["docs/**"]
    }
  ],
  "recent_events": [
    {
      "generated_at": "2026-06-19T23:55:00Z",
      "classification": "validated_progress",
      "summary": "public-safe compact progress event"
    }
  ],
  "source_warnings": []
}
```

The v0 source map should stay boring and inspectable:

| Projection field | Source surface |
| --- | --- |
| `goal_id`, `display_name`, `waiting_on`, `latest_status` | `loopx status` project asset and registry metadata |
| `next_action`, `user_todos`, `agent_todos`, `open_gates` | active state todo/gate sections plus `review-packet` summaries |
| `decision_frame` | `interaction_contract` from `quota should-run` and review-packet routing |
| `quota` | `quota should-run`, including the spend policy and capability/workspace guards when present |
| `artifacts` | public-safe docs, compact run artifacts, review packets, or showcase assets already allowed by `goal_boundary` |
| `active_leases` | current soft claims and future `task_lease_v0` records |
| `recent_events` | compact run-history rows only, not raw logs or transcripts |
| `source_warnings` | stale state, todo projection gaps, private-boundary omissions, or missing authority sources |

The projection must exclude raw chat transcripts, raw benchmark task text, raw
trajectories, credentials, production logs, private document URLs, local
absolute paths, and write-capable commands. If a useful frontstage field would
need one of those sources, emit a compact `source_warnings` item instead of
copying the raw material.

Frontstage consumers should treat this as an input snapshot:

- refresh it from LoopX rather than editing it in the UI;
- render controlled actions as links to CLI/review-packet flows, not as hidden
  write authority;
- show stale or missing-source warnings near the affected card;
- keep event detail drill-downs tied to compact run artifacts; and
- never let the channel view override `goal_boundary`, operator gates, quota,
  required capabilities, workspace guards, or task leases.

The first product-path fixture lives in `loopx.frontstage` and is covered
by `examples/goal-channel-projection-smoke.py` plus
`examples/goal-channel-frontstage-fixture-smoke.py`. It intentionally stays
read-only: callers pass already-compact status, quota, run-history,
review-packet, artifact, and lease/claim payloads; the builder emits
`source_warnings` when raw or private-looking fields appear instead of copying
those values into the channel. The static HTML fixture in
`examples/goal-channel-frontstage-fixture.py` renders that projection into
semantic panels with `data-panel` markers, no write controls, and a visible
truth contract. `loopx --format json status` and the loopback
`serve-status` feed now expose the same read-only projection on
`attention_queue.items[].goal_channel_projection`, so a dashboard can render the
channel without recomputing project truth.

### `agent_profile_v0` And `agent_member_v0`

The registry-owned `agent_profile_v0` contract is defined in
[`docs/product/agent-profile-contract.md`](product/agent-profile-contract.md).
Use it as the source of truth for registered agent id, primary/side role,
default scope, worktree policy, and review handoff policy. The channel roadmap
only needs the read-only member projection.

This is an identity and permission projection for an actor participating in a
goal:

```json
{
  "schema_version": "agent_member_v0",
  "agent_id": "codex-local-controller",
  "role": "controller",
  "goal_id": "loopx-meta",
  "write_scope": ["docs/**", "examples/**", "loopx/**"],
  "last_action": "refresh_state",
  "claim_id": null
}
```

Roles should stay product-level and portable: controller, executor, reviewer,
monitor, critic, dreaming_proposer. A role can guide UI copy and default
permissions, but the concrete authority still comes from `goal_boundary`,
leases, and active-state todos.

### `task_lease_v0`

This is the concurrency contract that should eventually back task claim. The
pending key is per todo: `(goal_id, todo_id)`. Do not serialize an entire
goal just because one todo is claimed; independent todos under the same goal
should remain independently claimable when gates and write scopes allow it.
LoopX does not have a separate issue object in this runtime model:
`goal_id` names the control-plane boundary, and `todo_id` names the work item
inside that boundary.
The v0.1 control plane still keeps role assignment simple: one
`coordination.primary_agent` owns review/merge/publication for the goal, and
side agents claim scoped todos and work in separate git worktrees. They may
self-merge small AGENTS-eligible validated changes with explicit evidence;
otherwise they add a primary-agent review todo when finishing.

```json
{
  "schema_version": "task_lease_v0",
  "todo_id": "todo_123",
  "owner_agent": "codex-local-controller",
  "goal_id": "loopx-meta",
  "lease_until": "2026-06-15T12:30:00Z",
  "write_scope": ["docs/frontstage-channel-lease-roadmap.md"],
  "idempotency_key": "loopx-meta:todo_123:20260615T1230Z",
  "conflict_policy": "fail_closed_on_scope_overlap",
  "status": "active"
}
```

The first implementation can be local and file-backed. A later server can own
the same schema with stronger locking, lease renewal, and stale-claim cleanup.
Conflicts should be detected by `(goal_id, todo_id)` plus overlapping
write-scope checks: another agent may claim a different todo in the same goal,
but a second pending claim on the same todo must fail closed, renew, or
explicitly transfer ownership.

## Priority

P1:

- Design and test `task_lease_v0` first. It prevents lost writes and concurrent
  controller confusion, and it naturally extends the existing todo locking
  lane. The durable invariant is per-todo pending: one active pending lease per
  `(goal_id, todo_id)`, not one active lease per goal or project.
- Treat the shipped React `/frontstage` route as the baseline
  `goal_channel_projection_v0` reader. Future work should polish visual
  acceptance, operator onboarding, and local fixture realism while preserving
  the invariant that the CLI/status export is the source and the browser has no
  write authority.

P2:

- Add agent-member projection to status/review packets after leases exist, so
  agent identity is useful rather than decorative.
- Build a Raft-style local frontstage view that renders channel timelines and
  member activity from LoopX projections.
- Let dreaming/planning proposals appear as a separate channel lane or badge.
- Add bridge adapters that can post channel summaries to collaboration tools,
  while preserving LoopX as the ledger of record.

## Non-Goals

- Do not make conversation history the only project state.
- Do not let UI membership labels override `goal_boundary`, operator gates, or
  run permissions.
- Do not require a server for the first schema; the CLI must remain a usable
  fallback/client.
- Do not let background dreaming claim delivery work without the normal
  `quota should-run` and lease path.

## Acceptance Frame

The first successful slice should prove that a human can open one goal view and
see:

- what the goal is;
- who or what is currently responsible;
- which task is claimed and until when;
- which files/surfaces that claim may touch;
- which event made the current state true;
- what the next safe action is.

The corresponding agent should be able to read the machine projection and avoid
double-running, double-spending, or writing outside scope.
