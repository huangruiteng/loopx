# Public Launch Narrative Draft

This draft is the public, repository-maintained version of the LoopX
launch narrative. It is safe to review in PRs, quote in public issues, and use
as source material for external posts. It should not include private benchmark
traces, internal document links, raw verifier output, local absolute paths, or
unpublished performance claims.

## Core Judgment

LoopX is not primarily a todo app, benchmark runner, or replacement
agent framework.

Its strongest public position is:

> Always-on agent teams need a human-in-the-loop control plane: human-gated
> work waits explicitly, while independent safe lanes keep moving with
> evidence.

The important product detail is not that the harness stores more state. It is
that the state becomes actionable:

- the blocked human decision remains visible as a concrete user todo;
- primary and side agents can see who owns which todo and scope;
- safe fallback work can continue without pretending the fallback is now the
  main lane;
- quota, validation, public/private boundaries, and run evidence remain tied to
  the turn;
- the next agent can inherit the decision instead of reconstructing it from
  chat history.

## Public-Safe Good Case

A useful public-safe example is a long-horizon benchmark rotation.

The agent was rotating across Terminal-Bench, SkillsBench, and Agents' Last
Exam style work. One benchmark family became source-ready, but the next real
local run required acquiring a large Docker image. That acquisition is a human
resource decision, not something an automation loop should silently perform.

LoopX should handle that situation as a first-class control-plane event:

1. Write the image acquisition as a concrete user todo.
2. Keep that benchmark lane marked as source/runner-ready but image-gated.
3. Continue safe no-upload work on other benchmark families when quota and
   policy allow it.
4. Record that the continued work is a blocked-priority fallback, not a change
   in the primary objective.

This is the product moment worth explaining publicly.

Many agent products stop at the first gate and wait for the user to click a
choice. LoopX should make the user decision explicit while still using
the agent turn on safe validated work. The operator sees both facts: what needs
their decision, and why the agent is still allowed to make progress elsewhere.

## Message Architecture

The external story can be compressed into three claims:

1. Agent runtimes do the work; LoopX keeps long-running work
   recoverable, reviewable, and bounded.
2. Human-in-the-loop is not frequent confirmation. It is durable user intent,
   gate, reward, and boundary state that future agent turns can inherit.
3. Good long-running automation needs a control plane for objective, evidence,
   fallback, quota, and publication safety.

This lets the project stay distinct from generic agent frameworks:

- Prompt engineering asks how to instruct the model.
- Context engineering asks what to show the model.
- LoopX asks how the agent keeps acting over time without losing the
  goal, crossing boundaries, or making the human become a scheduler.

## README / PR Boundary

Public README and PR copy may claim:

- LoopX makes user and agent work lanes explicit.
- A gated high-priority lane can coexist with safe fallback work.
- Fallback work is audited as fallback.
- Quota spend happens only after validated delivery or compact blocker
  writeback.
- Public/private boundary checks are part of the product surface.

Public copy should not claim:

- benchmark-wide score uplift from one positive case;
- official leaderboard performance;
- access to private raw trajectories or verifier output;
- fully autonomous production control;
- that any single benchmark family proves the whole product.

## Follow-Up Public Assets

Useful next public assets:

- a fake benchmark-rotation demo that shows `user_gate + safe_fallback`;
- a README screenshot or status fixture where the blocked gate and fallback are
  both visible;
- a short post explaining why long-running agent work is a control-plane
  problem, not just a longer-context problem;
- a contributor-friendly issue for `blocked_priority_fallback` dashboard/status
  projection.

These assets should use synthetic or compact public-safe data. Real benchmark
evidence can inform the design, but raw traces and private runner artifacts
should stay outside the repository.
