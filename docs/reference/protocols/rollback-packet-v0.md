# rollback_packet_v0

`rollback_packet_v0` is the public-safe compensation protocol for long-running
LoopX work. It describes what must be undone, fixed forward, cleaned up, or
monitored after a delivery step creates risk. It is a plan and evidence
packet, not an execution permission.

Rollback in LoopX is broader than `git revert`. A long-horizon task may need to
compensate repository commits, local state projections, external resources,
open PRs, cached public surfaces, todo ownership, or user gates. The packet
keeps those relationships explicit so agents do not erase history, repeat the
same unsafe action, or leave the operator guessing what remains exposed.

## Product Contract

The packet exists to answer five questions:

1. What visible or durable state is affected?
2. Which todo, rollout event, commit, PR, or external resource caused it?
3. Is the next safe action a revert, fix-forward patch, state correction,
   support request, external cleanup, or monitor?
4. Who must approve protected or destructive steps?
5. Which validation and public/private boundary checks prove the compensation
   is complete?

## Shape

```json
{
  "schema_version": "rollback_packet_v0",
  "packet_id": "rollback_public_boundary_example_v0",
  "goal_id": "public-long-horizon-loop",
  "created_at": "2026-06-24T01:20:00+08:00",
  "trigger": {
    "kind": "public_boundary_leak",
    "summary": "A public PR surface exposed context that should remain local.",
    "todo_ids": ["todo_public_boundary_repair"],
    "source_event_ids": ["evt_lh_005_minimal_fixture_validated"]
  },
  "scope": {
    "repository_refs": {
      "commit_refs": ["abcdef1"],
      "pr_refs": ["huangruiteng/loopx#617"]
    },
    "todo_ids": ["todo_public_boundary_repair"],
    "external_resource_refs": ["github_support_request"],
    "user_visible_surfaces": ["pull_request", "cached_view"],
    "local_state_refs": []
  },
  "decision": {
    "owner": "maintainer",
    "required": true,
    "reason": "History rewrite and external cached-view removal require explicit owner action.",
    "default_safe_action": "pause_and_monitor"
  },
  "plan": [
    {
      "step_id": "clean_main_history",
      "kind": "history_rewrite",
      "action": "replace public branch history with a clean equivalent commit set",
      "requires_gate": true,
      "destructive": true,
      "automatable_by_agent": false
    },
    {
      "step_id": "submit_support_request",
      "kind": "support_request",
      "action": "ask provider support to remove read-only PR refs and cached views",
      "requires_gate": true,
      "destructive": false,
      "automatable_by_agent": false
    },
    {
      "step_id": "verify_public_boundary",
      "kind": "validation",
      "action": "scan normal heads and changed public paths for private markers",
      "requires_gate": false,
      "destructive": false,
      "automatable_by_agent": true
    }
  ],
  "todo_compensation": {
    "complete_todo_ids": ["todo_submit_support_request"],
    "add_todos": [
      {
        "role": "agent",
        "task_class": "continuous_monitor",
        "title": "Verify provider-side cached view removal after support response."
      }
    ],
    "supersede_todo_ids": []
  },
  "validation": {
    "commands": [
      "git diff --check",
      "loopx check --scan-path <public-safe-path>",
      "git ls-remote --heads origin"
    ],
    "public_boundary_scan_required": true,
    "success_criteria": [
      "normal public heads no longer contain the affected public markers",
      "provider-owned cached views or read-only refs are removed or tracked by an open external gate",
      "successor monitor todo exists when external cleanup is pending"
    ]
  },
  "boundary": {
    "raw_task_text_recorded": false,
    "raw_logs_recorded": false,
    "raw_trajectory_recorded": false,
    "raw_session_transcript_recorded": false,
    "credential_values_recorded": false,
    "absolute_paths_recorded": false
  }
}
```

## Kinds

Allowed trigger kinds:

- `validation_regression`;
- `public_boundary_leak`;
- `operator_request`;
- `external_setup_partial_failure`;
- `wrong_owner_or_lane`;
- `bad_state_projection`;
- `release_or_publish_mistake`.

Allowed plan step kinds:

- `git_revert`: create a normal revert commit;
- `fix_forward`: keep history and add a correcting patch;
- `history_rewrite`: rewrite public branch history; always protected;
- `state_compensation`: correct LoopX active state, todo metadata, or rollout
  event projections;
- `external_cleanup`: clean up an external resource;
- `support_request`: ask a provider to remove read-only or cached surfaces;
- `todo_supersede`: replace stale todos with successor work;
- `validation`: prove the compensation state.

## Commit And Todo Linkage

Commit-to-todo linkage is the minimum useful rollback anchor. A public PR or
commit should be traceable to:

- one or more `todo_id` values;
- one or more rollout event ids when available;
- validation commands or public-safe evidence refs;
- successor todos or no-follow-up rationale after completion.

This linkage does not require every commit message to encode every detail. It
does require enough durable state for a later agent to answer "which todo does
this commit compensate, supersede, or validate?" without reading private chat
history.

When linkage is missing, use a rollback packet to create the missing
compensation todos before touching history.

## Safety Rules

- A rollback packet does not authorize destructive git commands, force pushes,
  production actions, provider support requests, external deletes, or public
  comments.
- `history_rewrite` requires explicit user or maintainer approval and a backup
  or equivalent recovery point.
- Provider-owned read-only refs, cached views, or search indexes are external
  cleanup. If normal repository commands cannot remove them, the packet must
  keep a user/support gate or monitor todo open.
- External-resource setup should prefer partial-success preservation over
  deletion. If a usable board, base, environment, or artifact was created,
  save the minimum usable local config first, then treat optional enrichment
  failures as warnings or follow-up work.
- Fix-forward is preferred when it avoids protected history operations and
  fully removes user-facing risk.
- Public fixtures and packets must not include raw logs, raw transcripts,
  credentials, local absolute paths, or private source bodies.

## Acceptance Checks

A valid packet or implementation must prove:

- `schema_version` is exactly `rollback_packet_v0`;
- every plan step has `step_id`, `kind`, `action`, `requires_gate`,
  `destructive`, and `automatable_by_agent`;
- destructive or provider-owned actions require a gate;
- the packet links at least one todo, rollout event, commit/PR ref, or external
  resource ref;
- todo compensation is explicit when work remains after the rollback step;
- validation commands are public-safe labels, not raw logs;
- boundary flags are present and false.

The durable smoke is:

```bash
python3 examples/protocol/rollback-packet-protocol-smoke.py
```
