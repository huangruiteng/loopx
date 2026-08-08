# Agent sessions, Codex Goal, and LoopX

These are not mutually exclusive products. They own different layers of state and responsibility. The
right choice depends on how much control information must survive outside the current session.

## What you should learn

After this chapter, you should be able to:

- explain which state a normal session, Codex Goal, and LoopX each own;
- describe five observable contracts that LoopX adds beyond a Host goal;
- keep Goal, Agent, and Host identity decisions separate;
- use a Task qualification card before introducing a long-running control plane;
- select a start path from the actual Host wake-up and writeback surface;
- recognize when Codex Goal is sufficient;
- combine Codex Goal and LoopX without creating competing state machines.

## Three layers of state

| Layer | State it primarily owns | Problem it primarily solves |
| --- | --- | --- |
| Normal agent session | Current transcript, tool results, and turn plan | Reason and execute inside one context |
| Codex Goal | Host or thread objective and Goal lifecycle | Continue turns around one goal and expose active, blocked, or complete |
| LoopX | Project-owned Goal, Todo, Gate, Evidence, Quota, and recovery state | Coordinate an auditable lifecycle across sessions, agents, Hosts, and external systems |

LoopX does not duplicate model execution. Codex Goal owns continuation around an objective on one Host.
LoopX compiles project state into the bounded work that is legal for the next turn.

## Four actors

Separate four responsibilities before calling every component an “agent”:

| Actor | Primarily owns | Must not own |
| --- | --- | --- |
| User / operator | Direction and decisions over private material, credentials, production, and public claims | Manual scheduling for every ordinary Todo |
| Host | Sessions, model turns, visible TUI, heartbeat, and wake-up surfaces | Project-long facts or a second custom state machine |
| Executor / Agent | Current-turn reasoning, tool calls, bounded delivery, and validation | Implicit long-term memory or unauthorized approval |
| LoopX control plane | Goal, Todo, Gate, quota, evidence lineage, and recovery protocol | Model reasoning or authoritative Git/CI facts |

Dashboards, review packets, and prompts are projection or interaction surfaces. They are not a fifth
authority.

## Keep three identities separate

LoopX coordinates Goals, Agents, and Hosts, but each identity answers a different question:

| Identity | Question it answers | Stability and selection rule |
| --- | --- | --- |
| `goal_id` | Which long-running project boundary are we advancing? | Binds registry state, Todos, Gates, and evidence lineage; reuse requires the exact existing id |
| `agent_id` | Which peer or work lane owns the current responsibility? | Binds claims, Vision, quota, and writeback; new onboarding defaults to a fresh identity |
| `host_surface` / runtime profile | Which product surface executes and wakes this turn? | Binds App heartbeat, a visible Goal, or another Host loop; declare the surface that is actually running |

Reusing a Goal does not imply that a new session should take over an existing Agent identity. The current
Goal-start contract keeps those choices explicit:

1. if several registered Goals exist, return a read-only `goal_selection_gate` and rerun with one exact
   `--goal-id`;
2. do not infer a Goal from similar objective text, a chat summary, or a directory name;
3. a new argument-bearing `start-goal --guided` without `--agent-id` enters fresh identity registration,
   even when zero or one Agent is already registered;
4. continue an existing Agent only when the user explicitly selects that exact `agent_id`;
5. an Agent name or prefix does not prove the Host surface; runtime metadata does.

This lets a session continue the same project without silently impersonating the previous executor.

## Task qualification card: decide whether LoopX earns its cost

LoopX is not synonymous with “use it whenever the task is large.” Write a reviewable qualification card
first:

This card is an editorial decision aid from this book. It is not a LoopX CLI schema, and `start-goal` does
not persist it automatically. The current Goal, Todo, Gate, acceptance, and boundary protocols remain
authoritative.

