# decentralized_auto_research_state_v0

`decentralized_auto_research_state_v0` is a LoopX protocol for running
autonomous research without introducing a single leader agent. It borrows the
useful parts of Arbor's public design, especially durable hypothesis state,
worktree isolation, dev/held-out evaluation, and replayable evidence, but maps
them onto LoopX's shared control plane: todos, claims, quota, run history,
rollout events, gates, and read-only projections.

The goal is to let multiple agents explore research hypotheses in parallel
while preserving provenance, ownership, and promotion rules. No agent owns the
whole research tree. The source of truth is the append-only state graph; each
agent sees a scoped frontier through `quota should-run --agent-id ...`.

## Arbor Signals To Preserve

Primary public Arbor surfaces reviewed:

- `README.md`: Arbor frames the work as autonomous research through
  hypothesis-tree refinement, with a Coordinator, Executors, worktrees,
  held-out validation, reports, replay, and a benchmark zoo.
- `docs/how-it-works.md`: the six-step cycle is observe, ideate, select,
  experiment, evaluate, backpropagate, then merge or prune.
- `src/coordinator/idea_tree.py`: each node records hypothesis, status,
  insight, result, score split, test score, branch ref, grounding,
  related-work audit, eval status, stop reason, and attempt count.
- `src/coordinator/tools/executor_run.py`: executor outcomes distinguish
  scored success from `needs_retry` for timeout, max-turn, eval-crash, or
  unparseable reports, while preserving branch/report/diff for continuation.
- `docs/search.md`: grounded ideation and novelty audit are separate lanes;
  text fetched to inspire an idea is not reused to certify novelty.
- `arbor-zoo/algotune_knn`: the showcase benchmark packages an editable
  solver, protected harness, dev/test split, provenance, and one `score:` line.

LoopX should preserve these product lessons, not Arbor's centralized topology.

## Non-Goals

- Do not add a LoopX-wide "research director" agent that owns all planning.
- Do not replace todos, run history, or rollout events with a second research
  database.
- Do not let a showcase dashboard mutate source state.
- Do not treat an advisory grounded-search result as proof of novelty.
- Do not merge or publish a research result without held-out evidence or an
  explicit gate when the boundary requires one.

## Source Protocol

Source state is writable only through LoopX lifecycle commands, project-owned
state files, or future narrow kernel APIs.

The companion
[`auto_research_lane_contract_v1`](auto-research-lane-contract-v1.md) defines
which decentralized agent lanes may create, execute, evaluate, promote, retire,
or narrate these records. This file defines the record shapes and projections;
the lane contract defines capability ownership without introducing a leader
agent.

| Source state | Existing or proposed anchor | Purpose |
| --- | --- | --- |
| `research_contract_v0` | proposed packet, registry goal metadata | Public-safe objective, editable scope, protected scope, metric direction, dev/held-out commands, budget, and stopping condition. |
| `todo_item_v0` | `loopx todo` | Formal executable work, user gate, blocker, or monitor. Research work remains todo-backed. |
| `research_hypothesis_v0` | proposed rollout event and optional domain pack | A hypothesis node linked to a todo, parent hypothesis, agent lane, mechanism family, and current status. |
| `research_evidence_event_v0` | proposed `loopx_rollout_event_v0` specialization | Append-only evidence for an attempt: score, split, command label, branch, artifact refs, eval status, and boundary facts. |
| `dataset_window_contract_v0` | `loopx/ml_experiment.py` | Train/dev/held-out window or split contract, including missing-window policy. |
| `agent_lane_next_action_v0` | `quota should-run --agent-id ...` | The current agent's selected frontier item; it does not replace the global state graph. |
| `operator_gate` | `loopx operator-gate`, review packet | Promotion, merge, private-material, or showcase-publication decision. |
| `human_reward` | `loopx reward` | Run-bound owner judgment, not general write permission. |

### `research_contract_v0`

```json
{
  "schema_version": "research_contract_v0",
  "goal_id": "loopx-meta",
  "research_objective": "optimize a benchmark task under a protected evaluator",
  "editable_scope": ["solution.py"],
  "protected_scope": ["eval.py", "task.py", "data/**"],
  "metric": {"name": "speedup", "direction": "maximize"},
  "dev_eval": {"label": "eval_dev", "command_label": "bash eval.sh dev"},
  "holdout_eval": {"label": "eval_test", "command_label": "bash eval.sh test"},
  "promotion_policy": "requires_holdout_improvement_and_clean_boundary",
  "budget": {"max_attempts": 8, "max_parallel_lanes": 3}
}
```

