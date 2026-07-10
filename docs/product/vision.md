# Product Vision

LoopX is not only a developer tool for AI coding loops. It starts there
because engineering work exposes the hard control-plane problems quickly:
state drift, human gates, run evidence, handoffs, ownership, quota, and
public/private boundaries. The larger product category is a dynamic goal
control plane: a way to turn a static agent goal into long-running, reviewable
state that stays understandable and recoverable across many turns.

The long-term product should help humans who do not want to inspect prompts,
logs, or traces. The first customer is the maintainer/operator of a Loop Agent:
someone who needs to manage always-running digital workers, external signals,
human gates, evidence, and value over time. A user should be able to run
multiple agents across tools and off-hours, then open a first screen and
understand:

- what the agent has done;
- what the agent is doing now;
- where progress is blocked;
- what will happen next;
- what the agent needs from the user;
- how user feedback changes the plan.

## Loop Agent

A Loop Agent is an always-running digital worker with:

- a relatively stable responsibility;
- a relatively consistent work objective;
- external signals it watches or receives;
- work products that match its responsibility;
- organized evidence of what it did and why it mattered;
- human feedback through a lightweight performance-review loop;
- explicit focus and cost controls.

LoopX should not try to make every worker smarter by hiding more autonomy in
the executor. It should make the worker more manageable: selectable work,
visible gates, bounded execution, compact evidence, reviewable outcomes, and
clear next improvement targets.

## First-Screen Copy

**Always-on agent teams, governed by human judgment**

**Gate-aware human-in-the-loop control plane**

**Dynamic goal control plane for long-running agents**

**让多个 agent 昼夜接力，把人的判断留在控制面。**

LoopX 把目标、用户决策、agent todo、认领关系、scope、safe fallback、
run history 和 quota 放进同一层状态：该等人的地方明确等人，不该空等的
安全侧路继续推进。

The product promise is always-on progress without uncontrolled autonomy:
registered peers can continue independently claimed bounded work, while human gates,
capability gates, quota, evidence, and project boundaries remain explicit. In
that sense, LoopX is not just a longer prompt or a bigger todo list; it
is the dynamic goal state around executor loops.

## Maintainer-First Management Surface

The highest-priority product surface is an intelligent management view for the
maintainer/operator. It should answer:

- what signals arrived since the last check;
- which signals are high-value anchors worth acting on;
- which Loop Agent owns each active lane;
- which human gates need attention;
- what evidence proves progress or explains a stop;
- where the agent earned or lost performance-review credit;
- what next management action matters most.

This surface comes before a domain-specific issue-fix UI. Open-source issue and
PR work is valuable because it creates visible artifacts and measurable
feedback, but it should feed the maintainer surface rather than define the
whole product.

### Agent Work Feed

The ideal first interaction is closer to a recommendation feed than to a
project dashboard. The user should be able to review agent work the way they
review a stream of cards: quickly decide whether each output was useful,
misdirected, risky, or worth turning into the next anchor.

The feed item is not a raw task and not a raw log. It is an agent work card:

- what the agent produced;
- why the card deserves attention now;
- what evidence backs the claim;
- what it cost in quota or user attention;
- what the agent proposes next;
- which one-tap feedback choices are available.

Useful feedback should be lightweight but structured:

- useful; continue this direction;
- not useful; lower this pattern's priority;
- wrong direction; correct the goal or reward;
- evidence is insufficient; add validation;
- promote to anchor, showcase, or follow-up todo;
- risky or private; trigger boundary review or a gate.

This turns performance review from a periodic report into a continuous
human-in-the-loop signal. LoopX should sort the feed for management value, not
addiction: unresolved gates, high-value uncertain work, expensive repeated
patterns, evidence gaps, and showcase candidates should surface before routine
activity.

## Display Surface Adoption Path

The intelligent display surface and the LoopX control loop should be
decoupled at adoption time, but designed to grow together.

The first step can be read-only:

- ingest existing agent artifacts, issues, PRs, docs, run summaries, or chat
  feedback;
- show what the agent did, what evidence exists, and what deserves review;
- let the maintainer score value, quality, control, cost, and learning;
- produce a performance-review summary without changing the agent's next
  action.

This mode is useful even before a team adopts LoopX. It gives a maintainer a
low-friction way to inspect and quantify whether an always-running agent is
useful.

The second step is control writeback:

- accepted feedback becomes gates, todo changes, preference hints, reward
  notes, or anchor selection;
- low-quality work becomes blocker evidence, scope correction, or next
  improvement targets;
