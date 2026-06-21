# Session Runtime to LoopX Contract

Status: public-safe contract v0 for read-only first-screen projections.

This contract defines how an external agent runtime can map a visible session
into LoopX without making LoopX the runtime, copying private traces, or hiding
the user's primary control surface. It is intentionally runtime-neutral: Codex
CLI, Claude Code, Cursor, custom workers, and future host integrations should
all be able to project the same small shape.

## Boundary

The session runtime owns:

- session lifecycle, model/tool execution, sandboxing, host auth, and billing;
- raw transcripts, raw logs, raw tool outputs, and host audit trails;
- host-native session, event, tool-call, artifact, and approval ids.

LoopX owns:

- goal id, goal boundary, and authority sources;
- todo, gate, quota, run history, reward, and handoff state;
- compact public-safe projections over session facts;
- controlled writeback decisions through LoopX commands or equivalent adapters.

The first integration mode is read-only. A runtime may feed compact session
facts to LoopX, but LoopX must not write to the runtime, launch a new session,
or claim same-session automation until a separate controlled-write contract is
accepted.

## Identity Map

Every projection should preserve the join keys needed to debug a handoff while
keeping private data out of LoopX state.

| Field | Owner | Meaning |
| --- | --- | --- |
| `goal_id` | LoopX | Stable goal being controlled. |
| `agent_id` | LoopX | Registered automation or human-facing agent lane. |
| `runtime_id` | Runtime adapter | Public-safe runtime family, such as `codex_cli_tui` or `custom_worker`. |
| `session_id` | Runtime adapter | Public-safe handle for the visible session or worker. Redact when unsafe. |
| `run_id` | LoopX | Compact LoopX run-history event that records the projection. |
| `event_id` | Runtime adapter | Optional compact source event pointer. |
| `todo_id` | LoopX | Linked todo when the projection selects or blocks a concrete task. |
| `outcome_id` | Runtime adapter | Optional compact outcome/result pointer. |

`session_id`, `event_id`, and `outcome_id` are references, not evidence
payloads. They must not embed raw prompts, local paths, credentials, private
document ids, or full host URLs.

## First-Screen Projection

The first screen is the minimum operator view needed to decide whether a loop
can continue:

| Field | Required | Description |
| --- | --- | --- |
| `waiting_on` | yes | `none`, `user`, `controller`, `agent`, `runtime`, or `external_evidence`. |
| `next_action` | yes | One compact safe action, written for the current actor. |
| `open_user_todo` | yes | First concrete user todo, or `null`. |
| `first_executable_agent_todo` | yes | First runnable agent todo after quota, scope, and capability gates, or `null`. |
| `latest_validation` | yes | Latest compact validation, blocker, or missing-evidence summary. |
| `gate_state` | yes | `clear`, `user_todo`, `operator_gate`, `blocked`, `deferred`, or `approved`. |
| `quota_state` | yes | `eligible`, `throttled`, `monitor_quiet_skip`, `operator_gate`, or `blocked`. |
| `boundary` | yes | Read/write scope, private-data rule, and stop condition. |

The projection should be useful even when no session is currently attached. In
that case, `runtime_id` may be `none`, `session_id` may be `null`, and
`latest_validation` should explain which runtime fact is missing.

## Minimal JSON Shape

```json
{
  "schema_version": "session_runtime_loopx_projection_v0",
  "goal_id": "loopx-meta",
  "agent_id": "codex-side-bypass",
  "runtime": {
    "runtime_id": "codex_cli_tui",
    "session_id": "public-safe-session-handle",
    "source_ids_redacted": false
  },
  "loopx_refs": {
    "run_id": "run_123",
    "todo_id": "todo_123",
    "event_id": "evt_123",
    "outcome_id": null
  },
  "first_screen": {
    "waiting_on": "agent",
    "next_action": "advance the first executable agent todo",
    "open_user_todo": null,
    "first_executable_agent_todo": "todo_123",
    "latest_validation": "last run validated install smoke",
    "gate_state": "clear",
    "quota_state": "eligible",
    "boundary": {
      "mode": "read_only_projection",
      "raw_transcripts_copied": false,
      "credentials_copied": false,
      "private_paths_copied": false,
      "stop_condition": "stop for user gate, missing authority, or unsafe write"
    }
  }
}
```

## Product Surfaces

The same contract should feed two different surfaces:

- **Showcase frontstage:** public fixtures only, rendered as narrative case
  cards or motion states. It may dramatize progress, gates, and handoffs, but it
  must not publish live registry state.
- **Local control plane:** live private/local projections for the operator.
  It may show session handles and current gates when they are safe in the local
  environment, but those details stay out of GitHub Pages and public docs.

## Acceptance Checks

A session-runtime projection is acceptable when:

1. `goal_id`, `agent_id`, `runtime_id`, and LoopX refs are enough to reconcile a
   handoff without copying raw evidence.
2. `waiting_on`, `next_action`, user todo, agent todo, validation, gate, and
   quota state can be rendered on the first screen.
3. Missing runtime facts become explicit blockers or `null` fields, not guessed
   actions.
4. The projection is read-only unless a separate writeback contract is enabled.
5. Public fixtures contain no raw transcripts, credentials, private links,
   local paths, or internal project names.

