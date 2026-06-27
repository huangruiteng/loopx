# Auto Research k-NN Pack

This public pack is a tiny LoopX-native reproduction target for decentralized
auto research. It turns the fixture-only k-NN showcase into something an agent
can actually run:

- editable solver: `solution_candidate.py`;
- protected evaluator and data generation: `protected_eval.py`;
- baseline solver: `solution_baseline.py`;
- public contract: `research_contract.json`;
- deterministic dev and holdout splits.

The task is exact brute-force k-nearest-neighbor inference. A candidate may
change only the editable solver. The evaluator owns the data, exactness oracle,
metric, and promotion gate.

## Commands

Baseline:

```bash
python3 examples/auto_research_knn_pack/protected_eval.py \
  --solution examples/auto_research_knn_pack/solution_baseline.py \
  --split dev
```

Candidate:

```bash
python3 examples/auto_research_knn_pack/protected_eval.py \
  --solution examples/auto_research_knn_pack/solution_candidate.py \
  --split holdout
```

Smoke:

```bash
python3 examples/auto-research-knn-pack-smoke.py
```

## Metric

The primary metric is deterministic protected speedup. The evaluator compares
the baseline full-sort ranking work against the candidate's declared exact
partial-selection ranking work. It still checks exact neighbor identities on
every query before reporting an improved score.

This avoids timing flake while preserving the product point: an autonomous
research lane can produce dev evidence, holdout evidence, negative evidence, and
a promotion decision without a leader agent mutating the whole graph.