| Field | Question | Default when missing |
| --- | --- | --- |
| `duration` | Will work cross sessions, waiting windows, or workdays? | Normal session |
| `external_wait` | Will it wait for CI, review, approval, or an external resource? | Normal session or Host Goal |
| `handoff` | Will Agent, Host, device, or owner change? | One Host Goal |
| `authority` | Does it involve private reads, credentials, production, or external writes? | Define the Gate before automation |
| `acceptance` | Which observable evidence proves completion? | Define acceptance before “continuous improvement” |
| `baseline` | What stays matched against a normal session or Host Goal? | Make no uplift claim |
| `stop_condition` | When does work complete, block, downgrade, or stop? | Define the terminal contract first |

One positive field is not enough. LoopX usually earns its cost when work crosses sessions, includes an
external wait or handoff, has independent acceptance, and needs authority, evidence, and recovery outside
the transcript.

### Compare a session, Goal, and LoopX fairly

To evaluate real task outcomes, do not compare different tasks or budgets. Match at least:

```text
same task semantics
same runner / model / reasoning settings
same verifier contract
same time and cost budget
```

Record completion, independent verifier result, erroneous writes, human intervention, stop-policy
correctness, wall time, and cost. Without a matched baseline or independent verifier, report experience;
do not claim product uplift.

