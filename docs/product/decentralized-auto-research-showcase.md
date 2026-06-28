# Decentralized Auto-Research Showcase Blueprint

This note turns the Arbor review into a LoopX product path. Arbor's public
showcase is strong because it is concrete: a benchmark, a hypothesis tree,
dev/held-out scores, replayable events, and a final report. LoopX should aim
for the same clarity while keeping its own architecture: decentralized agents
over one shared control plane, not one leader Coordinator.

## What Arbor Demonstrates

Arbor's public materials show a repeatable autonomous research loop:

- a Research Contract that names objective, editable files, protected harness,
  metric, budget, and review mode;
- an Idea Tree where hypotheses record status, evidence, score, branch, retry
  status, grounding, and related-work audit;
- isolated executor worktrees for each experiment;
- a dev metric for iteration and a held-out metric for promotion;
- replay/report/export surfaces that make the run inspectable;
- a benchmark zoo, including `algotune_knn`, that is small enough for a user to
  watch end to end.

The Arbor `algotune_knn` demo is especially useful for LoopX because it is
public-safe, deterministic, CPU-only, and easy to explain: optimize a k-nearest
neighbors solver without editing the protected evaluator. Arbor reports an
example six-cycle improvement from roughly baseline speed to multi-x speedup,
with held-out validation.

## LoopX Adaptation

LoopX should reproduce the product value, not the topology.

| Arbor shape | LoopX version |
| --- | --- |
| Coordinator-mediated tree management. | Kernel-owned evidence graph plus per-agent frontier projections. |
| Executors receive ideas from Coordinator. | Agents claim todo-backed hypotheses through `quota should-run --agent-id`. |
| Idea Tree is the durable memory. | `research_hypothesis_v0` plus `research_evidence_event_v0` in the shared state graph. |
| Merge/prune decided by Coordinator. | Promotion policy, held-out evidence, operator gates, and todo lifecycle decide. |
| Dashboard shows one run. | Frontstage shows lanes, claims, evidence, promotion candidates, and blockers. |

The important product phrase is:

> LoopX lets multiple agents run an autonomous research search without a
> leader agent: hypotheses, evidence, retries, and promotion decisions live in
> the control plane, and each agent receives only the frontier it is allowed to
> attempt.

The executable product contract is split in two:

- `decentralized_auto_research_state_v0` defines the records and projections:
  contracts, todo-linked hypotheses, evidence events, frontier, evidence graph,
  and showcase projection.
- `auto_research_lane_contract_v1` defines decentralized lanes: curator,
  hypothesis proposer, executor, evaluator/promoter, and product narrator. Each
  lane contributes typed records through claims and gates; none owns the whole
  graph.
- [Auto-research product metrics](auto-research-product-metrics.md) defines
  which user-value metrics the product surface should show. It intentionally
  favors scored attempts, held-out lift, negative-evidence reuse, retry
  recovery, and human promotion decisions over implementation counters such as
  file count, smoke count, or dashboard row count.

## Showcase Candidate

**Title:** Decentralized Auto Research: k-NN Speedup

**Public task:** make a brute-force k-nearest-neighbors solver faster while
preserving exact output.

**Inputs:**

- editable: `solution.py`;
- protected: `eval.py`, `task.py`, generated dev/test data;
- metric: `speedup`, higher is better;
- dev command: `bash eval.sh dev`;
- held-out command: `bash eval.sh test`;
- starting result: baseline around `1.0x`;
- expected value metric: best held-out speedup, plus number of useful negative
  directions retained as future priors.

**LoopX surfaces to show:**

1. Research Contract card: objective, editable/protected scopes, metric, budget.
2. Decentralized frontier: which agent claimed which hypothesis, which ones are
   blocked or retired, and why.
3. Evidence timeline: attempts, dev score, held-out score, branch/ref, retry
   status.
4. Promotion decision: what got promoted, which alternatives were retired, and
   which evidence proves the boundary.
5. Product metrics: time to first scored attempt, useful hypotheses per active
   day, held-out lift, negative-evidence reuse, retry recovery, and human
   promotion decisions required.
6. Report: concise public-safe final summary with commands and artifacts.

## Candidate Hypothesis Graph

This graph is a fixture target, not a claim that LoopX has already achieved the
numbers. It gives the showcase a concrete shape to reproduce.

```mermaid
graph TD
  ROOT["Research contract: exact k-NN speedup"]
  H1["hyp_001: vectorize pairwise distances"]
  H2["hyp_002: partial selection with argpartition"]
  H3["hyp_003: GEMM distance expansion"]
  H4["hyp_004: batch query path"]
  H5["hyp_005: dtype / contiguous array tuning"]
  H6["hyp_006: approximate search (retire if correctness fails)"]

  ROOT --> H1
  H1 --> H2
  H2 --> H3
  H3 --> H4
  H4 --> H5
  H4 --> H6
```

