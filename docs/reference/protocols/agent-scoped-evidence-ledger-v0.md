# agent_scoped_evidence_ledger_v0

`agent_scoped_evidence_ledger_v0` defines a thin, chronological read model for
agents that need to replan, hand off, or explain progress without reading raw
rollout logs, private active state, or another agent's detailed working trail.

The contract is a read model. It does not replace `ACTIVE_GOAL_STATE.md`, todo
state, compact run history, status projection, review packets, quota routing, or
the append-only rollout event log.

## Current Sources

LoopX already has useful history and evidence surfaces, but they serve different
jobs:

| Surface | Current job | Gap for agent replan |
| --- | --- | --- |
| `rollout-event-log.jsonl` | Append-only structured events such as todo, quota, refresh, validation, and compact evidence events. | It is a low-level event source, not an agent-facing filtered chronology. |
| `loopx status` | Projects current state, todo index, attention queues, agent lanes, run history, and event summaries. | It answers "what is true now", not "what sequence should this agent review before replanning". |
| `loopx review-packet` | Packages status and attention items for review or handoff. | It is packet-shaped, not a general scoped event ledger. |
| `loopx history` | Reads compact run history and run indexes. | It is run-centric and not equivalent to rollout events. |
| `loopx quota should-run --agent-id ...` | Decides whether a specific agent lane should act. | It can route work by agent, but does not expose a standard per-agent evidence read. |

The missing surface is a public-safe, bounded, agent-scoped ledger that an agent
can read before replanning.

## Ownership Boundary

| Layer | Owns | Must Not Own |
| --- | --- | --- |
| Event sources | Durable append-only events, compact run records, ids, timestamps, and public-safe refs. | Prompt-ready planning summaries or cross-agent privacy policy. |
| Status and review packets | Current projections, attention queues, frontier summaries, and operator packets. | Raw chronological replay or write authority. |
| Quota | Lane routing, spend policy, scheduler hints, and required read hints. | Reconstructing history itself or storing replan rationale. |
| Agent-scoped evidence ledger | Thin chronological rows for the current agent plus compressed frontier for other agents. | Canonical writes, raw logs, raw trajectories, private documents, or full other-agent traces. |
| Acting agent | Reads its scoped ledger before replan or handoff and cites the digest in writeback. | Inferring hidden context from another agent's private lane. |

## Read Model Shape

The first implementation should return JSON and may render Markdown later:

```json
{
  "schema_version": "agent_scoped_evidence_ledger_v0",
  "goal_id": "example-goal",
  "agent_id": "codex-evidence-peer",
  "generated_at": "2026-07-05T00:00:00Z",
  "source": {
    "rollout_event_log": true,
    "run_history": true,
    "todo_projection": true
  },
  "scope": {
    "current_agent_detail": true,
    "other_agent_detail": "compressed_frontier"
  },
  "filters": {
    "todo_id": null,
    "event_kind": null,
    "since": null,
    "limit": 30
  },
  "events": [
    {
      "event_id": "evt_123",
      "recorded_at": "2026-07-05T00:00:00Z",
      "source": "rollout_event_log",
      "event_kind": "todo_update",
      "agent_id": "codex-evidence-peer",
      "todo_id": "todo_123",
      "classification": "implementation_batch",
      "status": "open",
      "summary": "P0 implementation frontier was split into a design contract and a CLI read model.",
      "evidence_refs": ["docs/reference/protocols/agent-scoped-evidence-ledger-v0.md"],
      "boundary": {
        "raw_logs_recorded": false,
        "raw_trajectory_recorded": false,
        "credential_values_recorded": false,
        "absolute_paths_recorded": false
      }
    }
  ],
  "other_agent_frontier": [
    {
      "agent_id": "codex-main-control",
      "vision_summary": "Owns the currently claimed runtime validation slice.",
      "top_todo": "Validate the next control-plane PR batch.",
      "handoff_state": "no_handoff_required",
      "latest_material_at": "2026-07-05T00:00:00Z"
    }
  ],
  "reader_hints": {
    "required_before": ["autonomous_replan", "successor_replan", "handoff"],
    "next_required_reads": [
      "loopx evidence-log --goal-id example-goal --agent-id codex-evidence-peer --thin --limit 30"
    ]
  }
}
```

