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

The first real target user is the maintainer/operator of Loop Agents. That
person is not only asking "what did the agent do?" They are asking:

- what external signals deserve attention;
- which signals should become high-value anchors;
- which agent lane owns the next step;
- whether the agent is becoming more useful or merely busier;
- where human judgment should change the loop.

## Adoption Modes

The status surface should support two adoption modes.

### Read-Only Review Mode

In read-only mode, the user can connect existing agent work without adopting
the LoopX control loop. The surface ingests public or consented artifacts such
as issues, pull requests, documents, run summaries, compact logs, or manually
entered feedback. It then shows a reviewable summary and captures human scores.

This mode should not mutate the agent's plan. Its product value is measurement:
the maintainer can see whether the agent created useful work, respected
boundaries, consumed attention responsibly, and improved over time.

### LoopX Writeback Mode

In writeback mode, the same feedback becomes control-plane input. Scores and
comments can turn into gates, todo changes, selected anchors, reward notes,
scope corrections, or next improvement targets. The important contract is that
the display surface does not silently convert taste or fuzzy feedback into
hard policy. It must show what will be written back and why.

This two-step adoption path keeps the product easy to try while preserving the
larger LoopX promise: review first, then controlled improvement.

## Agent Work Feed

The default interaction should feel like reviewing a feed of agent work cards,
not like operating a backend console. A user should be able to "swipe through"
recent outputs and give low-friction feedback while still keeping every card
auditable.

A work card represents a reviewed output, not a raw todo:

- `Output`: what the agent produced.
- `Why now`: why this deserves attention instead of staying in history.
- `Evidence`: artifact, validation, source boundary, or blocker.
- `Cost`: token/quota cost and user-attention cost when available.
- `Next proposal`: continue, stop, validate, promote, or ask.
- `Feedback`: structured buttons that write to review state.

The feed should prioritize management value:

- unresolved human gates;
- high-value but uncertain outputs;
- expensive repeated work patterns;
- evidence gaps before promotion;
- cards that may become anchors, showcases, or public-safe examples.

The feed must stay inspectable. A card can be lightweight on the first screen,
but the user should be able to open the evidence, PR, run summary, boundary
note, or review history behind it. Otherwise the surface becomes attractive
but untrustworthy.

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
5. **Review performance, not just status.** A Loop Agent should show where it
   created value, where it lost points, what feedback changed, and what it
   should improve next.
6. **Make feedback cheap but structured.** The user should be able to dismiss,
   approve, correct, promote, or gate a work card without reading a long run
   report first.
7. **Prefer one next action.** The first screen can link to a backlog, but it
   should name the next concrete thing that will happen or the exact question
   that needs a human answer.

## Card Set

### Work Feed

Purpose: let the user quickly review recent agent outputs and turn fuzzy
judgment into structured feedback.

Suggested fields:

- `Card type`: progress, blocker, proposal, evidence, anchor candidate,
  showcase candidate, or boundary warning.
- `Summary`: one or two sentences of what the agent produced.
- `Proof`: compact evidence and validation state.
- `Cost`: token/quota cost, elapsed time, and attention cost where known.
- `Suggested action`: continue, validate, promote, defer, stop, or ask.
- `Feedback actions`: useful, not useful, wrong direction, evidence missing,
  promote to anchor, private/risky.

The feed is the primary review surface. Other cards can appear as card details
or filters, but the first screen should help the user clear the highest-value
review items quickly.

### Goal Snapshot

Purpose: remind the user what the long-running goal is and why the current
work matters.

Suggested fields:

- `Goal`: one sentence from the registry or active state.
- `Mode`: delivery, safe side path, planning proposal, waiting on user, or
  paused.
- `Owner`: registered peer or user.
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

### Signal Inbox

Purpose: show which outside signals entered the loop and whether any are worth
turning into work.

Suggested fields:

- `Signal`: issue, PR, review comment, failing check, chat feedback, doc
  change, benchmark result, or user note.
- `Source`: public artifact, private source, connector, or manual entry.
- `Fit`: ignore, monitor, candidate anchor, ask owner, or create todo.
- `Boundary`: public-safe, private, requires owner review, or not usable.

This card is quiet by default. It should avoid turning every signal into work.
The maintainer should see the few signals that might change priorities.

### Anchor Selection

Purpose: identify the small number of high-value anchors worth driving.

Suggested fields:

- `Anchor`: public issue, PR, failing check, stale review, user request,
  showcase candidate, or internal management question.
- `Why this matters`: credible pain, repeated workflow, public evidence, or
  strategic value.