The user-facing point is not the exact technique. The point is that LoopX
retains the failed or bounded directions as explicit negative evidence, so the
next agent does not rediscover them from scratch.

## Minimal Reproduction Plan

New users should not have to learn the full command matrix first. The
quickstart path starts from one read-only command that returns the research
contract, the files that would be created, and the first runnable hypothesis for
the current agent:

```bash
loopx --format json auto-research quickstart \
  --agent-id codex-side-bypass
```

When the preview is acceptable, explicitly create the protected starter pack:

```bash
loopx --format json auto-research quickstart \
  --agent-id codex-side-bypass \
  --output-dir auto_research_knn_pack \
  --execute
```

This writes a k-NN research pack with one editable candidate file, a protected
baseline/evaluator, and a `research_contract_v0`. The command also returns the
next dev/holdout/evidence commands, so an agent can continue from a concrete
hypothesis instead of choosing among `frontier`, `evidence`, and
`append-evidence` manually.

The runnable pack now lives at `examples/auto_research_knn_pack/`. It provides
an editable candidate solver, a protected evaluator, deterministic dev/held-out
splits, and a no-upload boundary.

Run the candidate on the dev split:

```bash
python3 examples/auto_research_knn_pack/protected_eval.py \
  --solution examples/auto_research_knn_pack/solution_candidate.py \
  --split dev
```

Run the candidate on the held-out split:

```bash
python3 examples/auto_research_knn_pack/protected_eval.py \
  --solution examples/auto_research_knn_pack/solution_candidate.py \
  --split holdout
```

The current public pack reports exact neighbor identity with deterministic
protected speedup `4.0x` on dev and `4.5x` on holdout for the partial-selection
candidate. The metric is a protected ranking-work proxy rather than wall-clock
time, so it is stable enough for smoke tests while still preserving the product
shape: dev evidence, held-out promotion evidence, and a clean boundary.

The fixture-backed projection remains the read-only showcase state slice:

```bash
loopx --format json auto-research frontier \
  --fixture examples/fixtures/decentralized-auto-research-knn.public.json \
  --agent-id codex-side-bypass
```

This renders `decentralized_research_frontier_v0`,
`research_evidence_graph_v0`, and `research_showcase_projection_v0` from a
public fixture. It does not launch experiments; it proves that the state shape
can present a per-agent frontier without one leader agent.

The protected evaluator outputs can also be converted into public-safe evidence
records:

```bash
loopx --format json auto-research evidence \
  --contract examples/auto_research_knn_pack/research_contract.json \
  --eval-result dev-result.public.json \
  --eval-result holdout-result.public.json \
  --hypothesis-id hyp_pack_partial_selection \
  --todo-id todo_auto_research_pack_001 \
  --agent-id codex-side-bypass \
  --claimed-by codex-side-bypass \
  --mechanism-family partial_selection \
  --hypothesis "Use exact partial selection to avoid full distance sorting." \
  --branch-ref codex/auto-research-evidence-writer
```

The command emits an `auto_research_evidence_packet_v0` containing one
`research_hypothesis_v0` and split-aware `research_evidence_event_v0` records.
It preserves `needs_retry`, negative evidence, protected-scope clean flags, and
branch/artifact refs while keeping raw logs, local paths, and private artifacts
out of the public payload.

Append the packet into LoopX's existing rollout event log when the evidence is
ready to become durable source state:

```bash
loopx --format json auto-research append-evidence \
  --packet auto-research-evidence-packet.public.json
```

The append step writes one `research_hypothesis` rollout event and one
`research_evidence` event per split. It skips existing event ids on retry, which
keeps heartbeat-driven lanes replayable.

## Local Demo Supervisor

The short-term multi-agent demo should be inspectable before it launches
anything. The supervisor command therefore starts as a dry-run packet: it plans
a visible tmux layout for multiple Codex CLI lanes, but it does not start tmux,
launch Codex, read session files, write LoopX state, or spend quota.

```bash
loopx --format json auto-research demo-supervisor \
  --goal-id loopx-auto-research-knn
```

The packet has two important product properties:

- the supervisor is a host shell layout, not a leader agent;
- every lane receives its own `quota should-run` and `auto-research frontier`
  command, so work routing still comes from LoopX state, todo claims, gates,
  and evidence graph projections.

Operators can pass explicit lanes when rehearsing a real local demo:

