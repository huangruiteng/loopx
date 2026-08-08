# One governed turn

LoopX is not about "running an Agent in an infinite loop." It compiles current project facts into one
bounded, verifiable, writable work contract. This chapter starts from the `quota should-run` decision and
explains how the user, Agent, and CLI each assume different obligations within a single turn.

## What you should learn

After this chapter, you should be able to:

- explain why quota is a decision kernel rather than only a balance check;
- read the user, Agent, and CLI channels in an `interaction_contract`;
- distinguish bounded delivery, user gate, monitor quiet, replan, repair, and terminal;
- decide whether an Agent result is sufficient for canonical writeback;
- explain why validation, refresh, receipt, and spend must happen in that order;
- explain why a scheduler hint is not execution authority.

## From Source Facts to an Interaction Contract

Every turn begins by reading current facts, not by reusing the judgment from the previous prompt:

```text
registry and goal boundary
  + todo frontier and claims
  + decision scopes and gates
  + capability and workspace
  + evidence freshness and run history
  + quota and scheduler context
  + vision / replan obligations
  -> interaction_contract
```

`loopx quota should-run` is the main entry point for this decision surface. Historical compatibility
fields may still provide `should_run`, `action_required`, or `recommended_action`, but a new reader
should prioritize:

1. `interaction_contract.mode`;
2. the user, Agent, and CLI channels;
3. selected Todo, goal boundary, and guards;
4. scheduler hint and spend policy;
5. then use compatibility fields for supporting display.

`should_run: false` alone cannot distinguish "waiting for the user," "monitor not yet due," "no
in-scope work for the current Agent," or "control-plane repair needed." Those states require entirely
different next actions.

## Three channels can be true at once

