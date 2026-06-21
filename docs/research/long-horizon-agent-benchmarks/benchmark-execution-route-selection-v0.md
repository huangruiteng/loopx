# Benchmark Execution Route Selection v0

Date: 2026-06-12

Status: route selected; real execution still gated.

## Scope

This packet chooses the next execution-scope route after the recent public-safe
gate packets. It does not start a benchmark, read raw task material, invoke
Codex or model APIs, generate patches, acquire images, start containers, start
service stacks, evaluate outputs, upload, submit, touch public ranking paths,
read credentials, or inspect raw trajectories/screenshots.

## Decision

Choose the SWE-Bench Pro one-instance private pilot as the first real e2e route
if and only if a separate execution-scope gate is approved later.

Defer TheAgentCompany single-task host-Codex execution until after the first
SWE-Bench Pro pilot or until SWE-Bench Pro is rejected/stalled.

## Why SWE-Bench Pro First

SWE-Bench Pro has the smaller integration surface today:

- selected public row has already been compacted into hash/count metadata;
- one selected public image has metadata recorded;
- official runner source has been preflighted without task material;
- one-instance launch and execution gate packets already exist;
- the future real pilot has a clear five-phase boundary: private sample
  reduction, trusted-local Codex patch generation, selected image acquisition,
  selected container start, and official patch evaluation.

TheAgentCompany remains valuable but has more unresolved integration work:

- no single task has been selected;
- no task image reference has been selected;
- real execution needs multi-service setup;
- host-networking/socket-permission implications are broader;
- a host-Codex container/browser/file action adapter is still unimplemented;
- private trajectory and screenshot handling is more central to the runner.

## Route Ranking

| Rank | Route | Ready Evidence | Main Blockers | Decision |
| --- | --- | --- | --- | --- |
| 1 | SWE-Bench Pro one-instance private pilot | selected row, image metadata, runner source preflight, launch packet, execution gate packet | private sample, local Codex patch generation, selected image/container, evaluator | choose as first real pilot after execution-scope approval |
| 2 | TheAgentCompany single-task host-Codex pilot | setup readiness, source preflight, single-task host-Codex gate packet | service stack, task selection/material, action adapter, private artifacts | defer |
| 3 | another reachable low-success gate packet | benchmark scan exists | lower marginal value than first execution-scope decision | defer unless execution scope is rejected or stalls |

## Execution-Scope Contract

The selected SWE-Bench Pro route is not authorized to run from this packet.
A future real pilot must explicitly approve the following scope before any
execution:

- private sample artifact creation and hash/count-only public reduction;
- trusted-local Codex CLI patch generation without copying Codex auth;
- selected image acquisition with explicit platform handling;
- selected container start and evaluator execution;
- private output storage and compact result reduction;
- no upload, no submit, no public ranking path, and no leaderboard claim.

Until that scope exists, the next safe automatic actions are limited to
public-safe control-plane maintenance, another no-run gate packet, or surfacing
the execution-scope decision.

## Executable Fixture

The deterministic fixture is:

```bash
python3 examples/benchmark-execution-route-selection-smoke.py
```

It emits `benchmark_execution_route_selection_v0` and asserts:

- SWE-Bench Pro is selected before TheAgentCompany;
- the selected route has lower integration-surface score;
- real execution is not authorized now;
- no benchmark, Codex/model call, image/container, service stack, private
  material, credential, raw artifact, upload, submit, or public ranking path is
  touched.

## Validation

Targeted validation:

```bash
python3 examples/benchmark-execution-route-selection-smoke.py
python3 -m py_compile examples/benchmark-execution-route-selection-smoke.py
loopx check \
  --scan-path examples/benchmark-execution-route-selection-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/benchmark-execution-route-selection-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

## Claim Boundary

This route-selection packet is not a benchmark result and should not be used
to claim LoopX improves SWE-Bench Pro, TheAgentCompany, or any other
benchmark. It only reduces the next-route ambiguity for future execution-scope
planning.