```bash
loopx --format json auto-research demo-supervisor \
  --goal-id loopx-auto-research-knn \
  --agent codex-side-bypass:hypothesis-runner \
  --agent codex-product-capability:evidence-promoter \
  --agent codex-main-control:control-plane-guard
```

### Visible Operator Rehearsal Path

The first user-facing demo step is a single inspection command, not a hidden
launcher:

```bash
loopx --format json auto-research demo-supervisor \
  --goal-id loopx-auto-research-knn \
  --agent codex-side-bypass:hypothesis-runner \
  --agent codex-product-capability:evidence-promoter \
  --agent codex-main-control:control-plane-guard
```

The user should see four concrete things in the packet:

- `mode: dry_run`, plus a boundary block showing `starts_tmux`,
  `runs_codex`, `writes_loopx_state`, and `spends_loopx_quota` are all false;
- one pane plan per digital worker lane, with that lane's own
  `quota should-run`, `auto-research frontier`, and
  `codex-cli-bootstrap-message` commands;
- a `start_script` array that can be copied into the user's shell only after
  the user sets `LOOPX_PROJECT`, `LOOPX_REGISTRY`, and
  `LOOPX_RUNTIME_ROOT`;
- explicit takeover controls: `tmux attach -t loopx-auto-research` to inspect
  every lane before accepting Codex prompts, and
  `tmux kill-session -t loopx-auto-research` to stop the rehearsal.

The safe demo acceptance bar is that the user can inspect the plan, attach to
the visible tmux session before any Codex prompt is accepted, interrupt any
lane manually, and confirm that each lane still routes through LoopX quota,
todo claims, frontier projection, and normal evidence writeback. The
supervisor never becomes a leader agent; it is only a shell layout that makes
the decentralized workers visible and interruptible.

The generated shell plan uses environment placeholders such as `LOOPX_PROJECT`,
`LOOPX_REGISTRY`, and `LOOPX_RUNTIME_ROOT` instead of embedding local absolute
paths. A future `--execute` path must remain user-visible: attach to tmux
before accepting any Codex prompt, preserve manual interrupt, and keep same-
session prompt injection blocked until visible-attach and idle evidence pass.

Next reproduction steps:

1. Keep `research_contract_v0`, `research_hypothesis_v0`, and
   `research_evidence_event_v0` as the public-safe record boundary.
2. Read `research_hypothesis` and `research_evidence` rollout events back into
   the evidence graph instead of depending on fixture-only evidence.
3. Keep one local smoke that proves:
   - protected files are not editable;
   - each hypothesis is todo-linked;
   - each evidence event names split and metric;
   - no leader agent owns the graph;
   - held-out promotion is required.
4. Build the showcase page from fixture evidence, then replace fixture numbers
   with a real run when available.

## Kernel/Capability Improvements

P0 candidates:

- **Research hypothesis ledger in core state.** Promote the existing
  `hypothesis_ledger_v0` idea from the ML domain pack into a generic,
  todo-linked research hypothesis shape.
- **Per-agent research frontier projection.** Extend status/quota projection so
  a current agent sees only claim-compatible hypotheses and promotion
  candidates, while other-agent claims remain visible context.
- **Retry semantics.** Add `needs_retry` as a reusable outcome for
  incomplete/unscored research attempts, preserving branch/evidence refs.
- **Split-aware evidence.** Make dev/held-out split labels first-class in
  evidence events and showcase projections.

P1 candidates:

- **Grounded ideation / novelty audit separation.** Add two explicit source
  lanes so research input and novelty checking cannot contaminate each other.
- **Benchmark-zoo-style pack.** Add a `loopx research scaffold` path that turns
  a small optimization task into a protected benchmark pack.
- **Replay/export surface.** Convert evidence graph events into a static HTML
  replay for public-safe showcases.

## Design Guardrails

- The control plane may select a frontier; it must not become a hidden leader.
- Agents may propose and execute hypotheses within their claim/scope.
- Promotion requires evidence and gate policy, not a persuasive chat summary.
- A user can inspect every branch of the research graph from source refs.
- Public showcase pages must distinguish "fixture target" from "achieved run".
- Private docs, internal links, raw logs, credentials, local paths, and raw
  benchmark traces stay out of public artifacts.

## Suggested Public Narrative

LoopX does for autonomous research what it already does for long-running
engineering agents: it turns a noisy loop into a managed control plane. The
novel part is that research hypotheses become first-class work items with
claims, evidence, retry state, and promotion gates. The result can look like an
Arbor-style hypothesis tree to the user, while the implementation remains
LoopX-native and decentralized.