The schema is intentionally narrow. It should be cheap to produce, cheap to read
in a prompt, and stable enough for quota/replan tests.

## CLI Contract

The first public CLI can be read-only:

```bash
loopx evidence-log --goal-id <goal-id> --agent-id <agent-id> --thin --limit 30
```

Supported filters:

| Option | Meaning |
| --- | --- |
| `--todo-id <todo-id>` | Return rows tied to one todo plus goal-level rows that block it. |
| `--since <iso8601>` | Return rows recorded after a timestamp. |
| `--event-kind <kind>` | Filter rollout event kinds such as `todo_update`, `quota_should_run`, or `validation`. |
| `--include-other-agent-frontier` | Include compressed other-agent frontier rows. This should be on by default for replan packets, but not expand other-agent detail. |
| `--limit <n>` | Bound rows after filtering. Default should be small enough for an agent prompt. |
| `--format json` | Emit the schema above. Markdown can be a later convenience view. |

The command must fail closed on missing `goal_id` or `agent_id`. A vague
surface value such as `codex` should not silently fall into `other-agent`
semantics; callers should pass a registered agent id and, when needed, a
separate host surface such as `codex-app`, `codex-cli`, `opencode`, or `claude-code`.

## Scoping Rules

The current agent gets detailed rows when any of these are true:

- the event has `agent_id` equal to the requested agent id;
- the event references a todo claimed by that agent;
- the event references an unclaimed todo currently selected for that agent lane;
- the event is a gate, blocker, validation, or state projection that directly
  changes that agent's next action;
- the event records a handoff to or from that agent.

Goal-level rows may appear only when they change route, acceptance, global gate,
active next action, or replan obligation.

Other agents should not be shown row by row by default. They should be compressed
into `other_agent_frontier` with bounded `vision_summary`, `top_todo`,
`handoff_state`, and latest material timestamp. This lets an agent understand the
shared direction without inheriting another lane's private scratchpad.

## Replan Integration

When quota or status projects a replan obligation for an agent, the interaction
contract should include required reads:

```json
{
  "effective_action": "autonomous_replan",
  "required_reads": [
    {
      "kind": "agent_scoped_evidence_ledger",
      "command": "loopx evidence-log --goal-id loopx-meta --agent-id codex-evidence-peer --thin --limit 30",
      "reason": "Read this agent's own material chronology before writing a replan delta."
    }
  ]
}
```

The agent should then write back one of:

- a bounded replan delta that cites the ledger digest;
- a successor todo or handoff route;
- a concrete blocker or user todo;
- a no-follow-up rationale when the ledger proves the lane is intentionally
  closed.

An acknowledgement without reading the ledger or writing a bounded delta should
not clear the replan obligation.

## Privacy Boundary

The ledger must preserve the rollout event boundary:

- no raw task text;
- no raw logs, stdout, stderr, trajectories, or verifier tails;
- no credentials, tokens, headers, or secrets;
- no absolute local paths;
- no private document body or chat transcript;
- no private source payload copied into public-safe rows.

Rows may contain compact ids, relative public artifact refs, redacted summaries,
omission notes, and private source counts. If a source is private, the row should
say that only a compact pointer or count was recorded.

## Rollout Plan

1. Add this public contract and keep it separate from runtime changes.
2. Implement a read-only builder over rollout events with agent-id, todo-id,
   kind, since, and limit filters.
3. Merge compact run-history references into the same row shape without changing
   existing `loopx history` semantics.
4. Add other-agent frontier compression from todo/vision/handoff projections.
5. Wire `required_reads` into quota, status, review packets, and autonomous
   replan writeback.
6. Add focused smokes for agent filtering, other-agent compression, privacy
   redaction, and replan required-read stability.
7. Expose discoverability in docs and help text once the CLI path is stable.

## Acceptance

A change satisfies this contract only when:

- `loopx evidence-log` returns a bounded JSON packet for a concrete `goal_id` and
  `agent_id`;
- current-agent rows are detailed while other-agent rows are compressed by
  default;
- filters behave deterministically and do not require parsing raw JSONL in agent
  prompts;
- replan-capable quota/status payloads can point agents to the required ledger
  read;
- the existing status, history, review-packet, and rollout-event-log surfaces
  keep their current responsibilities; and
- public tests prove the privacy boundary without committing private state,
  local paths, raw logs, or raw trajectories.
