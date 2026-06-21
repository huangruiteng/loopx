# Session Runtime Control-Plane Adapter

Status: public-safe architecture target + read-only projection contract v0.

LoopX should be able to sit beside an existing agent host without
becoming that host. The target role is a long-horizon task control plane:
turn session-level execution facts into goal-level state that is recoverable,
auditable, gated, attention-ranked, and reusable across sessions.

## Layer Boundary

An agent host owns the execution plane:

- agent definitions and runtime configuration;
- environment and session lifecycle;
- append-only session events;
- tool and sandbox execution;
- host authentication, rate limits, billing, trace, and audit;
- raw transcripts, raw logs, and raw tool outputs.

LoopX owns the goal-level control projection:

- `goal_state`: objective, non-goals, authority sources, current boundary;
- `run_projection`: compact session/outcome summary with pointers to source
  facts;
- `operator_gate`: cross-session owner/controller decisions;
- `human_reward`: human judgment on a route or run result, separate from a
  task scorer;
- `work_lane_contract`: advancement, monitor, blocker, and user-gate routing;
- `quota_decision`: whether the goal should spend the next automatic agent
  turn;
- `handoff_packet`: the approved next action for a project agent;
- `dreaming_proposal`: background exploration that remains advisory until
  promoted.

A product surface owns the frontstage user experience: task cards, approvals,
progress, recovery entry points, and collaboration views. LoopX should
explain why a card exists, whether it may run, which gate blocks it, and how it
recovers after approval; it should not become the default end-user console.

## Core Principle

The host session log is the raw fact source. LoopX run history is a
compact control projection. A projection may reference host ids such as session,
event, tool call, artifact, approval, or outcome ids, but it must not copy full
transcripts, credentials, raw logs, private traces, or sandbox internals into
LoopX state.

This avoids a second event store. If the host says a session completed and Goal
Harness says a goal is still blocked, the projection must explain the
reconcile rule: missing gate, missing validation, failed outcome, stale
artifact, or human decision not yet recorded.

## Adapter Phases

### Phase 1: Read-Only Projection

Input: compact host summaries for sessions, events, outcomes, approvals, and
artifacts.

Output: a LoopX attention item with:

- `waiting_on`;
- `next_action`;
- first open user todo;
- first executable agent todo;
- latest validation or blocker;
- gate state;
- compact source pointers.

This phase must not write back to the host, alter runtime behavior, or launch a
session. The first useful demo is a long-running task first screen that answers
four questions:

1. Who or what is the goal waiting on?
2. Can the agent continue now?
3. What gate or evidence is required before continuing?
4. What did the most recent run validate or block?

### Phase 2: Controlled Writeback

After the read-only projection proves useful, LoopX may map compact
control events back to host metadata or events:

- operator gate requested/resolved;
- human reward or route judgment;
- handoff packet accepted;
- quota decision as a scheduler hint, not billing;
- artifact pointer or run projection pointer.

Writeback must remain compact and reversible. It should not copy raw evidence
or turn LoopX into the host's permission system.

### Phase 3: Product Surface Integration

The product surface should display LoopX projections instead of asking
users to read the LoopX dashboard directly. LoopX remains the
reliability and governance layer behind the product view.

## Non-Goals

LoopX should not:

- reimplement the host's agent loop or model strategy;
- reimplement the host's event store;
- run tools or sandboxes directly when the host already owns them;
- replace host authentication, billing, rate limits, or trace;
- become the product frontstage for ordinary end users;
- store raw transcripts, private traces, credentials, or raw benchmark logs.

## First Public Contract

A minimal read-only adapter contract can be shaped as:

```json
{
  "schema_version": "session_runtime_readonly_projection_v0",
  "source": {
    "host_kind": "session_runtime",
    "source_ids_redacted": true
  },
  "session_facts": {
    "session_count": 1,
    "latest_event_at": "2026-01-01T00:00:00Z",
    "outcome_status": "blocked",
    "approval_state": "none",
    "raw_transcript_copied": false
  },
  "goal_projection": {
    "waiting_on": "codex",
    "next_action": "write compact blocker or continue approved handoff",
    "first_user_todo": null,
    "first_agent_todo": "advance one bounded segment",
    "latest_validation": "compact validation summary"
  }
}
```

The public fixture should prove only projection semantics. Private source ids,
raw event bodies, exact host URLs, raw logs, credentials, and local paths stay
outside the repository.

The current v0 implementation is a pure builder,
`loopx.session_runtime.build_session_runtime_readonly_projection(...)`.
It accepts compact session, event, outcome, gate, artifact, and decision-result
summaries, then returns:

- `first_screen`: waiting owner, user action, agent action, validation, blocker,
  and recommended next step;
- `attention_item`: a compact dashboard/status item with source pointers;
- `work_lane_contract`: `user_gate`, `advancement_task`, `blocker`, or
  `monitor`;
- `reconcile_rule`: the rule that host logs remain raw facts while Goal
  Harness stores only compact control projection.

Run:

```bash
python3 examples/session-runtime-readonly-projection-smoke.py
```

## Metrics

The integration is valuable if it improves:

- interrupted task recovery rate;
- duplicate compute avoided;
- owner gates preserved across sessions;
- cross-session handoff success;
- stale projection detection;
- time from "task is blocked" to "the right owner sees the blocker".

These metrics are goal-control metrics, not model-quality scores.
