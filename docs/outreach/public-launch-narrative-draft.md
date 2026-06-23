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

An even more concrete way to say this for early users:

> LoopX helps a maintainer manage Loop Agents as always-running digital
> workers: pick the right anchors, keep gates visible, review evidence, and
> decide what should improve next.

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

## Public-Safe Primary Case

The strongest first public story should be maintainer-first management, not a
domain-specific solver UI.

A maintainer has several long-running agent lanes: product docs, showcase
cards, open-source collaboration candidates, issue / PR pilot ideas, and
private strategy inputs. Without a control plane, the maintainer becomes the
scheduler: reading chats, remembering which agent owns which lane, deciding
what still matters, and asking "continue?" again and again.

LoopX should make that work visible:

1. Incoming signals enter a compact signal inbox.
2. The maintainer or policy selects a small number of high-value anchors.
3. Each anchor gets an owner, allowed action, evidence boundary, and stop
   condition.
4. Agent work writes back evidence instead of raw traces.
5. Human feedback becomes performance-review signal: value, quality, control,
   cost, and learning.

This is the core public claim: LoopX is not another executor. It is the
management surface for long-running agent work.

## Public-Safe Good Case

A useful supporting example is a long-horizon benchmark rotation.

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

## Public-Safe Office Operations Case

Another supporting story is office operations: social research, chat/context
review, draft preparation, and outreach follow-up.

The risky version of this story says "the agent writes more posts." That is too
shallow. The better story is:

1. Connectors bring in information from browser channels, local chat archives,
   issues, docs, or tasks.
2. LoopX turns information into selected signals and anchors instead of a noisy
   stream.
3. The agent proposes a draft, reply, follow-up, or research note.
4. A human scores usefulness, taste, risk, and source quality.
5. Publishing or outreach remains a gate.
6. The Loop Agent review records what became a qualified conversation,
   accepted insight, useful draft, or rejected path.

This makes office operations a good acquisition story because many teams feel
information overload before they feel a need for another agent framework.
LoopX should claim the management loop: more relevant signals, better feedback,
clearer gates, and evidence-backed improvement.

## Message Architecture

The external story can be compressed into three claims:

1. Agent runtimes do the work; LoopX keeps long-running work
   recoverable, reviewable, and bounded.
2. Human-in-the-loop is not frequent confirmation. It is durable user intent,
   gate, reward, and boundary state that future agent turns can inherit.
3. Good long-running automation needs a maintainer surface for signal intake,
   anchor selection, evidence, fallback, quota, performance review, and
   publication safety.

This lets the project stay distinct from generic agent frameworks:

- Prompt engineering asks how to instruct the model.
- Context engineering asks what to show the model.
- LoopX asks how the agent keeps acting over time without losing the
  goal, crossing boundaries, or making the human become a scheduler.

## README / PR Boundary

Public README and PR copy may claim:

- LoopX makes user and agent work lanes explicit.
- LoopX helps maintainers manage Loop Agents through signal inbox, selected
  anchors, gates, evidence, and performance review.
- A gated high-priority lane can coexist with safe fallback work.
- Fallback work is audited as fallback.
- Quota spend happens only after validated delivery or compact blocker
  writeback.
- Public/private boundary checks are part of the product surface.
- Open-source issue / PR pilots can be used as high-value anchors when the
  implementation ownership, evidence boundary, and showcase consent are clear.
- Office-operations pilots can use browser, chat, issue, doc, and task
  connectors as information inputs, while publish/outreach actions remain
  explicit human gates.

Public copy should not claim:

- benchmark-wide score uplift from one positive case;
- official leaderboard performance;
- access to private raw trajectories or verifier output;
- fully autonomous production control;
- that any single benchmark family proves the whole product.

## Follow-Up Public Assets

Useful next public assets:

- a maintainer-first management screenshot with signal inbox, anchors, active
  lanes, gates, evidence, and performance-review notes;
- a public-safe open-source anchor packet template for issue / PR solver
  pilots;
- a public-safe office-operations connector storyboard that measures accepted
  signals, qualified conversations, useful drafts, feedback learning, and
  boundary correctness instead of raw article count;
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
