# local_agent_launch_plan_v0

`local_agent_launch_plan_v0` is a public-safe dry-run contract for previewing
how LoopX would assign local agents to a goal before any host starts a worker,
daemon, server, or external process.

The contract answers a narrow product question: "Given the registered agents,
current quota decision, and todo projection, what launch plan would the
operator see?" It is not a launcher, scheduler, task lease store, or permission
grant.

## Boundary

The source of truth remains:

- the project registry and registered-agent configuration;
- `quota should-run` and its `interaction_contract`;
- todo projection, claims, gates, and run history;
- the active goal state and public/private boundary rules.

The plan may be rendered by a dashboard, Codex App host, or CLI dry-run packet.
Its machine marker is `mode=dry_run`. It must not start a process, allocate a
shell, open a daemon connection, call a remote agent service, or write LoopX
state.

## Shape

```json
{
  "schema_version": "local_agent_launch_plan_v0",
  "mode": "dry_run",
  "goal_id": "loopx-meta",
  "primary_agent_id": "codex-main-control",
  "generated_at": "2026-06-27T04:00:00Z",
  "configured_agents": [],
  "role_assignments": [],
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
    "recompute_rule": "Recompute from registry, quota, todos, gates, and run history before each preview."
  }
}
```

## Configured Agents

`configured_agents[]` is the discovered agent list after registry and
capability gates are applied. Each item should include:

- `agent_id`: registered LoopX agent id;
- `role`: `primary`, `side_agent`, `reviewer`, `observer`, or `blocked`;
- `source`: compact configuration source label, such as
  `registry.coordination.registered_agents`;
- `scope_summary`: public-safe scope summary;
- `can_receive_work`: whether quota and capability gates allow the agent to
  receive a dry-run assignment;
- `blocked_by`: compact blocker labels when the agent cannot receive work.

Do not copy raw automation prompts, private chat history, local worktree paths,
or connector payloads into `scope_summary` or `blocked_by`.

## Role Assignments

`role_assignments[]` maps configured agents to lanes that a host can display.
Required fields:

- `agent_id`;
- `lane`: `primary_control`, `bounded_delivery`, `review_handoff`,
  `monitor_only`, or `blocked`;
- `responsibility`: one compact public-safe sentence;
- `claim_policy`: how todos should be claimed or reviewed;
- `handoff_target_agent_id`: optional next reviewer or controller.

Role assignments are advisory preview rows. A real claim still goes through the
existing todo lifecycle and claim rules.

## Launch Preview

`launch_preview[]` describes what the host would show before a launch. It must
remain non-executable:

```json
{
  "preview_id": "preview_side_agent_delivery",
  "agent_id": "codex-side-bypass",
  "todo_id": "todo_public_slice",
  "next_step_label": "Build the public dry-run fixture slice.",
  "worktree_policy": "independent_worktree_required",
  "host_execution": {
    "will_start_process": false,
    "tool_call_allowed": false,
    "shell_command": null,
    "daemon_required": false,
    "external_service_call": false
  }
}
```

The preview may name a todo id and the worktree policy, but it must not include
a runnable shell command, process id, credential, host auth token, or remote
URL. If a host later adds real local-agent launch support, that is a separate
contract with explicit server/daemon and permission gates.

## Status And Evidence Projection

`status_projection` gives the first screen:

- `waiting_on`: `agent`, `primary`, `user`, `controller`, `runtime`, or
  `none`;
- `next_action`: compact current action;
- `user_action_required`: boolean;
- `agent_can_continue`: boolean;
- `first_agent_todo`: todo id or `null`;
- `gate_state`: `clear`, `user_todo`, `operator_gate`, `blocked`, or
  `deferred`;
- `quota_state`: `eligible`, `throttled`, `operator_gate`, or `blocked`;
- `launch_state`: `preview_only`, `blocked`, or `future_gated`.

`evidence_projection` gives compact public-safe proof:

- `source_refs`: registry, quota, todo, run, or review-packet ids;
- `validation_refs`: smoke, check, CI, or review proof ids;
- `raw_logs_copied`, `raw_transcripts_copied`, `credentials_copied`,
  `private_paths_copied`: all false for public fixtures;
- `public_safe_summary`: one compact summary.

Evidence references are join keys, not payloads. They must not embed raw logs,
full transcripts, private document ids, host URLs, or local absolute paths.

## Future Gates

The following capabilities stay future-gated in v0:

- `server_daemon_launch`: starting or controlling a local LoopX daemon;
- `external_agent_execution`: starting Codex, Claude, worker, CI, or remote
  agent processes from this plan;
- `credentialed_host_actions`: any action that needs host auth, secrets, or
  production access;
- `state_write_from_preview`: claiming todos, approving gates, refreshing
  state, or spending quota from the preview itself.

Each gate should name `state=future_gated` or `state=blocked_without_authority`
and a compact `required_contract` before it can be enabled.

## Acceptance Checks

A fixture or implementation is acceptable when:

1. `schema_version` is exactly `local_agent_launch_plan_v0`;
2. `mode` is exactly `dry_run`;
3. configured-agent discovery includes the primary and at least one non-primary
   agent when present in the registry source;
4. each configured agent has a matching role assignment;
5. every launch preview has `will_start_process=false`,
   `tool_call_allowed=false`, `shell_command=null`,
   `external_service_call=false`, and no runnable command text;
6. status projection exposes waiting actor, next action, user action flag,
   agent continuation flag, gate, quota, and launch state;
7. evidence projection contains compact refs and explicitly marks raw logs,
   transcripts, credentials, and private paths as not copied;
8. server/daemon launch, external execution, credentialed host actions, and
   preview writes remain future-gated; and
9. public fixtures contain no raw transcripts, credentials, private links,
   local paths, or internal project names.
