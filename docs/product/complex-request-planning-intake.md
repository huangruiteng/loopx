# Complex Request Planning Intake

This note defines a bounded intake pattern for large user requests. It keeps a
strategy-heavy conversation from becoming invisible chat history by converting
it into a small, typed LoopX plan that agents can inspect, claim, and verify.

The pattern is intentionally conservative. It is not a delivery shortcut, a
domain expert, or a permission grant. It is a planning intake that turns messy
context into control-plane objects while preserving authority, scope, and
public/private boundaries.

## When To Use It

Use `complex_request_intake_v0` when a user gives an input that mixes several
of these signals:

- product strategy, roadmap, partner ideas, benchmark direction, or launch
  planning in one turn;
- multiple possible work lanes with unclear ownership;
- references to existing authority docs, active state, or prior decisions;
- a request to "think through the whole plan" before implementation;
- a heartbeat that finds important strategy only in chat, not in LoopX state.

Do not use it for a narrow bug fix, a single docs edit, a direct PR merge, or a
clear one-step user gate.

## Product Role

Complex intake sits between the intelligent management surface and normal LoopX
execution:

```text
large user signal
  -> complex_request_intake_v0
  -> small typed todo batch
  -> normal quota / claim / execution / evidence writeback
```

The intake gives the management surface something stable to show: themes,
candidate anchors, ownership decisions, and the next few proof slices. Normal
LoopX objects remain the source of truth for delivery.
For external trackers such as Lark Kanban, this is the task-spawning path: the
tracker shows status and claims, while intake creates the typed todo batch that
later syncs back to the tracker.

## Intake Steps

1. **Read authority first.** Inspect the registry-declared active state,
   status/quota output, registered docs, current todos, and any explicitly
   named public design notes before inventing work.
2. **Synthesize themes.** Reduce the request to a few themes such as product
   proof, onboarding, benchmark evidence, management surface, partner anchors,
   or repository safety.
3. **Create a small todo batch.** Add only the minimum viable set of typed
   todos, usually three to seven. Each todo should have priority, role,
   `task_class`, `action_kind`, acceptance evidence, and a stop condition.
4. **Claim narrowly.** The current agent may claim only the items that match
   its advisory profile and current scope. Other-peer work stays with its
   claimant; use explicit claim transfer or `review_handoff` when task policy
   requires a different peer.
5. **Keep private thinking local.** If raw strategy, names, screenshots, or
   sensitive context are needed, write a local/private management note and
   reference only a safe summary in public docs or active state.
6. **Refresh the next action.** After writeback, refresh LoopX state so quota,
   status, and the management surface can see the chosen next proof slice.

## Output Contract

The intake result should be compact enough to review in a status card:

```yaml
complex_request_intake_v0:
  source_refs:
    - active_state
    - registered_docs
    - user_message_summary
  theme_summary:
    - name: management_surface
      intent: make long-running agent work reviewable
    - name: proof_anchor
      intent: select high-value public evidence before broad execution
  todo_batch:
    - todo_id: todo_example
      priority: P1
      role: agent
      task_class: advancement_task
      action_kind: public_contract_design
      acceptance: "Public doc linked from product index and passes boundary scan."
      stop_condition: "Stop before runtime write paths or private material."
  claim_decisions:
    - todo_id: todo_example
      claimed_by: codex-side-bypass
      reason: "Matches productization/docs lane."
  private_note_ref: "local-only, optional"
  writeback:
    status: planned
    recommended_action: "Work the first claimed proof slice."
```

The concrete schema can evolve, but the fields above capture the minimum
reviewable shape: where the context came from, what it means, which todos were
created, who may work on them, and what evidence will prove progress.

## Boundaries

- The intake does not execute the plan. It only prepares bounded work.
- The intake does not override user gates, repo safety rules, worktree policy,
  quota, or claim ownership.
- The LoopX core should not do fragile natural-language scope filtering. Agents
  use their known scope and encode the outcome as explicit todo metadata.
- A completed non-trivial todo does not need a forced successor. It needs either
  a clear next todo when one is real, or a short no-follow-up rationale.
- Monitor-only loops should not run forever without producing either evidence,
  a blocker, a planning intake, or a quiet no-op rationale.
- Private context can inform local planning, but public docs and committed
  state must contain only safe summaries.

## Management Surface Implications

The management surface should render complex intake as a first-class review
card:

- themes extracted from the request;
- proposed todo batch with priority, role, and claim status;
- current-agent claim decisions versus explicit review handoffs;
- evidence expected for the first proof slice;
- unresolved user gates, if any;
- a link to any local-only management note without exposing its contents.

This lets a maintainer review the plan before agents spend many turns. It also
supports the "brush through work" interaction: accept a slice, reject an
off-scope item, ask for evidence, or promote one theme into an anchor.

## Acceptance Criteria

A good intake is successful when:

- the large request is no longer only in chat;
- the resulting todos are visible through LoopX status/quota projection;
- only current-scope work is claimed by the current agent;
- primary or user decisions are concrete, not hidden behind a generic owner
  gate;
- public artifacts pass private-boundary scans;
- the next heartbeat has a specific proof slice or a quiet no-op rationale.

The goal is to make complex strategy manageable without turning LoopX into a
free-form planning monolith.