[`release_outcome_baseline_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/release-outcome-baseline-v0.md)
sets a narrower release-qualification contract: it compares a stable LoopX release with a candidate
revision. It explicitly does not treat native-Agent-versus-LoopX treatment studies as release-promotion
evidence. Those studies can inform product research only when their arm semantics are stated separately.

## Compare them on one task

Use the same task in all three cases: add compatible JSON output to a CLI.

### Normal session

You tell an agent:

> Add `--format json`, preserve the default output, and add tests.

The agent can read, edit, and test. If the session ends while CI is running, recovery usually depends on
the Git diff, CI, and a human restating context. The rationale for the schema, the pending maintainer
decision, an expected failure, or an unperformed external action may exist only in chat.

### Codex Goal

Codex Goal separates the objective and Goal lifecycle from one prompt. The Host can start later turns
around the same objective and react differently when the Goal is active, blocked, or complete.

The user no longer needs to paste the complete objective after CI finishes. Codex Goal solves **goal
continuity inside the Host**. It does not have to become a project Todo graph, authority ledger, or
cross-Host registry.

!!! warning "Verify the current Host surface"
    Writing `/goal` in ordinary prose does not prove that a persistent Host Goal exists. Use the current
    Codex surface to create, inspect, block, resume, and complete it.

### LoopX

LoopX can retain a more specific project contract:

```text
Goal: ship-compatible-json-output
├── Todo A: implement formatter              done
├── Todo B: add schema tests                 done
├── Todo C: obtain field-name decision       blocked by Gate G
└── Todo D: release                          deferred until C

Gate G
├── scope: response.error_code
├── authority: maintainer
└── blocks: Todo C
```

The next turn can determine:

- which Todo is runnable;
- which lane the Gate blocks;
- which agent holds the claim or lease;
- which test result is valid evidence;
- whether release needs an external-effect receipt;
- whether the Host should run, wait, or monitor.

## Five project contracts LoopX adds

### 1. Todo, claim, and handoff

A Goal expresses the project outcome. A Todo is a schedulable work identity with priority, dependencies,
claim, lease, successor, and handoff information. Per-Agent Vision stores one peer's bounded role
direction, acceptance summary, and replan trigger. It is not another Goal or a global product vision.

This separates “the Goal is active” from “who may perform which work now.” An agent id labels a LoopX work
lane; it does not prove which Host is currently executing it. A new session may reuse the Goal history and
frontier while registering a fresh Agent identity. Existing claims move only through an explicit takeover
or handoff.

### 2. Gate and authority

A chat can ask a human a question, but the project still needs to know whether that question blocks one
Todo, every lane, or no delivery at all.

LoopX distinguishes:

- `user_gate`: relevant work cannot legally continue without a decision;
- `user_action`: a person should act, but other agent work may continue;
- safe fallback: work that does not depend on the missing decision.

A useful Gate binds decision scope, authority, and blocked work.

### 3. Evidence and receipt

“The agent invoked a command” is not proof that a transition happened. LoopX distinguishes:

- proposal: what should happen;
- observation: what was seen;
- validated evidence: checked material that supports a conclusion;
- effect readback: current fact returned by the external system;
- receipt: durable record of an accepted action or transition.

If `git push` times out, the tool invocation alone cannot mark publication complete. The workflow needs
remote readback or equivalent evidence.

### 4. Scheduler, monitor, and quota

Codex Goal lets the Host continue. LoopX adds a project decision about whether continuation is useful now:

- `quota should-run`: whether state and budget allow this turn;
- monitor: wait quietly when an external condition has not changed;
- scheduler hint: when a Host should wake again;
- backoff: avoid repeated no-change turns;
- spend: record budget only after bounded validated progress is written back.

The Host still owns the actual scheduler. LoopX emits the scheduling contract.

### 5. Cross-agent, cross-Host recovery

The canonical state belongs to the project. Codex App, Codex CLI, and other supported Hosts can read the
same Goal boundary:

```text
Codex App heartbeat ─┐
Codex CLI Goal ──────┼──> LoopX project state ──> current turn packet
Other Host hook ─────┘
```

Recovery uses events, lineage, projections, a fresh environment read, and replanning instead of requiring
the new Host to inherit the old transcript. The next chapter separates those state surfaces before the
book moves into work graphs and governed Turns.

## Host compatibility matrix

LoopX preserves one control-plane contract, but Hosts do not share one wake-up implementation. The current
public
[Runtime Connector Catalog](https://github.com/huangruiteng/loopx/blob/main/docs/integrations/runtime-connector-catalog.md)
defines these main paths:

| Host surface | Driver | Key limit |
| --- | --- | --- |
| Codex App | `$loopx <task>` plus App heartbeat | Cadence needs RRULE apply/readback/ACK |
| Codex App over SSH | Visible `/goal` | Does not depend on App automation tools |
| Codex CLI TUI | Generated bootstrap plus visible `/goal` | Stays visible and interruptible |
| Claude Code | `/loopx` plus opt-in native `/loop` adapter | Uses the same quota and writeback |
| OpenCode | `/loopx` plus opt-in Goal bridge | Bridge activation follows Todo writeback |
| Shell / other Agent | Guided packet plus caller-owned runner | Caller owns wake-up without a runner hook |

Catalog presence does not mean every Host exposes the same automation API. When `host_surface` is unknown,
omit it once and follow the read-only selection Gate. Do not guess that a CLI, IDE plugin, App SSH
workspace, or ordinary shell is a Codex App heartbeat.

## How Codex Goal and LoopX compose

A typical composition is:

1. LoopX selects a Todo and checks Gates, capability, write scope, and quota.
2. LoopX produces a bounded task body or decision packet.
3. Codex Goal carries continuation on this Host.
4. The agent delivers and validates one work segment.
5. The result is written back to LoopX, which decides the next turn.

```text
LoopX control plane -> Codex Goal continuation -> Agent turn
        ^                                      |
        `---------- validated writeback -------'
```

Codex Goal is the Host lifecycle. LoopX is the project lifecycle. They should compose, not compete.

## Choose the smallest sufficient layer

| Task characteristics | Recommended starting point |
| --- | --- |
| One-shot, bounded, and cheap to redo | Normal session |
| Persistent objective and recovery on one Host | Codex Goal |
| Project Todo, authority Gate, external effect, cross-agent or cross-Host recovery | LoopX, optionally combined with Codex Goal |

A control plane has maintenance cost. Do not create project state merely to make a simple task look more
agentic.