### `research_hypothesis_v0`

```json
{
  "schema_version": "research_hypothesis_v0",
  "goal_id": "loopx-meta",
  "hypothesis_id": "hyp_0004",
  "parent_hypothesis_id": "hyp_0002",
  "todo_id": "todo_123",
  "lane_id": "agent:codex-side-bypass",
  "claimed_by": "codex-side-bypass",
  "mechanism_family": "vectorized_distance_kernel",
  "hypothesis": "Batch query points through a shared index to reduce per-query overhead.",
  "status": "active",
  "frontier_rank": 2,
  "source_refs": ["research_contract:knn_speedup"],
  "grounding_refs": [],
  "novelty_audit_ref": null
}
```

Status vocabulary:

| Status | Meaning |
| --- | --- |
| `proposed` | Drafted but not yet accepted into executable work. |
| `active` | Runnable frontier item, normally backed by an open agent todo. |
| `running` | Claimed attempt is in progress. |
| `needs_retry` | Attempt produced no trustworthy score but left resumable evidence. |
| `supported` | Dev evidence supports the hypothesis; not yet promoted. |
| `contradicted` | Evidence shows regression or guardrail failure. |
| `promoted` | Held-out evidence and promotion policy accepted it into the current best artifact. |
| `retired` | No longer worth exploring, but retained as negative evidence. |

### `research_evidence_event_v0`

```json
{
  "schema_version": "research_evidence_event_v0",
  "goal_id": "loopx-meta",
  "hypothesis_id": "hyp_0004",
  "todo_id": "todo_123",
  "agent_id": "codex-side-bypass",
  "attempt": 1,
  "split": "dev",
  "metric": {"name": "speedup", "value": 11.4, "direction": "maximize"},
  "baseline_metric": 8.7,
  "primary_metric_status": "improved",
  "eval_status": "scored",
  "code_ref": "codex/research-hyp-0004",
  "artifact_refs": ["experiment:hyp_0004/report", "diff:hyp_0004"],
  "protected_scope_clean": true,
  "private_artifacts_recorded": false,
  "raw_logs_recorded": false
}
```

`needs_retry` is first-class evidence, not a generic failure:

```json
{
  "schema_version": "research_evidence_event_v0",
  "hypothesis_id": "hyp_0005",
  "eval_status": "failed_to_run",
  "stop_reason": "max_turns",
  "attempt": 1,
  "code_ref": "codex/research-hyp-0005",
  "resume_policy": "resume_from_code_ref_or_retire",
  "primary_metric_status": "inconclusive"
}
```

## Projection Protocol

Projection state is read-only. It may rank frontiers for display, but it must
carry source refs and remain recomputable from source state.

| Projection | Purpose |
| --- | --- |
| `decentralized_research_frontier_v0` | Per-agent queue of runnable or blocked hypotheses after quota, claim, capability, and boundary checks. |
| `research_evidence_graph_v0` | Read-only graph joining hypotheses, todos, attempts, branches, metrics, gates, and promotion decisions. |
| `research_showcase_projection_v0` | Public-safe view for a case page: objective, baseline, best result, attempt timeline, dev/held-out split, and reusable LoopX pattern. |

### `decentralized_research_frontier_v0`

```json
{
  "schema_version": "decentralized_research_frontier_v0",
  "goal_id": "loopx-meta",
  "agent_id": "codex-side-bypass",
  "selected": {
    "hypothesis_id": "hyp_0004",
    "todo_id": "todo_123",
    "reason": "current-agent claim and dev evidence gap",
    "allowed_action": "run_dev_attempt"
  },
  "blocked": [
    {
      "hypothesis_id": "hyp_0002",
      "blocked_by": "claimed_by:codex-product-capability",
      "visible_as_context": true
    }
  ],
  "promotion_candidates": [
    {
      "hypothesis_id": "hyp_0004",
      "requires": ["holdout_eval", "boundary_scan"]
    }
  ]
}
```

This projection intentionally replaces a centralized Coordinator decision. The
kernel selects only what the current agent may attempt; the agent still does
semantic implementation within its allowed boundary.

## Decentralized Cycle

Arbor's cycle maps to LoopX as a distributed control loop:

