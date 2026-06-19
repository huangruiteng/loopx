# Naming Decision Packet

This packet records the current public naming recommendation for Goal Harness.
It is intentionally lightweight: the project is still young, so the goal is to
avoid a premature repository rename while giving maintainers a crisp brand,
category, and tagline to test in first-contact conversations.

## Recommendation

Keep the repository and product name:

```text
Goal Harness
```

Use this category line near the first screen:

```text
Gate-aware human-in-the-loop control plane
```

Use this supporting category/tagline language when more explanation is needed:

```text
lifetime-goal control plane
```

The public story should be:

> Goal Harness is the lifetime-goal control plane around agent loops. Codex,
> Claude Code, Cursor, terminal agents, and benchmark runners execute bounded
> work; Goal Harness keeps the long-running goal, gates, todos, ownership,
> quota, evidence, and handoffs visible across those loops.

Do not rename the repo to `lifetime-goal-harness` now. Use "lifetime-goal" as
category language until there is stronger evidence that users remember it
better than `Goal Harness`.

## Why Not Rename Yet

`Goal Harness` has two advantages:

- it is short enough to say in conversation and fit in command names;
- it keeps the current CLI, docs, repo, package, and existing public links
  stable while the product surface is still moving.

The name is not perfectly distinctive. "Goal" can sound like a task-list or
Codex goal-mode feature, and "Harness" needs the first screen to explain the
control-plane role. But this can be handled with the category and comparison
copy:

```text
Not an agent runtime; the control plane around the runtime.
Not Codex goal mode; the lifetime-goal state that survives across executor
loops.
```

A repo rename would be noisy now: it would create link churn before the project
has enough public proof that a new name improves recall, search, and
comprehension.

## Candidate Comparison

| Candidate | Strength | Weakness | Decision |
| --- | --- | --- | --- |
| `Goal Harness` | Short, current, command-friendly, broad enough for engineering and creator/operator cases. | Needs category copy to avoid confusion with Codex goal mode or todo apps. | Keep as brand. |
| `Lifetime Goal Harness` | Makes the long-horizon ambition explicit. | Long, heavy, awkward as a repo/package name, and can sound abstract before users understand the product. | Use as explanatory language, not brand. |
| `Goal Control Plane` | Directly names the category. | Too generic; weak brand; less distinctive in search or conversation. | Use as occasional explanation only. |
| `Agent Control Plane` | Clear for agent-infrastructure audiences. | Overclaims the scope and implies Goal Harness is a runtime/orchestrator. | Avoid as primary framing. |
| `Long-Horizon Control Plane` | Emphasizes the real problem. | Broad and technical; less connected to the user's concrete goal. | Use in long-form docs when useful. |
| `GoalOS` / `AgentOS` style names | Memorable and product-like. | Overclaims platform scope and invites runtime expectations. | Avoid for now. |

## Naming Architecture

Use three layers:

1. **Brand**: `Goal Harness`
2. **Category**: `Gate-aware human-in-the-loop control plane`
3. **Support phrase**: `lifetime-goal control plane`

This lets the project keep a stable name while still sharpening the product
category.

Example first-screen stack:

```text
Goal Harness

Gate-aware human-in-the-loop control plane.

Long-running agent work, without losing the plot.
```

Chinese-first stack:

```text
Goal Harness

Gate-aware human-in-the-loop control plane
让人的判断成为控制面，而不是让 agent 在等待里空转。

Goal Harness 不是替代 Codex goal/automation，而是给这些 executor loop
提供 lifetime-goal 控制面。
```

## When To Use Each Phrase

Use `Goal Harness` when naming the product, repository, CLI, examples, and
showcase cases.

Use `Gate-aware human-in-the-loop control plane` when a first-contact reader
needs the product category immediately.

Use `lifetime-goal control plane` when explaining why this is larger than one
agent session, one terminal command, or one benchmark run.

Use `long-running agent work, without losing the plot` as a human tagline, not
as a formal architecture term.

Avoid `agent teammate`, `agent framework`, `autonomous platform`, or `agent OS`
unless a future product surface actually owns those capabilities.

## Validation Signal Before Any Rename

Do not rename from `Goal Harness` unless at least one lightweight validation
cycle shows the current brand is the bottleneck.

A good validation cycle:

1. Show five new users the README or launch post for less than one minute.
2. Ask them to answer three questions without hints:
   - Is Goal Harness replacing Codex/Claude/Cursor, or wrapping them?
   - What problem does it solve in long-running agent work?
   - What phrase do they remember after closing the page?
3. Compare recall of `Goal Harness`, `lifetime-goal control plane`, and
   `human-in-the-loop control plane`.
4. Record only public-safe aggregated notes: no raw chat transcripts, personal
   names, screenshots, internal links, or private project context.
5. Rename only if users consistently remember another name better and also
   understand the runtime-vs-control-plane distinction.

Until that happens, improve first-screen copy, showcases, and diagrams before
changing the brand.

## Practical Copy Rules

- Pair the brand with the category on first mention:
  `Goal Harness, a gate-aware human-in-the-loop control plane`.
- When users confuse it with Codex goal mode, answer with the executor-loop
  split: Codex does bounded work; Goal Harness preserves lifetime-goal state.
- Use "lifetime-goal" in explanatory paragraphs, not every headline.
- Keep bilingual hero copy for Chinese-first surfaces, but keep English README
  body primarily English.
- Treat naming claims as outreach language. Do not add brittle smoke tests that
  assert exact marketing copy unless the wording becomes a stable public
  contract.

## Current Decision

Decision: keep `Goal Harness`.

Rationale: the name is serviceable, current, and compact; the sharper work is
to make the category unmistakable through first-screen copy, showcases, and
the control-plane board.

Next review trigger: revisit naming only after first-contact validation shows
that the name, not the explanation surface, is the main comprehension blocker.
