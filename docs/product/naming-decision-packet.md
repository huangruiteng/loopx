# Naming Decision Packet

This packet records the current public naming recommendation for LoopX.
It is intentionally lightweight: the project is still young, so the goal is to
avoid a premature repository rename while giving maintainers a crisp brand,
category, and tagline to test in first-contact conversations.

## Recommendation

Keep the repository and product name:

```text
LoopX
```

Use this hero promise near the first screen:

```text
Always-on agent teams, governed by human judgment
```

Use this control-plane category line next to it:

```text
Gate-aware human-in-the-loop control plane
```

Use this supporting category/tagline language when more explanation is needed:

```text
dynamic goal control plane
```

The public story should be:

> LoopX is the dynamic goal control plane around agent loops. Codex,
> Claude Code, Cursor, terminal agents, and benchmark runners execute bounded
> work; LoopX turns a static goal into long-running state: gates, todos,
> claims, scopes, quota, evidence, and handoffs stay visible across those loops.

Do not rename the repo to `lifetime-loopx` or
`dynamic-loopx` now. Use "dynamic goal control plane" as category
language until there is stronger evidence that users remember another name
better than `LoopX`.

## Why Not Rename Yet

`LoopX` has two advantages:

- it is short enough to say in conversation and fit in command names;
- it keeps the current CLI, docs, repo, package, and existing public links
  stable while the product surface is still moving.

The name is not perfectly distinctive. "Goal" can sound like a task-list or
Codex goal-mode feature, and "Harness" needs the first screen to explain the
control-plane role. But this can be handled with the category and comparison
copy:

```text
Not an agent runtime; the control plane around the runtime.
Not Codex goal mode; the dynamic goal state that survives across executor
loops.
```

A repo rename would be noisy now: it would create link churn before the project
has enough public proof that a new name improves recall, search, and
comprehension.

## Candidate Comparison

| Candidate | Strength | Weakness | Decision |
| --- | --- | --- | --- |
| `LoopX` | Short, current, command-friendly, broad enough for engineering and creator/operator cases. | Needs category copy to avoid confusion with Codex goal mode or todo apps. | Keep as brand. |
| `Lifetime LoopX` | Makes the long-horizon ambition explicit. | Long, heavy, awkward as a repo/package name, and can sound abstract before users understand the product. | Use as explanatory language, not brand. |
| `Dynamic LoopX` | Captures the contrast with static goal prompts and one-shot automation. | Still long as a repo/package name, and "dynamic" can sound generic without the control-plane proof. | Use as category signal, not brand. |
| `Goal Control Plane` | Directly names the category. | Too generic; weak brand; less distinctive in search or conversation. | Use as occasional explanation only. |
| `Agent Control Plane` | Clear for agent-infrastructure audiences. | Overclaims the scope and implies LoopX is a runtime/orchestrator. | Avoid as primary framing. |
| `Long-Horizon Control Plane` | Emphasizes the real problem. | Broad and technical; less connected to the user's concrete goal. | Use in long-form docs when useful. |
| `GoalOS` / `AgentOS` style names | Memorable and product-like. | Overclaims platform scope and invites runtime expectations. | Avoid for now. |

## Naming Architecture

Use three layers:

1. **Brand**: `LoopX`
2. **Hero promise**: `Always-on agent teams, governed by human judgment`
3. **Category**: `Gate-aware human-in-the-loop control plane`
4. **Support phrase**: `dynamic goal control plane`

This lets the project keep a stable name while still sharpening the product
category.

Example first-screen stack:

```text
LoopX

Always-on agent teams, governed by human judgment.

Gate-aware human-in-the-loop control plane.

Dynamic goal control plane for long-running agents.
```

Chinese-first stack:

```text
LoopX

Always-on agent teams, governed by human judgment
Gate-aware human-in-the-loop control plane
Dynamic goal control plane for long-running agents
让多个 agent 昼夜接力，把人的判断留在控制面。

LoopX 不是替代 Codex goal/automation，而是给这些 executor loop
提供动态长期目标控制面。
```

## When To Use Each Phrase

Use `LoopX` when naming the product, repository, CLI, examples, and
showcase cases.

Use `Always-on agent teams, governed by human judgment` when the first-contact
surface needs a stronger product promise than "state management" without
overclaiming autonomous production control.

Use `Gate-aware human-in-the-loop control plane` when a first-contact reader
needs the technical category immediately.

Use `dynamic goal control plane` when explaining why this is larger than one
agent session, one terminal command, or one benchmark run. Use
`lifetime-goal` only as a secondary explanation for time horizon, not as the
main category.

Use `Your agents keep the night shift. You keep the judgment.` as a social or
demo tagline, not as a formal architecture term.

Avoid `agent teammate`, `agent framework`, `autonomous platform`, or `agent OS`
unless a future product surface actually owns those capabilities.

## Validation Signal Before Any Rename

Do not rename from `LoopX` unless at least one lightweight validation
cycle shows the current brand is the bottleneck.

A good validation cycle:

1. Show five new users the README or launch post for less than one minute.
2. Ask them to answer three questions without hints:
   - Is LoopX replacing Codex/Claude/Cursor, or wrapping them?
   - What problem does it solve in long-running agent work?
   - What phrase do they remember after closing the page?
3. Compare recall of `LoopX`, `dynamic goal control plane`,
   `lifetime-goal control plane`, and `human-in-the-loop control plane`.
4. Record only public-safe aggregated notes: no raw chat transcripts, personal
   names, screenshots, internal links, or private project context.
5. Rename only if users consistently remember another name better and also
   understand the runtime-vs-control-plane distinction.

Until that happens, improve first-screen copy, showcases, and diagrams before
changing the brand.

## Practical Copy Rules

- Pair the brand with the category on first mention:
  `LoopX, an always-on control plane for agent teams governed by human
  judgment`.
- When users confuse it with Codex goal mode, answer with the executor-loop
  split: Codex does bounded work; LoopX preserves dynamic goal state.
- Use "dynamic goal" for the category; use "lifetime-goal" in explanatory
  paragraphs only when the time horizon needs emphasis.
- Keep bilingual hero copy for Chinese-first surfaces, but keep English README
  body primarily English.
- Treat naming claims as outreach language. Do not add brittle smoke tests that
  assert exact marketing copy unless the wording becomes a stable public
  contract.

## Current Decision

Decision: keep `LoopX`.

Rationale: the name is serviceable, current, and compact; the sharper work is
to make the category unmistakable through first-screen copy, showcases, and
the control-plane board.

Next review trigger: revisit naming only after first-contact validation shows
that the name, not the explanation surface, is the main comprehension blocker.
