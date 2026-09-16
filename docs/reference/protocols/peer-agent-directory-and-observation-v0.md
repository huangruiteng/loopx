# peer_agent_directory_v0

`peer_agent_directory_v0` is the reusable LoopX contract for one Agent
discovering, observing and delivering a bounded request to another Agent. It is
the Agent-facing companion of
[`agent_management_projection_v0`](agent-management-projection-v0.md): that
projection answers "what does the operator see", this contract answers "what may
a peer or a steward see and do about it", under the identity and authority rules
of [`peer_agent_runtime_v1`](peer-agent-runtime-v1.md) and the shared-intent
rules of
`docs/architecture/rfcs/shared-goal-alignment-and-governed-amendment-v0.md`.

It exists because both the steward channel and the peer Agents inside one Goal
need the same three abilities, and each of them is currently answered by a
different internal surface:

1. **Directory** — which Agents exist for this Goal, and which of them is
   running right now;
2. **Observation** — what bounded state and output may I read about one of them;
3. **Delivery** — how may I hand one of them a bounded request, and what does a
   successful hand-off actually prove?

The contract is provider-neutral. A host surface that owns a terminal space may
supply *presence* and *live output* (see [Related work](#related-work)); a
prompt-only transport supplies neither, and the contract still works with the
durable half.

## Sources Of Truth

Nothing here is a new source of truth.

| Field group | Canonical owner |
| --- | --- |
| Agent identity, registration, `agent_model` | Goal registry (`registered_agents`) |
| Work item, claim, lease/fence | `todo_id`, task lease, per-Agent frontier |
| Canonical intent and its revision | `shared_goal_intent_v0` |
| Delivery of context or a bounded request | `context_handoff` (with its receipt) |
| Lane, quota and next action | quota `interaction_contract`, lane contract |
| Terminal layout, pane and live process | the host surface that owns the terminal space |

Two consequences follow, and both are rules rather than observations:

- a live session never creates an Agent identity, and an Agent that has no live
  session is still registered, still owns its claims, and is still a delivery
  target;
- a host surface's view of the terminal is **advisory**. It is not evidence of
  LoopX progress, and it may not overwrite any row in the table above.

## Directory Packet

```json
{
  "schema_version": "peer_agent_directory_v0",
  "goal_id": "loopx-meta",
  "collected_at": "2026-09-16T10:00:00Z",
  "scope": "goal_registered_agents",
  "rows": [
    {
      "agent_id": "codex-alpha",
      "registered": true,
      "work": {
        "todo_id": "todo_ab12",
        "claimed": true,
        "lease": "active"
      },
      "presence": {
        "provider": "terminal_space",
        "provider_session_ref": "w1:p2",
        "liveness": "working",
        "observed_at": "2026-09-16T09:59:58Z",
        "basis": "provider_detection"
      },
      "observation_limits": ["provider_scrollback_bounded"]
    }
  ],
  "limitations": ["presence_is_advisory", "presence_stale_after_provider_restart"]
}
```

Rules:

- a row exists per registered Agent of the Goal, whether or not it is running;
- `presence` is optional and must carry `provider`, `observed_at` and `basis`,
  so a reader can tell "not running" from "this machine cannot see it";
- `provider_session_ref` is an opaque handle **inside one provider session**.
  It is never a Goal identity, never stable across providers, and must not be
  compared across machines or used as a Todo/Agent key;
- a provider's own in-space proof of context (for example an environment flag and
  injected pane identifiers) may strengthen "I am inside this space". It never
  replaces registry registration, and a failure of that proof means the reader
  reports `unknown`, not `absent`.

## Presence Vocabulary

Presence answers "is this Agent runnable right now", not "is its work done".

| `liveness` | Meaning | Must not be read as |
| --- | --- | --- |
| `working` | the provider observed the Agent executing | progress, or evidence of an outcome |
| `blocked` | the provider recognized a question or approval gate | work done, or permission to answer the gate |
| `idle` | the Agent is ready for input | a delivered request, or an available lease |
| `done` | the Agent settled and is ready for input | task completion, or a closed Todo |
| `unreachable` | the provider knows the target, and cannot reach it now | an empty lane, or missing work |
| `unknown` | the provider cannot classify the target | completion, or absence of progress |

`done` and `idle` are both "ready for input" for a directory reader; the
provider's seen/unseen bookkeeping distinguishes them and is deliberately not
part of this contract. A reader that cannot obtain presence reports `unknown`
and names the coverage gap instead of inferring anything about the work.

## Bounded Observation

Observation prefers typed state and falls back to bounded output.

1. **Typed first.** Work state, frontier, claims, lease facts, gates and
   evidence come from LoopX projections (`shared_goal_alignment_v0`,
   `agent_management_projection_v0`, the Agent-scoped evidence ledger), never
   from parsing a terminal.
2. **Bounded output second.** When a caller needs what a peer actually said or
   did, the provider may return a bounded excerpt: an explicit source
   (rendered viewport, recent output, unwrapped recent output, detection
   snapshot), an explicit line bound, and an explicit "this is advisory" label.
3. **Declared limits.** A provider must state its limits instead of silently
   truncating: alternate-screen output that never enters scrollback, a cleared
   viewport, a restarted server, a disconnected machine.
4. **Durable fallback.** When bounded output cannot carry the answer, the caller
   asks the peer to write a durable artifact (file, Todo note, delivery
   receipt) and reads that. A screen excerpt is never promoted to evidence.

## Bounded Delivery

Delivery hands a peer a bounded request or context. The contract separates four
facts that are easy to conflate:

1. **Refusal before write.** If the target is at a question or approval gate, the
   delivery is refused with a typed blocker (`agent_blocked`-style) and writes
   nothing. Resolving that gate belongs to the gate's owner, not to the sender.
2. **Submission is not execution.** A successful submission proves bytes were
   written in order. It does not prove the peer started a turn.
3. **Observed activity is the weaker-but-real signal.** Where the provider can
   observe lifecycle, a delivery should also report whether activity followed
   inside a declared window, with a typed `stalled` outcome when it did not, and
   an expiry outcome when the sender's own timeout elapsed first.
4. **No blind resend.** A timeout or a stall does not prove the request was never
   delivered, so the sender inspects state before repeating; `context_handoff`
   delivery receipts remain the durable record that a delivery happened.

## Authority And Scope

- **Observation grants nothing.** Discovery and observation confer no claim, no
  lease, no priority, no plan change, no merge and no permission.
- **Delivery is not a work edit.** Handing a peer context or a request stays
  delivery. Changing what the Goal asks for stays an amendment
  (`shared_acceptance`, `protected_authority`), and changing work state stays
  with the canonical Todo, quota and lane owners.
- **No leader Agent.** A directory reader is not a scheduler for its peers. The
  rules that forbid a leader agent, hidden scheduler, promotion authority or
  second source of truth apply to this contract exactly as written for the
  multi-agent launcher.
- **Scope is authorization, not convenience.** A reader sees only the Agents and
  Goals its channel or Goal authorization covers. The directory must not become
  a cross-tenant enumeration surface, and an out-of-scope target is reported as
  a scope gap rather than as a missing Agent.
- **Host-surface control stays with the host.** Closing, moving or reconfiguring
  another actor's terminal space is a host-surface action with the host's own
  consent rules; it is not part of peer delivery.

## Provider Contract

A provider that supplies presence and live output must declare:

1. how a caller proves it is inside the space (and that failing the proof means
   `unknown`, not control);
2. opaque, session-scoped identifiers for its locations and occupants, plus the
   rule for what happens to an identifier after a move, close or restart;
3. its liveness vocabulary and the mapping into the vocabulary above;
4. its observation sources and bounds, including what it cannot recover;
5. its refusal and error taxonomy for delivery (blocked target, stalled
   submission, expired timeout, unreachable host);
6. its persistence claim: what survives a client detach, a server restart and a
   machine restart.

LoopX ships no requirement that a provider exists. With no provider, the
directory degenerates to registered identity plus durable work state, presence
is omitted, and delivery remains available through the durable hand-off path.

## Related Work

Herdr (`https://github.com/herdrdev/herdr`) is a terminal-space provider whose
Agent-facing skill documents the same three abilities from the other direction,
which is why it is a useful reference implementation of the provider half of
this contract:

- it proves caller context with an environment flag plus injected workspace, tab
  and pane identifiers, and instructs the Agent to stop when that proof fails;
- it separates a raw pane surface from a recognized-agent surface, and its
  liveness vocabulary (`working`, `blocked`, `idle`, `done`, `unknown`) matches
  the mapping above, including "`unknown` does not prove completion";
- it exposes bounded observation with explicit sources and line bounds, and
  names the alternate-screen limit that makes a larger read impossible;
- it refuses `agent prompt` at an approval gate before writing, reports a stalled
  submission when no activity follows, and warns that a timeout does not prove
  non-delivery;
- it owns terminals rather than wrapping Agents, keeps its identifiers
  session-scoped, and restores layout without resurrecting processes.

What LoopX adds, and a terminal-space provider cannot supply: durable Agent
identity, the canonical intent revision an Agent's frontier is based on,
claim/lease ownership, typed gates, and the authority rule that observation and
delivery grant nothing.

## Non-Goals

- No new agent registry, session table, pane inventory or message bus.
- No cross-machine identity: two providers may use the same identifiers for
  different Agents, and neither is authoritative.
- No screen scraping as evidence, and no parsing a peer's terminal to decide
  LoopX state.
- No control of another actor's terminal space, and no remote upgrade of a
  provider to unlock a missing capability.

## Acceptance Checks

- A Goal with two registered Agents and one live session returns two rows: the
  live one with presence, the other with registry identity and no presence.
- A provider that cannot classify a running Agent yields `unknown` with a named
  coverage gap, and the answer never claims the peer made no progress.
- A delivery to a gated peer is refused with a typed blocker and writes nothing;
  a stalled delivery reports `stalled` rather than success; a timeout never
  triggers an automatic resend.
- With no provider at all, the directory still lists registered Agents and the
  durable delivery path still works.
- No field added by this contract changes a Todo, a claim, a lease, quota or the
  canonical intent.
