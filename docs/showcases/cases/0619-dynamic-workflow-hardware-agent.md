# 0619: Dynamic Workflow For Hardware-Agent Development

## Summary

This companion note explains the public-safe boundary for the interactive
hardware-agent workflow case:

[Open the interactive case page.](0619-dynamic-workflow-hardware-agent.html)

The case describes a dynamic workflow around fuzzy, long-running hardware
development goals: generated scripts coordinate bounded worker-agent actions,
while LoopX keeps the goal, quota, todo ownership, validation evidence, and run
history stable outside any one chat thread.

## What Can Be Said Now

The case is useful because it points to a different showcase family from the
benchmark cases:

- the goal is open-ended rather than a fixed benchmark run;
- the domain has specialized engineering constraints;
- multiple agents need a shared view of ownership, state, and convergence;
- the product story is "dynamic workflow" rather than a single CLI command;
- the public artifact now includes five public-safe hardware cases spanning
  closed validation, timing optimization, design-space exploration, Fmax
  optimization, and convergence to an engineering floor.

## LoopX Behavior To Highlight

The public case highlights how LoopX helps with:

- durable state across a long-running fuzzy goal;
- agent ownership and handoff instead of opaque parallel work;
- progress convergence through shared todos, evidence, quota, and review boundaries;
- operator visibility into what needs a decision versus what can continue.

## Evidence Boundary

Do not publish raw chats, screenshots, proprietary design details, internal
tool names, private repositories, local paths, task ids, or unpublished
hardware artifacts. Public claims should stay at the product-pattern and
public-case level unless a contributor explicitly approves deeper sanitized
evidence.

## Public Artifact

The interactive HTML page is a static public artifact. It can be opened directly
from the repository or hosted as part of the Frontstage Pages bundle. It is not
a runnable hardware benchmark and should not be presented as a reproducible
EDA workflow.

## Public Evidence Sequence

1. A fuzzy engineering goal needs more than one worker agent.
2. LoopX gives the agents a shared state and ownership surface.
3. Generated scripts fan out bounded work to specialized workers.
4. Work converges through claimed todos, validation evidence, and a primary
   review path.