- selected anchors become bounded LoopX work with explicit evidence and stop
  conditions.

In short, the display surface makes agent work visible and reviewable; LoopX
makes that review change the next loop. The two surfaces can be adopted in
sequence, but they should share schemas such as `signal_v0`, `anchor_v0`,
`review_event_v0`, and `performance_review_v0`.

## Open-Source Anchors

Open-source issue / PR solver pilots are strong value-proof candidates when
they are chosen as high-value anchors:

- visible public artifact: issue, PR, failing check, stale review, or conflict;
- credible maintainer pain;
- bounded risk and clear stop conditions;
- measurable outcome: routed, diagnosed, fixed, merged, rejected, or gated;
- public-safe story potential.

LoopX's maintainer-side role is to choose anchors, define the candidate packet,
record the evidence boundary, capture human review signals, and graduate
approved outcomes into showcase material. The actual solver implementation may
belong to a repo-specific collaborator or adapter.

## Office Operations Connectors

Office and content-operations workflows are another useful showcase lane. The
point is not to make an agent produce more posts. The point is to show that a
Loop Agent can connect to more information surfaces, select higher-quality
signals, propose useful actions, and learn from human feedback.

A public-safe workflow can look like:

```text
connector
  -> information
  -> signal / trend / anchor candidate
  -> draft or action proposal
  -> human scoring / feedback
  -> optional publish or outreach gate
  -> performance review / next improvement
```

Good connector examples include browser-based social research, local-first chat
archive search, issue / PR metadata, meeting notes, task systems, and document
changes. Publishing or outreach should remain explicitly gated.

The right metrics are not raw draft count. Better signals are accepted anchors,
useful insights, qualified conversations, user-rated draft quality, feedback
learning, source-boundary correctness, and cost per useful signal.

## Creator-Operator Case

A useful medium-term case is a self-media or creator-operations user. The user
does not primarily care whether the underlying worker is Codex, Claude Code, a
browser agent, or a workflow script. They care whether the long-running agent
can help them keep a creative goal moving:

- detect trends across social platforms;
- map trends against the user's creative preferences and audience;
- extract insights that are worth creating from;
- draft articles, outlines, scripts, or video concepts;
- maintain a material, phrase, source, and copy library;
- show what changed since the last check;
- ask for human taste, risk, or publishing decisions at the right time.

The bottleneck is product experience as much as model capability. A user should
not have to read raw browsing traces, private notes, or agent reasoning to know
whether the work is useful. LoopX should turn that activity into a
small set of visible control-plane objects: goals, gates, todos, evidence,
feedback, boundaries, and next actions.

## Productization Tracks

The current roadmap should land as four public-safe tracks:

1. **Maintainer management surface**: design first-screen cards for signal
   inbox, selected anchors, active lanes, gates, evidence quality, performance
   review, value/cost trend, and next management action.
2. **Non-technical operator status model**: design first-screen cards that say
   what happened, what is happening, where the agent is blocked, what comes
   next, and what user feedback would change. This model should avoid internal
   CLI jargon and translate control-plane state into plain language.
3. **Open-source anchor packet**: define how an issue, PR, failing check, stale
   review, or conflict becomes a candidate with owner, risk, allowed action,
   evidence boundary, human gate, and showcase consent.
4. **Office-operations connector showcase**: prototype a public-safe
   connector-to-signal-to-feedback loop using synthetic or consented data, with
   an explicit publish/outreach gate and metrics beyond article count.
5. **Feedback and boundary contract**: define how user feedback becomes gates,
   preferences, todo updates, or product-improvement notes while preserving
   source attribution, platform terms, no-autopublish gates, and private
   creative-material boundaries.

## Boundary

This vision does not turn LoopX into a social-media crawler, publishing
bot, or end-user content platform. Those tools may live in a host product or
project adapter. LoopX should provide the durable control projection:
current goal, decision gates, safe next work, evidence summaries, feedback
writeback, and boundary checks.

The default product posture is conservative:

- do not autopublish content without an explicit user gate;
- do not treat private notes, drafts, or creative material as public evidence;
- do not copy raw platform data into public docs or examples;
- do not claim trend, audience, or performance uplift without a measured
  public-safe basis;
- keep user taste feedback separate from hard safety or permission gates.

## Why It Belongs In LoopX

This case stress-tests the same product promise as engineering and benchmark
loops, but with a different user: a non-engineering operator who needs clarity,
not infrastructure. If LoopX can make this workflow legible, it proves
the control plane is not just for developers. It is a way to keep long-running
agent work useful, bounded, reviewable, and easy to steer.