[`loopx_interaction_contract_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/quota-allocation.md)
splits one turn's obligations into three views:

### User channel

It answers:

- whether the user must act now;
- whether to notify or remain quiet;
- the concrete question, decision scope, and reason;
- whether the Gate blocks only a specific action, lane, or the entire Goal.

### Agent channel

It answers:

- whether this Agent must attempt work;
- whether delivery is allowed;
- whether a quiet no-op is allowed;
- which single primary action owns the turn;
- whether this is ordinary delivery, observation, repair, or replan.

### CLI channel

It answers:

- which lifecycle commands come next;
- how validation leads to refresh or writeback;
- when spend is allowed;
- why a Gate, wait, or no-change poll must not spend.

The three channels are not mutually exclusive booleans. For example:

```text
user channel:
  action_required = true
  action = approve homepage publication

agent channel:
  must_attempt = true
  primary_action = run an independent link check

CLI channel:
  spend_after_validation = true
```

The user Gate remains visible, but it does not cover the independent link-check Todo. Collapsing the
three channels into "a user Todo exists, so stop the Agent" loses the scoped fallback. Collapsing them
into "the Agent can run, so do not notify the user" is equally wrong.

## Common interaction modes

A mode compresses a related set of states into a testable contract. External developers should at least
be able to recognize these categories:

| Mode | Agent behavior | User behavior | Spend |
| --- | --- | --- | --- |
| `bounded_delivery` | Produce one bounded artifact, blocker, or state delta | Usually no interruption | Once after validation + writeback |
| `user_gate` | Do not run the path covered by the Gate | Answer, reject, defer, or redirect | No spend |
| `scoped_user_gate_fallback` | Run only the selected fallback that does not depend on the Gate | Gate remains visible | Once after fallback validation |
| `external_evidence_observation` | Read a bounded handle/readback; do not invent delivery | Supply a missing handle only when needed | Spend possible only after material transition |
| `monitor_quiet_skip` | Stay quiet when not due or no material change | No interruption | No spend |
| `agent_scope_wait` | No in-scope candidate for the current peer; wait for reassignment | Usually no action | No spend |
| `autonomous_replan` | Write Todo, Vision, acceptance, or no-follow-up delta | Interrupt only for owner-held decisions | After an accountable delta |
| `outcome_floor_recovery` | Recover missing outcome evidence only, or write a blocker | Depends on blocker owner | After validated recovery |
| `blocked_health` / repair | Repair registry, projection, or boundary first | Intervene only when owner authority is needed | No valid delta, no spend |

Specific modes will evolve with the protocol. What the book preserves is the reasoning method: who owns
the next transition, which behavior is allowed, and what evidence permits writeback — not a permanently
unchanging list of enum values.

## Decision pipeline: eliminate illegal paths before choosing the frontier

Quota decision-making is not about letting multiple rules each return a boolean and letting the last
assignment win. It compiles source facts into one interaction contract in dependency order. External
developers do not need to memorize implementation functions, but they must understand the nine stages:

1. **Identity:** resolve the exact Goal and registered Agent; fail closed when identity is ambiguous;
2. **Goal boundary:** establish repository, write scope, authority source, spawn policy, and the
   public/private boundary;
3. **User Gate:** normalize blocking scope, decision scope, the concrete question, and projection gaps;
4. **Outcome / repair obligation:** inspect repeated surface-only progress, Vision, or acceptance gaps
   to decide whether replan or self-repair must run;
5. **Capability:** retain only candidates the current execution surface can actually perform;
6. **Workspace:** check the task repository, worktree, branch, and required write scopes;
7. **Frontier:** resolve priority, claim/lease, dependency, successor, monitor, and terminal
   closure;
8. **Interaction contract:** compose the result into the user, Agent, and CLI channels;
9. **Scheduler hint:** derive the next wake, backoff, and ACK from the resolved lifecycle state.

The order itself is a safety contract. For example, selecting a Todo before checking the workspace
would let a Host start writing before discovering that "the current directory is wrong"; treating any
open user item as a global block would starve safe work that does not depend on that decision. A more
reliable reading order is:

```text
identity
  -> authority and boundary
  -> scoped decision
  -> repair obligation
  -> capability and workspace eligibility
  -> frontier and continuation
  -> interaction contract
  -> scheduler
```

### Three combined cases

**Scoped Gate with independent work.** When a P0 is blocked by a scoped Gate and an independent P1
exists, keep the Gate in the user channel and execute only the explicitly selected P1 in the Agent
channel. Do not simplify into "a User Todo exists, so stop the entire Goal."

**Monitor not yet due.** When no advancement work exists and a Monitor is not yet due, the correct
result is quiet wait/backoff: do not poll, do not spend, and do not stop automation. `should_run=false`
does not mean the Goal is terminal.

**Monitor, Gate, and Replan changing together.** When a due Monitor produces a new Gate while
autonomous replan is also due, first write the compact observation; then place the Gate in the user
channel and let replan form a machine-visible frontier delta; finally recompute scheduler identity. Do
not remain quiet on the old cadence merely because the Monitor finished this poll.

These cases show that rules compose rather than overwrite one another. A Gate constrains authority, a
Monitor says when to observe, and Replan revises the frontier. Only the final interaction contract
defines this turn's behavior.

For the complete decision table, nine combined cases, source seams, and smokes, use
[Control-Plane Course Lesson 4](/loopx/docs/development/control-plane-course/04-quota-decision-kernel/).
Host, heartbeat, stateful backoff, and scheduler receipt implementation details are in
[Lesson 5](/loopx/docs/development/control-plane-course/05-host-scheduler-and-heartbeat/).

### Quota is a decision compiler, not a balance check

The intuition of "how much quota is left" is subtraction-driven thinking: deduct one on each run, stop
when exhausted. But a single turn of legitimate work may not need to spend (monitor poll, dry-run,
preflight), and a single spend does not equal effective delivery (artifact without validation).
Treating quota as a balance check causes the system to fail in these scenarios:

- **PR checks pending:** do not invoke the model just because the goal is still active. You must first
  wait for external results, then decide the next step.
- **Repeated dry-run or preflight failures:** no spend has occurred, but the system should not retry
  indefinitely. Repeated failures need repair or replan, not continued "attempts."
- **Monitor not yet due:** do not poll early just because "there is still quota," wasting external
  resources.

The correct model for quota is compiling source facts into an interaction contract according to stable
precedence. It decides "whether delivery is allowed this turn, what behavior is allowed, and how many
spends are permitted," not "balance > 0, so start." Five key source facts and their decision
implications:

| Source Fact | Decision implication |
| --- | --- |
| Whether the Goal is registered and the Agent is recognized | Fail closed when identity is ambiguous; consume no resources |
| Whether a User Gate blocks the current scope | Blocked paths do not execute; unblocked fallbacks can run independently |
| Whether the frontier has a claimable Todo | Enter monitor/agent-scope wait when no runnable candidate exists; consume no agent resources |
| Whether consecutive deliveries lack outcome | After multiple surface-only rounds, demand real outcome or self-repair; do not deliver indefinitely |
| Whether external evidence is fresh | Stale evidence cannot enter the current decision; must refresh readback first |

Prohibited shortcuts include: skipping the Gate because "the goal is active," skipping the workspace
check because "there was quota before," and skipping validation because "the user has not complained."
These all treat a local signal as global authorization.

For the complete decision table, nine combined cases, and rule precedence, see
[Control-Plane Course Lesson 4](/loopx/docs/development/control-plane-course/04-quota-decision-kernel/).

## The five-stage bounded-delivery loop

One normal delivery turn has at least five stages:

```text
Decide
  -> Act
  -> Validate
  -> Write back
  -> Account
```

### 1. Decide

Read the current decision and select the Todo corresponding to `agent_channel.primary_action`. Do not
override the current contract with an old prompt, an old dashboard card, or the previous
`recommended_action`.

### 2. Act

Complete one recoverable bounded segment. Bounded does not mean "change only one line." It means the
segment:

- has an explicit input and boundary;
- produces a coherent artifact, observation, or blocker;
- can be independently validated;
- can lead to a next Todo, wait condition, or no-follow-up.

Reading only one file, repeating "still analyzing," or running unrelated commands is not delivery.

### 3. Validate

Validation must check the real postcondition, not trust the executor's self-report:

- code: focused test, contract test, smoke, or build;
- documentation: build, links, command surface, and public-boundary scan;
- external effect: remote readback, revision, or service state;
- blocker: concrete evidence of the missing dependency, permission, or observable handle.

`process exited 0` may only prove that a tool started successfully. It does not automatically prove the
target behavior, external state, or acceptance.

### 4. Write back

After validation, write compact truth back through Todo lifecycle, event, evidence, or `refresh-state`
paths. Writeback should at least identify:

- what was delivered;
- based on what revision / command / readback;
- which acceptance or blocker was advanced;
- next step, successor, replan, or no-follow-up;
- whether per-Agent Vision changed.

Raw transcripts and large log tails should not enter public-safe state.

### 5. Account

Only after validated writeback already exists, record one quota spend according to the CLI channel.
Gate notification, dry-run, failed preflight, unchanged monitor poll, scheduler cadence change, and
duplicate writeback must not masquerade as delivery spend.

The order must not be reversed:

```text
wrong: act -> spend -> later decide whether it worked
right: act -> independent validation -> durable writeback -> spend once
```

### Delivery failure modes

The five-stage loop is a continuous dependency chain. Missing any layer produces a different failure,
not "the loop is still running":

| Missing layer | Visible symptom | Consequence |
| --- | --- | --- |
| Missing Validation | Artifact exists but no postcondition check | Defective delivery enters writeback; subsequent decisions are based on wrong evidence |
| Missing Writeback | Artifact was produced but Todo is still open | The next peer cannot see completion; duplicates work or selects the wrong frontier |
| Missing Refresh | Todo was updated but status/vision is still stale | Quota selects the wrong target; monitor judges by expired conditions |
| Missing Spend | Delivery was written back but no quota record exists | Quota accounting and delivery causality are inconsistent |

Missing Validation is the most dangerous because it treats internal confidence as external fact. Missing
Writeback is the most common because agents skip the loop after "finishing work," keeping only local
artifacts or chat records. Missing Refresh is the most subtle: on the surface the state looks correct,
but quota and monitor are actually reading a decision from before the state was refreshed.

For complete experiments on this evidence ladder, see
[Control-Plane Course Lesson 6](/loopx/docs/development/control-plane-course/06-evidence-refresh-and-self-repair/),
which includes failure replay and repair paths for each layer.

## Evidence, Receipt, and Observation

Three concepts carry different responsibilities within a single turn:

| Object | What it proves | What it does not prove |
| --- | --- | --- |
| Observation | What was seen at one moment | That a conclusion was accepted or remains fresh |
| Evidence | Which material supports a judgment | That the state transition was actually written |
| Receipt | That an action/transition was accepted with bound input and revision | That the external world stays unchanged forever |

For example, after a `git push` timeout:

- the tool invocation is an attempt;
- the result of `git ls-remote` is a readback observation;
- a remote ref matching the expected commit can become evidence;
- LoopX recording the publication transition forms the durable receipt.

A proposal is not an effect either. A protocol declaration that "publication is recommended" does not
automatically grant credentials, authorize the action, or prove that the remote has changed.

## TurnEnvelope and LoopX Turn

A full quota decision can contain substantial diagnostic information. The optional
[`loopx_turn_envelope_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/turn-envelope-v0.md)
compresses an already computed decision into a bounded read model that preserves:

