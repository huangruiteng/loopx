# X Launch Playbook

## Source Intake

Build a compact source map before writing:

| Source | Use | Boundary |
| --- | --- | --- |
| LoopX public repo/docs | Product claims, repo link, feature nouns | Quote lightly; link repo/docs when relevant |
| Public X/tech posts | Tone, format, timing, who is in the conversation | Do not copy wording; transform into LoopX angle |
| CS-Notes creation drafts | Mechanisms and narrative preferences | Convert to public-safe English; remove private/company context |
| Local `.local` launch packets | Draft history and image paths | Do not commit or quote raw local/private state |
| Generated assets | X card or diagram | Verify quality and public-safe text before posting |

If the next read would cross into login-gated private timelines, raw chat
archives, private docs, or unpublished drafts, stop and project a user gate.

## Timing Heuristic

Use current research when available, but keep this default:

- Best general X windows for professional/tech content are weekday mornings in
  the target audience's local time, especially Tuesday to Thursday.
- For US and Europe overlap, prefer 9:00-10:30 AM US Eastern. It catches US
  East morning, Europe afternoon, and some US West early risers.
- If constrained to the next 24 hours, choose the next available weekday
  9:00-11:00 AM Eastern slot. Friday morning is acceptable for a launch that
  should not wait, but weaker than Tuesday to Thursday.
- Avoid Saturday for important launch posts unless the goal is a soft test.
- Leave the first 30-60 minutes free for replies, quote/reply follow-up, and
  monitoring. Early engagement matters more than a perfect timestamp.
- Schedule in exact local time and record the timezone conversion in the packet.

Example: with a Friday 2026-06-26 Asia/Shanghai morning decision and a "within
one day" constraint, the practical launch window is Friday 2026-06-26 21:05
Asia/Shanghai, equivalent to Friday 09:05 US Eastern.

## Post Forms

### Single Launch Post

Use when introducing LoopX to a broad developer-tool audience:

- 5-8 short lines;
- one repo link;
- one strong image;
- optional one or two relevant mentions;
- no hashtags unless the channel norm demands them.

Strong opening patterns:

- "Using Codex, Claude Code, or Cursor?"
- "Loop engineering needs a control plane."
- "The loop is no longer the hard part. Keeping it safe, stateful, and
  handoff-ready is."

### Thread

Use only when the idea needs proof, examples, or a technical derivation:

- post 1: category claim plus repo link;
- post 2: problem in the current agent workflow;
- post 3: LoopX control-plane primitives;
- post 4: concrete case or image;
- final post: ask for maintainers/builders to try the local setup.

Do not split a short launch claim into a thread just because X supports it.

### Reply/Conversation

Use replies to join existing conversations, not to spray the same pitch:

- first paragraph must be target-specific;
- cite the repository or issue only when it answers the conversation;
- ask for one concrete decision, such as "would this help your long-running
  repro/CI loop?";
- stop after one reply unless the owner engages.

## Image Rules

Use at least one image for a first launch post unless the post is deliberately
conversation-only.

Prefer:

- a clean diagram showing `runtime loop -> state/gate/evidence/handoff`;
- a polished product/repo screenshot with no private state;
- a generated card with one category claim and the repo URL.

Avoid:

- decorative gradients or generic AI art;
- tiny terminal screenshots that cannot be read on mobile;
- private active-state screenshots;
- images whose text says "control plane" without clarifying it is not merely a
  front-end/dashboard.

Image copy should fit one of these frames:

- `Loop engineering needs state, gates, evidence, and handoff.`
- `Local-first control plane for agent loops.`
- `Keep the loop moving. Keep judgment human.`

## Mentions And Anti-Spam

Mentions can help only when the post directly relates to the person's current
conversation or audience. For a first LoopX launch post, one or two relevant
mentions are acceptable; more than two usually looks like growth hacking.

Before posting from a new/cold account, check:

- the body is unique to this target/channel;
- the first sentence is not a generic pitch;
- the repo link is present when claiming an open-source product;
- the post names the concrete value, not just "we built X";
- the image is useful on its own;
- there is no request for credentials, private data, production action, or mass
  outreach.

If a GitHub/X comment is minimized as spam, do not repost, bump, edit, delete,
or appeal without explicit owner approval.

## LoopX Launch Angles

### Fast Local Entry

Audience: developers already using Codex, Claude Code, Cursor, or local agents.

Core message: LoopX is the fastest local way to add state, gates, evidence,
quota, and handoff around an existing agent loop.

Good when the post needs conversion to repo visits or install attempts.

### Philosophy

Audience: AI builders and agent-framework thinkers.

Core message: the next step after prompt/context engineering is loop
engineering; humans should own judgment while the loop remains inspectable.

Good when the goal is category creation and discussion.

### Academic/State Framing

Audience: research engineers and long-horizon agent benchmark readers.

Core message: long tasks fail when state drifts across handoff; LoopX makes the
handoff target explicit and validates drift.

Good when paired with diagrams such as state transform, fixed point, or drift.

### Evidence/Case Proof

Audience: maintainers, benchmark operators, and engineering managers.

Core message: show one gate/fallback/run-history case and what became safer or
cheaper.

Good when there is a public-safe case card or benchmark artifact.

### Connector/Content-Ops

Audience: creator-operators and open-source maintainers.

Core message: connectors such as X via ego-lite or GitHub reply monitoring
should start metadata-only, record gates, and promote only source-safe signals.

Good when explaining how users can connect their own agent into public-safe
content operations.

## Launch Packet Checklist

Every ready packet should include:

- chosen angle and target reader;
- exact post body;
- image path(s) and why each is included;
- repo link and mentions;
- source map with public/private status;
- posting time with timezone conversion;
- first-hour engagement plan;
- publish gate text that the user can approve verbatim;
- stop condition if the post is not sent or receives a spam/minimized signal.