- `Allowed action`: observe, route owner, diagnose, open PR, write proposal, or
  ask human.
- `Owner split`: LoopX maintainer, collaborator, repo maintainer, or adapter.
- `Exit`: accepted, rejected, merged, blocked, unsafe, or showcase candidate.

For open-source issue / PR pilots, this card is the bridge between growth and
control. LoopX does not need to implement every solver; it needs to choose
anchors well and keep the evidence reviewable.

### Current Work

Purpose: show what the active agent is actually doing now.

Suggested fields:

- `Todo`: the selected todo title, shortened.
- `Claim`: claimed agent and role.
- `Scope`: human-readable lane, such as benchmark, productization docs,
  runtime contract, or showcase.
- `Stop condition`: the condition that makes the agent stop and ask.

For repository-writing tasks, this card should also show the selected workspace
policy, whether repository policy permits self-merge, and whether an explicit
peer review handoff exists.

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

### Performance Review

Purpose: help the maintainer judge whether the Loop Agent is improving.

Suggested fields:

- `Value`: what useful artifact or decision was created.
- `Quality`: accepted, corrected, rejected, blocked, or needs review.
- `Control`: whether gates, scope, and boundaries were respected.
- `Cost`: quota or attention spent relative to value.
- `Learning`: what should change next time.

This is the main way fuzzy human feedback becomes durable without pretending it
is a benchmark score. The review can stay lightweight, but it must be tied to
evidence and a next improvement target.

### Project-Level Reward

Single-task benchmarks can measure whether an agent solved one task. They do
not fully measure whether a long-running agent created useful value across a
complex project. The management surface should therefore expose a
project-level reward model:

```text
reward = f(quantity, quality, token cost, user attention cost)
```

The fields have different sources:

- `Quantity`: completed tasks, accepted anchors, merged PRs, resolved
  blockers, or other countable outputs.
- `Quality`: human review, maintainer score, accepted/rejected outcomes,
  correction rate, and evidence quality.
- `Token cost`: run and quota accounting.
- `User attention cost`: user gates, review requests, clarification turns,
  approval steps, and manual interventions.

This is where the intelligent display surface becomes more than a dashboard:
it supplies the missing quality signal. A user can first connect existing
agent work in read-only mode, score the work, and see whether the agent is
creating value. After LoopX writeback is enabled, the same score can adjust
gates, todos, anchors, reward notes, and next improvement targets.

## State Mapping

The first screen should be generated from existing LoopX projections
before adding new UI state.

| Product card | Source fields |
| --- | --- |
| Goal Snapshot | registry goal, active state objective, latest status classification |
| Since Last Check | run history, refresh-state delivery outcome, validation evidence |
| Signal Inbox | connector events, user feedback, issue/PR metadata, doc changes |
| Anchor Selection | planning queue proposals, promoted todos, future anchor packets |
| Current Work | agent todos, `claimed_by`, advisory `agent_profile_v1`, future leases |
| Blocker Or Gate | user todos, operator gate, interaction contract, goal boundary |
| Next Agent Move | quota decision, recommended action, next action, stop condition |
| What I Need From You | user todo summary and concrete operator question |
| Feedback Capture | reward overlay, gate command, todo update, future feedback signal |
| Performance Review | run evidence, reward overlays, outcome classification, cost summary |

Missing fields should degrade gracefully. For example, before hard leases exist,
show `claimed_by` as soft ownership and avoid claiming exclusive execution.
Without `agent_profile_v1`, show the registered peer id and current claims; do
not infer rank or authority from the identity name.

## Creator-Operator Example

For a non-technical creator-operator case, the cards could read:

```text
Goal Snapshot
Keep a weekly content research loop moving for a creator-operator.

Since Last Check
The agent found three synthetic trend clusters and drafted two angle options.
Evidence is demo data only; no real platform scrape is included.

Current Work
The selected peer is building the public-safe showcase storyboard.

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
- signal inbox and anchor selection can represent at least one public-safe
  issue/PR pilot without requiring a custom issue-fix UI;
- no-open-user-todo states render quietly without false urgency;
- peer ownership and explicit review handoff are visible without overriding quota
  or gate decisions;
- feedback buttons map to explicit control-plane effects;
- performance-review notes stay evidence-backed and distinguish value,
  quality, control, cost, and learning;
- private evidence, raw traces, credentials, and internal links cannot appear
  in the public card payload.

This model should become the bridge between the current CLI/status contracts
and future frontend or Lark first-contact surfaces.
