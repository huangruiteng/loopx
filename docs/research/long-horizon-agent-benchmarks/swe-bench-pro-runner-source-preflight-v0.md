# SWE-Bench Pro Runner Source Preflight

Date: 2026-06-12

Scope: sparse, no-task, no-Docker source preflight for the official
SWE-Bench Pro runner. This preflight validates that a safe runner-source slice
can be inspected without task rows, run scripts, trajectories, Docker images,
model calls, uploads, or credentials.

This preflight did not read Hugging Face task rows, persist selected instance
metadata, pull Docker images, start containers, invoke Codex or model APIs,
generate patches, evaluate patches, upload artifacts, submit to a leaderboard,
inspect raw trajectories, open screenshots, or touch credentials.

## Source Pin

- Repository: https://github.com/scaleapi/SWE-bench_Pro-os
- Commit: `ca10a60a5fcae51e6948ffe1485d4153d421e6c5`
- Dataset metadata revision from the prior readiness scan:
  `7ab5114912baf22bb098818e604c02fe7ad2c11f`

## Sparse Checkout Contract

The final safe checkout used blob filtering plus root-anchored non-cone sparse
patterns. The checked-out repository files were limited to:

- `README.md`
- `.gitmodules`
- `LICENSE`
- `requirements.txt`
- `swe_bench_pro_eval.py`
- `helper_code/create_problem_statement.py`
- `helper_code/gather_patches.py`
- `helper_code/generate_sweagent_instances.py`
- `helper_code/image_uri.py`

The preflight also found a guardrail issue worth preserving: Git's default
cone-mode sparse checkout is too broad for this benchmark. A first sparse
attempt that named helper files still materialized additional helper data,
including gold/task-related helper paths. Their contents were not read, but the
event proves future automation should use root-anchored `--no-cone` patterns
or an allowlist post-check before any benchmark source sync is trusted.

Final forbidden-path checks passed after tightening the sparse patterns:

- no `run_scripts`;
- no `traj`;
- no `data`;
- no `error_analysis`;
- no `helper_code/sweap_eval_full_v2.jsonl`;
- no `helper_code/extract_gold_patches.py`.

## No-Run Validation

The no-task source slice passed Python compile checks for:

- `swe_bench_pro_eval.py`
- `helper_code/create_problem_statement.py`
- `helper_code/gather_patches.py`
- `helper_code/generate_sweagent_instances.py`
- `helper_code/image_uri.py`

`python swe_bench_pro_eval.py --help` succeeded without Docker, Modal
credentials, task rows, run scripts, or patch files. The help output confirms
that real evaluation requires:

- `--raw_sample_path`;
- `--patch_path`;
- `--output_dir`;
- `--dockerhub_username`;
- `--scripts_dir`;
- optional `--use_local_docker`;
- optional `--docker_platform`;
- optional `--block_network`.

Runner source inspection confirms the local-Docker path pulls
`jefzda/sweap-images`-style images through the Docker SDK and then starts a
container. Therefore help/compile is the correct no-task stopping point; any
real invocation needs a selected public instance row, local run scripts, patch
JSON, Docker image access, and an explicit no-upload execution approval.

## Decision

SWE-Bench Pro is now source-preflight ready but task-row gated. The safe next
SWE-Bench Pro step is not another source scan; it is owner approval for one
public task-material route, followed by a one-instance launch packet that
selects a compact public instance, pins its Docker tag, estimates image size,
and keeps Codex auth local.

Until that approval exists, autonomous benchmark-readiness work should move to
the next benchmark candidate rather than selecting a SWE-Bench Pro instance.
