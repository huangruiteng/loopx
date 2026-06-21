# Non-Technical Operator Status Model

This note defines a first-screen status model for people who are operating a
long-running agent goal but do not want to inspect prompts, logs, CLI output,
or raw traces.

The model is intentionally product-facing. It translates LoopX state
into plain-language cards:

- what changed since the last check;
- what the agent is doing now;
- where progress is blocked;
- what the agent plans next;
- what the agent needs from the user;
- how user feedback changes the control plane.

The same model should work for engineering, benchmark, research, and
creator-operator cases. The copy can change by domain, but the control-plane
objects stay the same: goal, gate, todo, evidence, safe side path, run history,
quota, and feedback.

## Design Principles

1. **Start with user meaning, not runtime internals.** The first screen should
   say "waiting for your publishing decision" before it says
   `operator_gate`.
2. **Keep blocked and moving work separate.** A user gate can block one route
   while safe side work continues. The surface should show both facts.
3. **Make evidence inspectable without making it raw.** Show compact evidence,
   validation, and source boundaries; keep traces, credentials, private notes,
   raw benchmark logs, and private creative material out of the card.
4. **Treat feedback as a structured transition.** User feedback should become
   a gate decision, preference hint, todo change, or product-improvement note,
   not an untracked chat memory.
5. **Prefer one next action.** The first screen can link to a backlog, but it
   should name the next concrete thing that will happen or the exact question
   that needs a human answer.

## Card Set

### Goal Snapshot

Purpose: remind the user what the long-running goal is and why the current
work matters.

Suggested fields:

- `Goal`: one sentence from the registry or active state.
- `Mode`: delivery, safe side path, planning proposal, waiting on user, or
  paused.
- `Owner`: primary agent, side agent, or user.
- `Freshness`: latest meaningful update time and whether status is fresh.

Plain-language examples:

- "Keeping the benchmark evaluation lane moving while a user gate waits."
- "Preparing a creator-operator showcase with synthetic data only."
- "Waiting for your decision before publishing; safe documentation work is
  still moving."

### Since Last Check

Purpose: answer "what changed?" before the user has to read history.

Suggested fields:

- `Latest outcome`: delivered, partial progress, blocker recorded, no-op, or
  planning proposal.
- `Evidence`: compact validation or artifact summary.
- `Confidence`: high, medium, low, or blocked.
- `Boundary`: public-safe, private, requires approval, or internal-only.

This card should never claim outcome progress from a surface-only change. If a
turn only prepared a contract or doc, say that plainly and point to the next
outcome-bearing step.

### Current Work

Purpose: show what the active agent is actually doing now.

Suggested fields:

- `Todo`: the selected todo title, shortened.
- `Claim`: claimed agent and role.
- `Scope`: human-readable lane, such as benchmark, productization docs,
  runtime contract, or showcase.
- `Stop condition`: the condition that makes the agent stop and ask.

For side agents, this card should also show whether work is in an independent
worktree/branch and whether self-merge is allowed or a primary-agent review is
expected.

### Blocker Or Gate

Purpose: make human decisions visible without implying the agent is helpless.

Suggested fields:

- `Question`: the exact user or controller decision.
- `Blocked route`: the work that must wait.
- `Safe side path`: whether independent work may continue.
- `Repeat policy`: whether the user should be reminded until resolved.

Plain-language copy should separate "the gated route waits" from "the whole
goal is stopped." For example:

```text
Needs your decision before publishing the case write-up.
Safe side path: continue polishing the public docs and synthetic demo.
```

### Next Agent Move

Purpose: answer "what will happen if I do nothing?"

Suggested fields:

- `Next action`: one bounded action from quota/status.
- `Validation`: the smoke, check, review, or artifact expected after work.
- `Quota`: enough to say whether another automatic turn is allowed.
- `Fallback`: what happens if validation fails or a blocker appears.

For non-technical users, quota should not be shown as raw internal counters by
default. Use plain copy such as "another automatic turn is allowed" or
"waiting until the next scheduled check."

### What I Need From You

Purpose: convert user attention into a short, concrete action.

Suggested fields:

- `Decision`: approve, reject, defer, pick an option, provide missing context,
  or no action.
- `Why now`: what the answer unlocks.
- `Safe default`: what will continue if the user does not answer.
- `Deadline`: only when the project has a real deadline.

If no user todo is open, this card should say "No action needed" and be
visually quiet. It should not manufacture a question to keep the UI busy.

### Feedback Capture

Purpose: let the user steer without editing the control plane directly.

Feedback options should map to structured writebacks:

| User input | Control-plane effect |
| --- | --- |
| "Approve this route." | Gate decision with scope and evidence reference. |
| "Do not do this again." | Preference hint plus possible todo mutation. |
| "This was useful." | Run-bound reward with compact reason. |
| "The summary is unclear." | Product-improvement note or status-copy todo. |
| "Focus on another lane." | Replan proposal or priority/todo update. |
| "This contains private material." | Boundary correction and stop/escalation. |

The surface should avoid turning inferred taste into hard policy. Explicit
feedback can shape replanning, but private chat should not become public
evidence, and soft preferences should remain distinguishable from safety,
permission, or compliance gates.

## State Mapping

The first screen should be generated from existing LoopX projections
before adding new UI state.

| Product card | Source fields |
| --- | --- |
| Goal Snapshot | registry goal, active state objective, latest status classification |
| Since Last Check | run history, refresh-state delivery outcome, validation evidence |
| Current Work | agent todos, `claimed_by`, future `agent_profile_v0`, future leases |
| Blocker Or Gate | user todos, operator gate, interaction contract, goal boundary |
| Next Agent Move | quota decision, recommended action, next action, stop condition |
| What I Need From You | user todo summary and concrete operator question |
| Feedback Capture | reward overlay, gate command, todo update, future feedback signal |

Missing fields should degrade gracefully. For example, before hard leases exist,
show `claimed_by` as soft ownership and avoid claiming exclusive execution.
Before `agent_profile_v0`, show the registered agent id and role from the
coordination registry.

## Creator-Operator Example

For a non-technical creator-operator case, the cards could read:

```text
Goal Snapshot
Keep a weekly content research loop moving for a creator-operator.

Since Last Check
The agent found three synthetic trend clusters and drafted two angle options.
Evidence is demo data only; no real platform scrape is included.

Current Work
Side agent is building the public-safe showcase storyboard.

Blocker Or Gate
Publishing remains blocked until the user approves tone and source policy.
Safe side path: polish synthetic demo copy and feedback flow.

Next Agent Move
Generate the fake-data storyboard and validate that it contains no private
material or autopublish claim.

What I Need From You
No action needed right now.
```

This is the level of legibility the product should aim for: the user can see
the work, the boundary, the gate, and the safe continuation without reading
agent logs.

## Acceptance Criteria

The first implementation of this model is ready when:

- a public-safe status mock can render all cards from synthetic or existing
  compact LoopX projections;
- open user todos appear as concrete questions, not generic "owner gate" copy;
- no-open-user-todo states render quietly without false urgency;
- side-agent ownership and review handoff are visible without overriding quota
  or gate decisions;
- feedback buttons map to explicit control-plane effects;
- private evidence, raw traces, credentials, and internal links cannot appear
  in the public card payload.

This model should become the bridge between the current CLI/status contracts
and future frontend or Lark first-contact surfaces.