- selected Todo and effective action;
- Gate, required reads, and goal boundary;
- capability/workspace guard;
- validation, writeback, and spend policy;
- scheduler action;
- a compact contract capsule.

TurnEnvelope is a projection. It does not select different work or change quota semantics.

[`LoopX Turn`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/loopx-turn-v0.md)
further defines an optional governed transaction:

```text
live decision
  -> typed host request
  -> Agent/Host candidate result
  -> independent validator
  -> durable writeback
  -> one spend
```

Codex App heartbeat, a visible Codex CLI Goal, and another Host do not need to use the same adapter
implementation, but they should maintain the same control semantics: the Host is responsible for
execution and wake-up, the LoopX decision is responsible for the legal next action, and the validator
does not directly trust a Host completion claim.

!!! info "Current maturity"
    TurnEnvelope is currently an explicitly enabled bounded projection, not the default quota output.
    LoopX Turn is an experimental protocol and implementation target. They are suitable for contributors
    to understand boundaries and build integration experiments, but should not be described as a stable
    runtime already uniformly adopted by every Host.

## Monitor and Scheduler Hint

When the frontier depends only on an external condition, create a `continuous_monitor` instead of
repeatedly asking the Agent "has anything changed." A monitor needs at least:

- a stable target key;
- cadence and next due time;
- a bounded observation handle;
- a material-change rule;
- expiry or termination conditions;
- a no-change accounting policy.

