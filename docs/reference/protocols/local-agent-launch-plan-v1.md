# local_agent_launch_plan_v1

`local_agent_launch_plan_v1` is a public-safe dry-run contract for previewing
how LoopX could assign local peer agents to current todos before any host starts
a worker, daemon, server, or external process.

It answers one narrow question: "Given registered peers, quota, todo claims,
task policy, and current gates, what launch preview should the operator see?"
It is not a launcher, scheduler, task lease store, or permission grant.

## Boundary

The source of truth remains:

- registry `coordination.agent_model=peer_v1` and `registered_agents`;
- `quota should-run` and its `interaction_contract`;
- todo projection, claims/leases, capabilities, gates, and run history;
- task/repository workspace and review policy.

The plan is `mode=dry_run`. It must not start a process, allocate a shell, open
a daemon connection, call a remote agent service, claim a todo, or write LoopX
state.

## Shape

```json
{
  "schema_version": "local_agent_launch_plan_v1",
  "mode": "dry_run",
  "goal_id": "loopx-meta",
  "agent_model": "peer_v1",
  "generated_at": "2026-07-10T04:00:00Z",
  "configured_agents": [],
  "task_assignments": [],
  "launch_preview": [],
  "status_projection": {},
  "evidence_projection": {},
  "future_gates": [],
  "truth_contract": {
    "source_of_truth": [
      "registry",
      "quota_should_run",
      "todo_projection",
      "run_history"
    ],
    "plan_is_authoritative": false,
    "plan_is_executable": false,
    "write_api": false,
    "launch_command_allowed": false,
    "recompute_rule": "Recompute before each preview."
  }
}
```

There is no goal-level leader id. A host may show which peer is selected for a
task bundle, but that coordinator is deterministic and temporary; it gains no
durable authority over other identities.

## Configured Agents

`configured_agents[]` is the discovered peer list after identity and capability
checks. Each item includes:

- `agent_id`;
- `agent_model=peer_v1`;
- optional advisory `profile_role` and `scope_summary`;
- `source`, normally `registry.coordination.registered_agents`;
- `can_receive_work` and compact `blocked_by` reasons.

Do not copy raw automation prompts, private chat history, local paths, or
connector payloads into the preview.

## Task Assignments

`task_assignments[]` maps current todos to peers for display. Required fields:

- `agent_id` and `todo_id`;
- `assignment_kind`: `claimed`, `unclaimed_candidate`, `review_handoff`,
  `monitor_only`, or `blocked`;
- `responsibility`: one compact public-safe sentence;
- `claim_policy`: how the todo must be claimed or transferred;
- optional `blocks_agent` / `unblocks_todo_id` for explicit review dependency.

Assignments are advisory preview rows. A real claim or transfer still uses the
todo lifecycle. A profile cannot supply an implicit reviewer.

## Launch Preview

Each preview describes what the host would show before launch and remains
non-executable:

```json
{
  "preview_id": "preview_peer_delivery",
  "agent_id": "codex-product",
  "todo_id": "todo_public_slice",
  "next_step_label": "Build the public dry-run fixture slice.",
  "workspace_policy": "selected_task_requires_isolation",
  "host_execution": {
    "will_start_process": false,
    "tool_call_allowed": false,
    "shell_command": null,
    "daemon_required": false,
    "external_service_call": false
  }
}
```

The preview may name a todo and task workspace policy, but it must not include a
runnable command, process id, credential, auth token, private path, or remote
URL. Real launch support requires a separate host execution contract.

## Status And Evidence Projection

`status_projection` includes `waiting_on`, `next_action`,
`user_action_required`, `agent_can_continue`, `first_agent_todo`, `gate_state`,
`quota_state`, and `launch_state`.

`evidence_projection` carries compact source and validation refs plus explicit
false markers for raw logs, transcripts, credentials, and private paths.
Evidence refs are join keys, not embedded payloads.

## Future Gates

These remain future-gated:

- `server_daemon_launch`;
- `external_agent_execution`;
- `credentialed_host_actions`;
- `state_write_from_preview`.

Each gate names `future_gated` or `blocked_without_authority` and the required
contract before it can be enabled.

## Acceptance Checks

A fixture or implementation is acceptable when:

1. `schema_version=local_agent_launch_plan_v1`, `agent_model=peer_v1`, and
   `mode=dry_run`;
2. configured agents are unique peers with no leader/parent role;
3. every task assignment references a configured peer and existing todo;
4. review ownership exists only through explicit `review_handoff` assignment;
5. every preview keeps all host execution booleans false and command null;
6. status and evidence projections remain compact and public-safe;
7. all real launch, credential, and preview-write capabilities remain gated.