| Arbor concept | LoopX decentralized equivalent |
| --- | --- |
| Observe | Agent reads `quota should-run`, active state, selected frontier, evidence graph, and relevant source docs. |
| Ideate | Any authorized lane may propose `research_hypothesis_v0` as a todo-backed candidate. |
| Select | `quota should-run --agent-id` filters by claim, gate, capability, and boundary. |
| Dispatch | The selected agent works in its own worktree and writes evidence. |
| Backpropagate | A deterministic projection summarizes supported/contradicted lessons into the evidence graph; no single agent rewrites global truth. |
| Decide | Promotion policy plus operator gates decide merge, retire, retry, or continue. |

## Search Lanes

LoopX should adopt Arbor's separation of search lanes:

| Lane | When | Authority | Writes |
| --- | --- | --- | --- |
| `grounded_ideation` | Before or during hypothesis proposal | Advisory input to a candidate hypothesis. | `grounding_refs` on the hypothesis. |
| `novelty_audit` | After a hypothesis has real evidence | Advisory contribution/overlap check. | `novelty_audit_ref` and evidence note. |

The two lanes must not share fetched text as proof. If a source shaped the idea,
it can be cited as grounding, but a later novelty audit must run an independent
source pass before claiming novelty.

## Promotion Policy

A research hypothesis is promotable only when:

1. the editable/protected scope boundary is clean;
2. dev evidence is scored and public-safe;
3. held-out evidence satisfies the metric direction and margin;
4. required user/controller gates are resolved;
5. the promoted artifact has a branch or commit ref;
6. the evidence graph records negative evidence for close alternatives.

Promotion is a state transition, not a chat conclusion. It should write a
todo completion, evidence event, and optional promotion gate/reward overlay.

## Integration With Existing LoopX

Already available:

- `todo_item_v0` has claims, task classes, action kinds, blockers, user gates,
  and resume conditions.
- `agent_lane_next_action_v0` scopes work per registered agent.
- `loopx/ml_experiment.py` already has `hypothesis_ledger_v0`,
  `dataset_window_contract_v0`, and advisory result packets.
- `long_horizon_agent_state_protocol_v0` already defines source/projection
  separation and concurrent lane views.
- `loopx auto-research frontier --fixture <public.json> --agent-id <agent>`
  now renders a fixture-backed `decentralized_research_frontier_v0`,
  `research_evidence_graph_v0`, and `research_showcase_projection_v0` without
  launching experiments or depending on a leader agent.
- `loopx auto-research frontier --goal-id <goal> --agent-id <agent>` now
  renders a live todo/quota-backed frontier for the current agent from LoopX
  status projection.
- `examples/auto_research_knn_pack/` now provides a runnable public k-NN pack
  with an editable candidate solver, protected evaluator, dev/held-out splits,
  exactness guard, deterministic speedup metric, no-upload boundary, and smoke
  coverage.
- `loopx auto-research evidence --contract <research_contract.json>
  --eval-result <eval.json>...` now builds an
  `auto_research_evidence_packet_v0` containing a public-safe
  `research_hypothesis_v0` and split-aware `research_evidence_event_v0`
  records. It preserves `needs_retry`, negative evidence,
  `protected_scope_clean`, and branch/artifact refs without recording raw logs
  or private artifacts.
- `loopx auto-research append-evidence --packet <packet.json>` appends that
  packet into the existing `loopx_rollout_event_v0` log as one
  `research_hypothesis` event plus one `research_evidence` event per split.
  Re-running the same packet skips existing event ids, so heartbeat retries do
  not duplicate evidence.
- `loopx auto-research frontier --goal-id <goal> --agent-id <agent>` reads
  `research_hypothesis` and `research_evidence` rollout events back into
  `research_evidence_graph_v0` and derives promotion/retirement candidates for
  the live frontier and showcase projection.

Needed next:

- render the lane contract, per-agent frontier, promotion candidates, retirement
  candidates, and retry candidates in a non-first-screen product board;
- add a public showcase page that reports baseline, dev result, held-out
  result, retired directions, and LoopX's decentralized coordination pattern.

## Acceptance Checks

An implementation is acceptable when:

- no single agent is required to own or mutate the full hypothesis graph;
- every executable hypothesis is linked to a todo and claim;
- per-agent frontier selection is derived from quota/status, not chat memory;
- `needs_retry` keeps resumable evidence instead of collapsing into `done`;
- grounded ideation and novelty audit are separated;
- held-out promotion is explicit;
- public projections contain no raw logs, private paths, credentials, or raw
  internal documents;
- the showcase can be rendered from public-safe evidence refs.
