# Host Integration Surface v0

LoopX host integrations let an agent host use the LoopX control
plane without becoming a second LoopX runtime. The compatibility
baseline remains the CLI. Hook, MCP, and server adapters are thin facades over
the same registry, active state, run history, quota, todo, gate, optional
lease, and public/private boundary contracts.

The v0 protocol contract is intentionally small: thin hook activation,
lifecycle reads, controlled todo/gate writes, future optional lease writes,
compact status projection, CLI fallback, and public/private boundary
invariants. It does not prove that any adapter is installed, and it does not
grant write authority beyond the existing CLI-equivalent LoopX
lifecycle.

## Roles

| Surface | Job | Must Not Do |
| --- | --- | --- |
| Hook activation | Start a host turn with the current LoopX lifecycle contract and route the agent toward `quota should-run`. | Embed stale project policy, schedule hidden work, or replace the user's visible TUI/control surface. |
| MCP adapter | Expose read and controlled write tools to a host that already understands tool calls. | Store raw transcripts, bypass LoopX CLI semantics, or invent host-specific permission rules. |
| Loopback server adapter | Provide compact status and controlled write endpoints for local dashboards or host runtimes. | Bind remotely by default, publish private state, or make browser/frontstage/server writes authoritative without CLI-equivalent dry-run. |
| CLI fallback | Preserve a deterministic path for every read and write when the hook/MCP/server layer is absent or unhealthy. | Become a hidden headless execution path for TUI-first bootstrap unless the user explicitly opted in. |

## Thin Hook Activation

A host hook may only activate the current LoopX lifecycle. It should:

1. resolve the goal id and registered agent id;
2. run or instruct the host to run `loopx doctor` if the CLI is missing;
3. read `quota should-run` with the shared global registry;
4. pass the resulting `interaction_contract`, `goal_boundary`, and selected
   `agent_lane_next_action` into the host turn;
5. stop when the user channel requires a concrete question or payload todo; and
6. leave scheduling, quota spend, and writeback to the normal LoopX
   lifecycle.

The hook body should stay thin like a generated heartbeat prompt. Project
policy belongs in registry metadata, active state, authority sources, and
adapter output. If a hook needs project-specific branches, treat that as a
LoopX product gap before copying policy into host code.

For Codex CLI /goal visible TUI bootstrap, hook activation must preserve the
visible TUI as the primary surface. It may generate the thin `/goal` body or a
copyable bootstrap message, but it must not silently switch to hidden
`codex exec`, read session transcripts, or claim same-TUI automation without
the visible proof and idle-detection contracts.

## Lifecycle Reads

Host integrations should expose read methods that map directly to CLI reads:

| Capability | CLI Baseline | Output Shape |
| --- | --- | --- |
| Health and installation | `loopx doctor` | compact readiness plus missing pieces |
| Registry and goal boundary | `loopx registry` and `quota should-run` | goal id, adapter status, write scope, registered agents, stop condition |
| Status and attention queue | `loopx --format json status` | first-screen status, user todos, agent todos, gate state, freshness warnings, optional read-only projections such as `task_graph_projection_v0` |
| Quota decision | `loopx --format json quota should-run --goal-id <goal-id> --agent-id <agent-id>` | `interaction_contract`, execution obligation, workspace guard, spend policy |
| Review packet | `loopx --format json review-packet --goal-id <goal-id>` | human/controller decision packet and agent handoff context |
| Run history | `loopx history` or status projections | compact run ids, classification, outcome, validation, blocker pointers |

Read methods return compact control facts. They must not return raw session
logs, raw benchmark task text, raw trajectories, private document bodies,
credentials, local absolute paths, or host auth material.
Optional projections such as `task_graph_projection_v0` and
`long_task_cadence_policy_v0` are read-only inputs to a host integration. They
do not add graph write authority, change quota gates, or create a new source of
truth.

## Controlled Writes

Writes must be CLI-equivalent, idempotent where possible, and fail closed when
the host lacks authority. A host adapter may expose these write classes:

| Write Class | CLI Baseline | Required Guards |
| --- | --- | --- |
| Todo claim and lifecycle | `loopx todo claim/update/complete` | registered agent id, active-state file lock, task class, optional primary review successor |
| User/agent todo creation | `loopx todo add --role user|agent` | public-safe text, concrete actor, duplicate detection |
| Gate decision | `loopx operator-gate --decision approve|reject|defer` | explicit controller/user decision, dry-run preview before write |
| Human reward | `loopx reward ... --dry-run` then explicit write | run-bound judgment, public-safe reason, no score impersonation |
| Lease or claim projection | `claimed_by` today; future `task_lease_v0` | `(goal_id, todo_id)` contention key; `task_lease_v0` stays optional and future until CLI/server lease commands ship |
| State refresh and quota spend | `refresh-state`, then `quota spend-slot --source heartbeat --execute` | validation evidence first, one spend per completed automatic turn |

The adapter must not translate a host approval, model confidence, browser click,
frontstage action, server callback, or scheduler timer into a protected write
unless the corresponding LoopX contract allows that write.
Browser/frontstage/server writes remain non-authoritative by default unless a
loopback capability advertises a dry-run/preview endpoint and the same
operation has a CLI fallback.

## Compact Status Projection

The host-facing status projection should be small enough for dashboards,
hooks, and MCP clients:

```json
{
  "schema_version": "host_integration_surface_v0",
  "goal_id": "loopx-meta",
  "agent_id": "codex-side-bypass",
  "host_kind": "codex_cli_tui",
  "activation": {
    "mode": "thin_hook",
    "visible_surface_required": true
  },
  "lifecycle_reads": ["doctor", "status", "quota_should_run", "review_packet"],
  "projection_inputs": ["task_graph_projection_v0", "long_task_cadence_policy_v0"],
  "write_capabilities": ["todo_lifecycle", "gate_decision"],
  "optional_write_capabilities": ["task_lease_v0_when_shipped"],
  "cli_fallback": {
    "available": true,
    "required_for_writes": true
  },
  "boundary": {
    "raw_transcripts_copied": false,
    "credentials_copied": false,
    "private_paths_copied": false,
    "remote_bind_default": false
  }
}
```

This projection is not project truth. It is a host capability map plus the
current LoopX lifecycle pointers. The registry, active state, event
ledger, todos, gates, quota, and future task leases remain authoritative. A
host may consume task graph or cadence projections, but those projections
remain derived read-only facts and never grant write authority.

## CLI Fallback

Every host integration must document the CLI fallback for the same operation.
Minimum fallback set:

```bash
loopx doctor
loopx --format json status --agent-id <agent-id>
loopx --format json --registry "$HOME/.codex/loopx/registry.global.json" quota should-run --goal-id <goal-id> --agent-id <agent-id>
loopx todo claim --goal-id <goal-id> --todo-id <todo_id> --claimed-by <agent-id>
loopx todo complete --goal-id <goal-id> --todo-id <todo_id> --claimed-by <agent-id> --evidence "<public-safe evidence>"
loopx refresh-state --goal-id <goal-id> --agent-id <agent-id>
loopx quota spend-slot --goal-id <goal-id> --slots 1 --source heartbeat --execute --agent-id <agent-id>
```

If the host adapter is unavailable, the user or automation can run those
commands and preserve the same state transitions. If a host offers an operation
without a CLI fallback, that operation is experimental and must not be used as
the default project control path.

## Public/Private Boundary

Host integrations must preserve these invariants:

- Raw host transcripts, raw tool outputs, raw benchmark task text,
  trajectories, verifier tails, credentials, production logs, and local private
  paths stay in the host or private project store.
- LoopX state stores compact summaries, public-safe evidence pointers,
  decision labels, todo ids, gate ids, lease ids, and run ids.
- Loopback servers bind locally by default and reject remote write authority
  unless a separate deployment contract says otherwise.
- MCP/server tools must report denied or missing authority as structured
  blockers instead of guessing around gates.
- Hook prompts and adapter code must not carry long project-specific policy
  branches; regenerate or read current LoopX state each turn.
- The Codex CLI TUI path remains visible-first. Hidden headless execution is
  only an explicit fallback, not the default bootstrap or same-session proof.

## Acceptance Checks

A host adapter is acceptable when:

1. `quota should-run` remains the first delivery gate;
2. user-channel action requirements surface concrete user todos/questions;
3. every write class has a CLI-equivalent command and dry-run/preview when the
   write affects gates, reward, leases, or browser-triggered actions;
4. duplicate todo claim, stale lease, stale status, and daemon-down cases fail
   closed or fall back to CLI;
5. compact status projection excludes raw/private material and marks optional
   projections as read-only inputs rather than authority; and
6. validation covers one hook activation packet, one lifecycle read, one
   controlled write preview, one CLI fallback path, and one public/private
   boundary trap.
