# State Machine

This is the product-level state machine for one LoopX heartbeat or manual tick.
It is not a new store. It is a deterministic view over registry, active state,
todos, gates, run history, quota, event ledger, and projections.

## Top-Level Machine

```mermaid
stateDiagram-v2
  [*] --> Registered
  Registered --> Ready: registry + active state resolved
  Ready --> QuotaCheck: heartbeat / manual tick / slash command

  QuotaCheck --> BoundedDelivery: eligible + runnable candidate
  QuotaCheck --> ScopedGateFallback: scoped gate + independent fallback
  QuotaCheck --> UserGate: gate covers selected action
  QuotaCheck --> ExternalEvidenceWait: external handle pending
  QuotaCheck --> MonitorQuiet: monitor not due or unchanged
  QuotaCheck --> AgentScopeWait: current agent has no scoped candidate
  QuotaCheck --> FocusWait: outcome floor or fresh-evidence floor
  QuotaCheck --> Repair: projection, boundary, workspace, or capability drift
  QuotaCheck --> ThrottledPaused: quota exhausted or paused

  BoundedDelivery --> WritebackSpend: artifact / blocker / evidence validated
  ScopedGateFallback --> WritebackSpend: fallback validated
  FocusWait --> WritebackSpend: recovery evidence validated
  Repair --> WritebackSpend: repair delta validated

  UserGate --> Ready: decision recorded
  ExternalEvidenceWait --> Ready: terminal evidence or blocker written
  MonitorQuiet --> Ready: no-spend liveness preserved
  AgentScopeWait --> Ready: reassigned / unblocked / new todo projected
  ThrottledPaused --> Ready: quota restored or pause lifted

  WritebackSpend --> Ready: refresh-state + spend when allowed
  WritebackSpend --> Done: terminal goal/todo outcome
  Done --> [*]
```

## Transition Table

| From | Guard | To | Required Writeback |
| --- | --- | --- | --- |
| `Registered` | Registry entry and active-state route resolve. | `Ready` | None, or registry repair event if resolution changed. |
| `Ready` | A host tick or user command asks whether work should run. | `QuotaCheck` | None before the guard. |
| `QuotaCheck` | Runnable candidate and no covering gate. | `BoundedDelivery` | Selected todo/run evidence after validation. |
| `QuotaCheck` | A gate is open but does not cover the selected fallback. | `ScopedGateFallback` | Gate remains visible; fallback evidence after validation. |
| `QuotaCheck` | Gate covers the selected action. | `UserGate` | Concrete user/controller decision, defer, rejection, or successor todo. |
| `QuotaCheck` | External evidence is pending or a launched handle must be observed. | `ExternalEvidenceWait` | Terminal evidence, compact observation, or blocker. |
| `QuotaCheck` | Monitor-only work is not due or unchanged. | `MonitorQuiet` | At most one no-spend monitor-poll event when contracted. |
| `QuotaCheck` | Current agent has no scoped candidate or waits on another owner. | `AgentScopeWait` | No spend; wait for todo lifecycle, reassignment, or unblock event. |
| `QuotaCheck` | Outcome floor or fresh-evidence floor blocks ordinary delivery. | `FocusWait` | Recovery evidence or blocker. |
| `QuotaCheck` | Source/projection/boundary/workspace/capability is inconsistent. | `Repair` | Repair delta, blocker, or concrete gate. |
| `QuotaCheck` | Quota exhausted or explicitly paused. | `ThrottledPaused` | None until quota/pause changes. |
| `BoundedDelivery` | Work validated. | `WritebackSpend` | Artifact, code/doc ref, test result, blocker, or evidence ref. |
| `WritebackSpend` | Todo/goal terminal. | `Done` | Completion rationale and archive/successor state. |
| `WritebackSpend` | More work remains. | `Ready` | Refreshed projection and one spend when the contract allows it. |

## Gate Scope Submachine

```mermaid
flowchart TD
  G["Gate open"] --> S{"does scope cover selected action?"}
  S -->|"yes"| A["ask concrete decision"]
  S -->|"no"| F["keep gate visible; run independent fallback"]
  S -->|"ambiguous"| R["repair projection or ask controller"]
  A -->|"approve"| U["unblock gated todo"]
  A -->|"reject"| X["supersede or create compensation todo"]
  A -->|"defer"| D["deferred resume_when"]
  F --> V["validate fallback"]
  V --> W["write fallback evidence and spend once"]
```

The key rule: a gate is scoped authority, not a global boolean. If the scope is
ambiguous, the machine goes to repair; it does not guess from prose.

## Todo Lifecycle Submachine

```mermaid
stateDiagram-v2
  [*] --> Suggested
  Suggested --> Open: promoted
  Open --> Claimed: claimed_by set
  Claimed --> Running: quota allows bounded delivery
  Running --> Done: validation/evidence accepted
  Done --> SuccessorOpen: follow-up required
  Done --> Archived: no follow-up required
  Open --> Blocked: concrete blocker
  Open --> Deferred: resume_when
  Deferred --> ResumeReady: condition satisfied
  ResumeReady --> SuccessorReplan: reopen, supersede, or no-follow-up rationale
  Open --> Superseded: replacement todo
  Superseded --> ReplacementOpen
```

`Running` is derived from quota and run history. It should not become a new
mandatory persistent todo status unless the event stream explicitly models it.

## Projection Sink Submachine

```mermaid
flowchart LR
  S["Canonical state bodies"] --> B["Projection builder"]
  B -->|"fresh and complete"| V["Read-only view"]
  B -->|"missing, stale, conflicting"| G["Projection gap"]
  G --> R["repair source or builder"]
  R --> B
  V -->|"user action"| W["LoopX write API"]
  W --> S
```

Frontstage, review packets, status cards, manager summaries, and external
kanban rows are projection sinks. They can make state understandable, but all
state-changing actions return through LoopX write APIs.

## Catalog Linkage

| Machine Edge | Catalog Patterns |
| --- | --- |
| `QuotaCheck -> BoundedDelivery` | IP-001 Bounded Delivery |
| `QuotaCheck -> ScopedGateFallback` | IP-002 Blocked Priority With Safe Fallback; IP-003 Scoped Gate With Safe Fallback |
| `QuotaCheck -> UserGate` | IP-004 Concrete User Todo Projection |
| `QuotaCheck -> Repair` | IP-005 State Projection Gap; IP-021 Per-Todo Capability Gate |
| `QuotaCheck -> FocusWait` | IP-007 Outcome Floor Recovery |
| `QuotaCheck -> MonitorQuiet` | IP-008 Monitor Quiet Skip |
| `QuotaCheck -> AgentScopeWait` | IP-026 Agent-Scoped No-Candidate Gap; IP-029 Handoff Todo Gate State |

If a new interaction pattern cannot point to a state-machine edge, it is
probably a product note, a UI variant, or a private incident label rather than
a core control-plane pattern.
