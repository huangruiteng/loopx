# 0620: Creator-Operator Long-Running Agent Case

## Summary

This case describes a public-safe creator-operator workflow for a
non-technical user who wants a long-running agent to help with content research
and planning.

The user is not trying to operate an agent framework. They want a controlled
work loop that can keep a creative goal moving:

- detect public trend candidates;
- map those candidates against personal creative preferences;
- extract reusable insights;
- draft article, short-video, or newsletter angles;
- maintain a material, phrase, source, and copy library;
- ask for human taste, risk, or publishing decisions at the right time.

The case is synthetic. It does not contain real platform data, private notes,
creator drafts, audience metrics, screenshots, raw browsing traces, internal
links, or performance claims.

## Situation

A creator-operator has recurring medium-horizon work:

1. Check what changed across public conversation spaces.
2. Decide which topics fit their own taste, expertise, and audience.
3. Turn the selected topics into useful creative angles.
4. Keep a library of source snippets, examples, hooks, and reusable phrases.
5. Review drafts before anything is published.

Without a control plane, the experience is awkward even if the underlying agent
is capable:

- the user has to ask "what did you do?" after every run;
- research, draft, and material-library work blur together;
- private notes and public evidence can be mixed by accident;
- a publishing decision can block the whole loop;
- feedback such as "not my style" is easy to lose in chat;
- the user cannot tell whether the agent is safely continuing side work or
  waiting for a required decision.

The bottleneck is product experience, not only model ability.

## LoopX Behavior

LoopX turns the workflow into visible control-plane objects:

| Workflow concern | LoopX object |
| --- | --- |
| Long-running creative objective | goal state |
| "Can this be published?" | user gate |
| Research, insight, draft, and library work | agent todos |
| "This is not my style" | feedback signal / preference hint |
| Synthetic demo data versus private user material | boundary note |
| What changed since last check | run history summary |
| Safe work while a publishing gate waits | safe side path |
| Agent identity and lane ownership | claim / future lease |

The important behavior is gate-aware continuation. The agent should not
autopublish or treat private drafts as public evidence. But while a publishing
decision waits, it can still do safe side work: organize synthetic examples,
prepare source-attribution checklists, update the material-library schema, or
draft questions for the user.

## Public-Safe Walkthrough

The following walkthrough uses only fake data.

### 1. Trend Candidates

The agent proposes three synthetic trend clusters:

| Candidate | Why it might matter | Boundary |
| --- | --- | --- |
| "AI note workflows for solo operators" | aligns with productivity and agent-tooling audience | public-safe synthetic topic |
| "Short-form content from long research notes" | fits creator-operator reuse loop | public-safe synthetic topic |
| "Human approval before agent publication" | matches safety and trust framing | public-safe synthetic topic |

### 2. Preference Map

The user has compact preference hints:

- prefers practical case studies over broad futurism;
- avoids growth-hack language;
- wants evidence boundaries stated plainly;
- likes examples that show what the agent will not do.

These are preferences, not hard safety gates. LoopX should keep them
separate from permission decisions such as publish/no-publish.

### 3. Insight Board

The agent extracts draft insights:

- "A long-running creator agent needs a dashboard, not another hidden prompt."
- "The user gate is not a failure; it is the product boundary."
- "Safe side paths keep research useful while publishing waits."

Each insight should carry source status: synthetic, public-source summary,
private note, or needs review. Public docs may only use synthetic or
public-source summaries.

### 4. Draft Queue

The agent prepares draft angles:

| Draft angle | Status | Gate |
| --- | --- | --- |
| "How I keep a research agent from waiting forever" | outline ready | tone review |
| "What a creator agent should show before it publishes" | idea only | publish policy |
| "Material libraries as memory for creative work" | source map needed | no publish yet |

The user sees what is ready, what is blocked, and what can continue.

### 5. Material Library

The agent maintains structured public-safe material:

- reusable hooks;
- source summaries;
- phrasing examples;
- rejected angles and why they were rejected;
- boundary notes for private drafts or unpublished ideas.

This library is not a raw memory dump. LoopX should keep it governed by
source status and user feedback.

### 6. Human Feedback

The user can respond with structured feedback:

| User feedback | Control-plane effect |
| --- | --- |
| "This angle is useful." | reward / preference reinforcement |
| "Too salesy." | preference hint and draft revision todo |
| "Do not use this source." | boundary correction and source removal todo |
| "Publish after I review tone." | user gate with explicit stop condition |
| "Keep researching, but do not draft yet." | todo reprioritization |

The feedback changes the next plan without becoming an invisible chat-only
memory.

The public feedback and source-status rules are specified in
[creator-ops-feedback-boundary-contract.md](../creator-ops-feedback-boundary-contract.md).

## User-Facing Value

For a creator-operator, the value is not "the agent can browse and write." The
value is that the work remains legible:

- the user knows what changed since the last check;
- publishing gates stay explicit;
- private material stays out of public examples;
- safe side work continues while gated work waits;
- feedback becomes a durable planning signal;
- the agent's next move is visible before it spends another run.

For a potential LoopX user, the reusable pattern is broader: a
long-running agent loop becomes easier to trust when goals, gates, todos,
evidence, boundaries, feedback, and next actions appear in one control plane.

## Evidence Boundary

This case is a synthetic product case spec. It intentionally excludes:

- real creator notes, drafts, screenshots, or audience data;
- raw social-platform content or scraping output;
- private user preferences that were not rewritten as synthetic examples;
- internal links, private repositories, local paths, credentials, or raw agent
  sessions;
- claims about reach, quality, engagement, or revenue improvement.

Future demos should use fake data or public-domain sample material and should
keep no-autopublish gates visible.

## Website Story Beats

1. A creator-operator has a long-running research and content-planning goal.
2. The agent proposes trend candidates, maps them to preferences, and drafts
   insight options using synthetic data.
3. LoopX separates the publishing gate from safe side work.
4. The user gives feedback that becomes structured control-plane state.
5. The next agent run starts from visible goals, todos, boundaries, and
   feedback instead of a hidden chat transcript.

## Demo Status

The first public-safe storyboard is available in
[creator-ops-fake-data-storyboard.md](../creator-ops-fake-data-storyboard.md).
It defines a synthetic fixture and frontend panel sequence for trend
candidates, preference map, insight board, draft queue, material library,
human feedback, and controlled replan. No executable demo is included yet.
The companion feedback contract is
[creator-ops-feedback-boundary-contract.md](../creator-ops-feedback-boundary-contract.md).
