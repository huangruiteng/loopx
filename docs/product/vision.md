# Product Vision

LoopX is not only a developer tool for AI coding loops. It starts there
because engineering work exposes the hard control-plane problems quickly:
state drift, human gates, run evidence, handoffs, ownership, quota, and
public/private boundaries. The larger product category is a dynamic goal
control plane: a way to turn a static agent goal into long-running, reviewable
state that stays understandable and recoverable across many turns.

The long-term product should help humans who do not want to inspect prompts,
logs, or traces. A user should be able to run multiple agents across tools and
off-hours, then open a first screen and understand:

- what the agent has done;
- what the agent is doing now;
- where progress is blocked;
- what will happen next;
- what the agent needs from the user;
- how user feedback changes the plan.

## First-Screen Copy

**Always-on agent teams, governed by human judgment**

**Gate-aware human-in-the-loop control plane**

**Dynamic goal control plane for long-running agents**

**让多个 agent 昼夜接力，把人的判断留在控制面。**

LoopX 把目标、用户决策、agent todo、认领关系、scope、safe fallback、
run history 和 quota 放进同一层状态：该等人的地方明确等人，不该空等的
安全侧路继续推进。

The product promise is always-on progress without uncontrolled autonomy:
primary and side agents can continue bounded work, while human gates,
capability gates, quota, evidence, and project boundaries remain explicit. In
that sense, LoopX is not just a longer prompt or a bigger todo list; it
is the dynamic goal state around executor loops.

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

The current roadmap for this case should land as four public-safe tracks:

1. **Creator-operator case spec**: write the scenario as a concrete public
   showcase with synthetic or redacted evidence. The case should explain the
   user's job-to-be-done, the agent's long-running loop, where human taste or
   publishing judgment gates progress, and what LoopX contributes.
2. **Non-technical operator status model**: design first-screen cards that say
   what happened, what is happening, where the agent is blocked, what comes
   next, and what user feedback would change. This model should avoid internal
   CLI jargon and translate control-plane state into plain language.
3. **Fake-data demo storyboard**: prototype a frontend-ready flow for trend
   discovery, preference mapping, insight extraction, draft queues, material
   libraries, feedback, and controlled replanning. The first demo should use
   synthetic or public-safe data.
4. **Feedback and boundary contract**: define how user feedback becomes gates,
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
