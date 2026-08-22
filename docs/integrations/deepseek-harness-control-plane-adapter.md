# DeepSeek Harness Control-Plane Adapter

Status: public-safe architecture target, read-only projection v0 connected.

DeepSeek Harness (dsh) is a plugin-based agent harness on vendored
[Cordis](https://github.com/cordis/cordis). LoopX sits beside it as a
long-horizon task control plane: turn session-level execution facts into
goal-level state that is recoverable, auditable, gated, attention-ranked, and
reusable across sessions.

## Why dsh is a natural control-plane target

dsh's architecture makes it a well-defined control-plane target:

- **Everything is a plugin.** The model adapter, tool registry, session log,
  and agent loop itself are all plugins. There is no privileged core to patch;
  registrations are Cordis effects that unwind when their plugin unloads.
- **Session log is append-only and durable.** Every agent event, tool call,
  and assistant message is an immutable fact in the log. LoopX can project
  compact summaries from these facts without copying raw transcripts.
- **Capability seam.** Every subsystem exposes a typed service seam
  (`ctx.sessions`, `ctx.tools`, `ctx.llm`, `ctx.agents`). A LoopX observer
  plugin can read these seams without altering host behavior.
- **Profiles and bundles.** Composition is declarative. A LoopX observer
  bundle can be stacked into any profile as a patch layer, inheriting the
  host's Cordis lifecycle (mount, event, effect, dispose).

## Layer boundary

| Plane | Owns | Does not own |
| --- | --- | --- |
| dsh host | Agent definitions, runtime config, Cordis tree, session log, tool execution, model streaming, sandbox, host auth, billing, trace | Goal-level state, cross-session gates, quota decisions, operator decisions |
| LoopX | Goal state, run projection, operator gates, quota, todo lifecycle, work-lane routing, evidence pointers, handoff packets | Raw transcripts, raw logs, credentials, tool outputs, sandbox internals |
| Product surface | Task cards, approvals, progress, recovery entry points, collaboration views | Raw control-plane state |

## Adapter phases

### Phase 1: Read-only projection (current)

A LoopX observer plugin reads the dsh session log and Cordis context to project
compact summaries:

- `goal_state`: objective, non-goals, authority sources, current boundary.
- `run_projection`: compact session/outcome summary with source pointers.
- `operator_gate`: cross-session owner/controller decisions.
- `work_lane_contract`: advancement, monitor, blocker, user-gate routing.
- `quota_decision`: whether the goal should spend the next automatic agent turn.

The read-only map bootstrap (Phase 1 entry) is already complete:

```bash
cd /path/to/deepseek-harness
loopx bootstrap --project . --goal-id deepseek-harness-goal \
  --adapter-kind read_only_project_map_v0 \
  --adapter-status connected-read-only
```

### Phase 2: Controlled writeback

After the read-only projection proves useful, LoopX may map compact control
events back to dsh metadata. Writeback is compact and reversible:

- operator gate requested/resolved;
- handoff packet accepted;
- quota decision as a scheduler hint;
- artifact pointer or run projection pointer.

### Phase 3: Observer bundle

A LoopX observer bundle (`dsh-loopx-observer`) can be stacked into any dsh
profile as a patch layer. It observes Cordis events (`session/event`,
`agent/step`, `agent/turn-stopping`) and emits compact LoopX projections
without blocking the host loop.

## Key seams for adapter work

dsh's Cordis tree exposes these seams that a LoopX adapter can observe:

| Cordis key | What it carries | LoopX projection target |
| --- | --- | --- |
| `ctx.sessions` | Append-only `SessionEvent` log, in-memory store | `run_projection`, `work_lane_contract` |
| `ctx.agents` | `Agent` interface, live registry, `agent/*` events | `goal_state`, `handoff_packet` |
| `ctx.tools` | Scoped tool registry, guarded execution pipeline | Tool-call evidence pointers |
| `ctx.llm` | Message and stream vocabulary, adapter seam | Model usage metadata |
| `ctx.systemPrompt` | Prompt-section and tool-schema assembly | Prompt audit surface |

Each seam is a typed Cordis service — reading it does not mutate host state.

## Session log projection

The dsh session log is the raw fact source. Each entry carries a type, a
timestamp, and a payload. LoopX projects compact summaries with source
pointers:

```json
{
  "schema_version": "dsh_session_readonly_projection_v0",
  "source": {
    "host_kind": "deepseek_harness",
    "session_id": "dsh:session:<id>",
    "event_count": 42,
    "raw_transcript_copied": false
  },
  "session_facts": {
    "started_at": "2026-08-14T00:00:00Z",
    "latest_event_at": "2026-08-14T01:00:00Z",
    "turn_count": 3,
    "tool_call_count": 12,
    "outcome_status": "completed"
  },
  "goal_projection": {
    "waiting_on": "codex",
    "next_action": "advance one bounded segment",
    "first_agent_todo": "write compact blocker or continue approved handoff",
    "latest_validation": "compact validation summary"
  }
}
```

## Non-goals

LoopX should not:

- reimplement dsh's agent loop or model strategy;
- reimplement dsh's event store;
- run tools or sandboxes directly when dsh already owns them;
- replace dsh authentication, billing, rate limits, or trace;
- become the product frontstage for ordinary dsh users;
- store raw transcripts, private traces, credentials, or raw benchmark logs.

## Bootstrap verification

```bash
cd /path/to/deepseek-harness
loopx bootstrap --project . --dry-run
loopx --registry .loopx/registry.json status
loopx --registry .loopx/registry.json check --scan-root .
```

## Related documents

- [Session runtime control-plane adapter](session-runtime-control-plane-adapter.md)
- [Complex project read-only adapter](complex-project-readonly-adapter.md)
- [Runtime connector catalog](runtime-connector-catalog.md)
- [Integration guide](../integration.md)