`scheduler_hint` projects current state into Host cadence: run now, wait for fresh evidence, wait for
reassignment, or wake at monitor cadence. It is not execution permission:

```text
scheduler hint: when to wake
interaction contract: what this turn may do
```

Even if the Host wakes at the correct time, it must re-run the current decision. An old scheduler
proposal, old `should_run`, or old selected Todo cannot be reused across state changes by default.

### Scheduler convergence requires apply, readback, and ACK

For a Codex App heartbeat, `recommended_rrule` is the target cadence, not proof that the Host applied
it. The complete convergence chain is:

```text
LoopX proposes recommended_rrule
  -> Host applies one automation update
  -> Host result / observed RRULE proves the actual cadence
  -> run the exact ack_hint.cli_args
  -> LoopX records reset token, identity, and applied RRULE
```

The important protocol branches are:

- `apply_needed=true`: the Host attempts at most one update; after success it runs the complete
  `ack_hint.cli_args` from the packet; after failure or timeout it does not ACK and runs
  `failure_hint.cli_args` once;
- `apply_needed=false, ack_needed=true`: the Host readback already exactly matches the proposal, so
  skip the no-op update and execute the bound ACK directly;
- `host_observation.status=drift_detected`: the actual cadence does not match the ledger; an old ACK
  cannot override the current readback; repair is needed;
- terminal pause/stop: verify the stop result according to the Host contract; do not disguise it as a
  normal RRULE ACK.

The current ACK uses `quota scheduler-ack-current` to re-read the latest hint. The Host must execute
the complete argv from the packet, because it may bind registry, runtime profile, Agent identity, and
capability envelope; manually copying only the reset token or dropping global arguments will write the
ACK to the wrong state.

Scheduler state also binds a `reset_token` and `identity_signature`. User feedback, a new Todo,
reassignment, Gate resolution, or material evidence transition changes the identity and restores the
cadence to the current profile's initial value; only consecutive unchanged polls continue backoff.
Cadence apply, failure writeback, and ACK are control-plane housekeeping and do not consume delivery
quota.

### Per-lane counting when multiple monitors are interleaved

When two monitors M1 and M2 alternate polling, if you only count "whether consecutive runs are
unchanged," M1's run will break M2's no-change streak, and M2 will break M1's. In the end, both
monitors' `consecutive_no_change` never reaches the threshold, the system cannot enter backoff, and it
turns into hot polling instead.

The correct approach is to **maintain an independent `consecutive_no_change` counter for each monitor
todo**. When M2 has a material change, only M2 is reset; M1 is unaffected. The turn order (A1, B1, A2,
B2...) does not cause mutual zeroing.

This per-lane design also applies to multi-agent scenarios: each agent's monitor is an independent
lane; they share the same frontier read model, but no-change judgment is per-lane. Implementation
details and interleaving experiments are in
[Control-Plane Course Lesson 6](/loopx/docs/development/control-plane-course/06-evidence-refresh-and-self-repair/).

## How a turn ends

A governed turn can end with different results:

- validated delivery + writeback + spend;
- a concrete blocker + recovery condition;
- a user Gate notification;
- one bounded external observation;
- quiet monitor / no-candidate wait;
- a replan / repair delta;
- stop after terminal audit.

"No code was written" is not necessarily failure; a Gate, wait, or quiet no-op may be exactly the
legal result required by the protocol. Conversely, writing a lot of code does not mean the turn was
valid, if it bypassed the selected Todo, authority, workspace, or validation.

The next chapter explains recovery across Turns, self-repair, and terminal closure, and places the
operational responsibilities of Agent, Capability, Provider, Extension, and external systems back
within the same fact boundary.