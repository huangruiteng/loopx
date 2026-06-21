# Codex App Parity Posthoc Check V0

This note defines a lightweight posthoc check for benchmark treatment rows that
claim to approximate the Codex App plus LoopX product path.

The check reads only compact `benchmark_run_v0` JSON. It must not read raw task
text, raw logs, raw trajectories, verifier output, credentials, local private
paths, screenshots, or benchmark submissions.

## Purpose

Benchmark treatment runs can be useful even when they are only product-mode
surrogates. The posthoc check makes that distinction explicit before we make
uplift or regression claims.

The check answers:

- Was a canonical case goal state visible, using
  `/app/.codex/goals/<case-goal-id>/ACTIVE_GOAL_STATE.md`?
- Was that state initialized before the in-case agent started?
- Is there compact evidence of LoopX CLI calls such as `status`,
  `quota_should_run`, `todo_list`, `history`, and `check`?
- Is there a public-safe Codex CLI trajectory summary or equivalent compact
  controller trace?
- Did the compact row avoid reward feedback, verifier output, raw task text,
  raw trajectories, credentials, and local private paths?

## CLI

```bash
loopx benchmark parity-check \
  --benchmark-run-json <compact-benchmark-run-v0.json>
```

Use `--format json` for batch processing. The output is
`benchmark_codex_app_parity_posthoc_check_v0`.

## Claim Policy

- `full_product_path_evidence_present`: enough compact evidence exists to treat
  the row as a close product-path run for attribution purposes.
- `product_mode_surrogate_missing_posthoc_evidence`: the row may still be useful,
  but uplift/regression should be described as a surrogate result and the missing
  evidence must be listed.
- `baseline_or_ablation_no_product_claim`: the row is not attempting a product
  path claim.
- `unsafe_or_leaky_artifact`: do not use the row for product-path attribution
  until the leakage or raw-material issue is fixed.

## Validation

```bash
python3 examples/benchmark-codex-app-parity-posthoc-smoke.py
```

