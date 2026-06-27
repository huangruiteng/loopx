# openviking_session_memory_adapter_v0

`openviking_session_memory_adapter_v0` is a public-safe specialization of
[`session_runtime_loopx_projection_v0`](session-runtime-loopx-projection-v0.md)
for an OpenViking-style issue-fix workflow. It previews how LoopX can connect
compact per-goal, per-issue session state to memory retrieval decisions without
copying raw trajectories, issue comments, or tool outputs into LoopX state.

This is a read-only adapter contract. It does not perform live OpenViking
retrieval, write memory, read issue/comment bodies, publish comments, create
PRs, or mutate runtime state.

## Boundary

The source of truth remains split:

- the session runtime owns raw transcripts, tool calls, tool outputs,
  trajectories, host auth, and raw execution logs;
- the issue tracker owns issue body text, comment bodies, timelines, and
  provider payloads;
- the memory system owns embeddings, raw memory records, retrieval queries, and
  writeback transactions;
- LoopX owns compact goal state, todos, gates, quota, run history, and
  public-safe projection records.

The adapter may preserve compact join keys such as goal id, issue ref, session
id, memory ref id, run id, and todo id. It must not copy raw bodies, raw
trajectory lines, prompt text, tool output text, credentials, private URLs, or
local filesystem paths.

## Shape

```json
{
  "schema_version": "openviking_session_memory_adapter_v0",
  "mode": "read_only_projection",
  "specializes": "session_runtime_loopx_projection_v0",
  "goal_id": "loopx-meta",
  "issue_projection": {},
  "session_projection": {},
  "memory_projection": {},
  "retrieval_gates": [],
  "status_projection": {},
  "evidence_projection": {},
  "future_gates": [],
  "truth_contract": {
    "source_of_truth": [
      "loopx_goal_state",
      "session_runtime_projection",
      "public_issue_metadata",
      "memory_system_refs"
    ],
    "adapter_is_writable": false,
    "live_retrieval_allowed": false,
    "memory_writeback_allowed": false,
    "issue_body_read_allowed": false,
    "comment_body_read_allowed": false,
    "tool_output_ingest_allowed": false
  }
}
```

## Issue Projection

`issue_projection` is limited to routing metadata:

- `provider`: compact provider label such as `github`;
- `repo`: public repo slug when safe;
- `issue_number`: numeric issue or PR id;
- `issue_ref_id`: compact public-safe join key;
- `title_summary`: optional short summary written by the adapter or operator;
- `issue_body_copied`: always false in public fixtures;
- `comment_bodies_copied`: always false in public fixtures;
- `provider_payload_copied`: always false in public fixtures.

If body or comment text is required for a real fix, represent that as a gate.
Do not copy the text into this projection.

## Session Projection

`session_projection` maps the issue to compact runtime state:

- `runtime_id`;
- `session_refs[]`: public-safe session ids or redacted handles;
- `latest_event_ref`;
- `linked_todo_ids[]`;
- `outcome_refs[]`;
- `raw_trajectory_copied`: false;
- `raw_transcripts_copied`: false;
- `raw_tool_outputs_copied`: false.

The projection may say that a session is blocked, validated, or stale. It must
not include raw prompts, source diffs, tool outputs, trace URLs, or terminal
logs.

## Memory Projection

`memory_projection` is a preview over memory routing, not a memory dump:

- `namespace`: compact memory namespace;
- `retrieval_mode`: `preview_only`, `disabled`, or `future_gated`;
- `live_retrieval_performed`: false for v0 public fixtures;
- `writeback_performed`: false for v0 public fixtures;
- `query_summary`: public-safe summary of why retrieval would be useful;
- `top_k_preview`: requested preview count, not a live retrieval result;
- `candidate_refs[]`: memory reference rows.

Each candidate ref may include:

- `memory_ref_id`;
- `source_kind`: `prior_issue`, `session_outcome`, `operator_note`,
  `validation_summary`, or `unknown`;
- `score_bucket`: `high`, `medium`, `low`, or `unknown`;
- `summary`: compact public-safe note;
- `raw_memory_copied`: false.

The adapter must not expose embeddings, vector contents, raw memory bodies,
private issue text, prompt excerpts, or tool outputs.

## Retrieval Gates

`retrieval_gates[]` describes what must be approved before a real retrieval or
writeback:

- `capability`: `live_openviking_retrieval`, `memory_writeback`,
  `issue_body_read`, `comment_body_read`, or `raw_tool_output_ingest`;
- `state`: `future_gated`, `blocked_without_authority`, or `approved`;
- `required_authority`: compact authority label;
- `blocks`: what would remain disabled until the gate is approved.

In v0, live OpenViking retrieval and memory writeback remain future-gated even
when a public fixture has candidate refs. This keeps the fixture reproducible
and avoids accidental dependency on private local memory stores.

## Status And Evidence Projection

`status_projection` follows the session-runtime first-screen contract:

- `waiting_on`;
- `next_action`;
- `user_action_required`;
- `agent_can_continue`;
- `first_agent_todo`;
- `gate_state`;
- `quota_state`;
- `memory_state`: `preview_only`, `future_gated`, `blocked`, or `disabled`.

`evidence_projection` contains compact refs only:

- `source_refs`: goal, issue, session, memory, todo, and run ids;
- `validation_refs`: smoke, check, CI, or review proof ids;
- `raw_trajectories_copied`, `comment_bodies_copied`,
  `raw_tool_outputs_copied`, `credentials_copied`, `private_paths_copied`:
  all false in public fixtures;
- `public_safe_summary`.

## Future Gates

The following capabilities stay future-gated in v0:

- `live_openviking_retrieval`;
- `memory_writeback`;
- `issue_body_read`;
- `comment_body_read`;
- `raw_tool_output_ingest`;
- `external_issue_comment_or_pr_publish`.

Any future implementation must add a separate live adapter contract with
explicit authority, dry-run preview, audit ids, public/private boundary checks,
and failure behavior before these gates can move to `approved`.

## Acceptance Checks

A public fixture or implementation is acceptable when:

1. `schema_version` is exactly `openviking_session_memory_adapter_v0`;
2. `mode` is exactly `read_only_projection`;
3. `specializes` is exactly `session_runtime_loopx_projection_v0`;
4. issue projection keeps issue body, comment bodies, and provider payload out
   of the fixture;
5. session projection keeps raw trajectories, transcripts, and tool outputs out
   of the fixture;
6. memory projection is preview-only or future-gated, with no live retrieval or
   writeback performed;
7. candidate refs contain compact ids, score buckets, source kind, and summary,
   but no raw memory body;
8. retrieval gates include live retrieval, memory writeback, issue body read,
   comment body read, and raw tool-output ingest;
9. status projection can render the first screen without private evidence; and
10. public fixtures contain no raw trajectories, comment bodies, tool outputs,
    credentials, private links, local paths, or internal project names.
