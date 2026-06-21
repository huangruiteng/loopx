# MLE-bench Source Preflight

Date: 2026-06-12

Scope: no-LFS, no-data source preflight for the official MLE-bench repository.
This preflight validates a safe source-surface checkout and minimal Python
checks without Kaggle credentials, Git LFS fetch/pull, dataset preparation,
Docker build/run, agent/model invocation, grading, uploads, leaderboard
submission, raw run reports, or private data.

## Source Pin

- Repository: https://github.com/openai/mle-bench
- Commit: `507f92e1138bb6e40dac5c6ee7a6758e6424bf97`

## Sparse Checkout Contract

The checkout used:

- `GIT_LFS_SKIP_SMUDGE=1`;
- `git clone --filter=blob:none --sparse --no-checkout`;
- root-anchored `--no-cone` sparse patterns.

The final checked-out source surface was `704K` and limited to:

- `README.md`
- `.gitattributes`
- `LICENSE`
- `pyproject.toml`
- `run_agent.py`
- `agents/README.md`
- `examples/README.md`
- `extras/README.md`
- `mlebench/__init__.py`
- `mlebench/cli.py`
- `mlebench/data.py`
- `mlebench/grade.py`
- `mlebench/grade_helpers.py`
- `mlebench/metrics.py`
- `mlebench/registry.py`
- `mlebench/utils.py`

The forbidden-path check passed:

- no `runs`;
- no `mlebench/competitions`;
- no `environment`;
- no checked-out `.csv`, `.json`, or `.jsonl` files outside `.git`.

This avoids the known LFS surfaces from `.gitattributes`: CSV files,
competition top solutions, and `runs/**/*.json/jsonl`.

## No-Run Validation

`python -m py_compile` passed for:

- `run_agent.py`
- `mlebench/__init__.py`
- `mlebench/cli.py`
- `mlebench/data.py`
- `mlebench/grade.py`
- `mlebench/grade_helpers.py`
- `mlebench/metrics.py`
- `mlebench/registry.py`
- `mlebench/utils.py`

`python -m mlebench.cli --help` did not reach argparse help in the bare local
environment because `mlebench.cli` eagerly imports `mlebench.data`, which
imports `diskcache`. The dependency is declared in `pyproject.toml`, but the
preflight intentionally did not install dependencies because the package also
declares heavy or gated dependencies such as `docker`, `kaggle`, `openai`,
`tensorflow`, and `pymongo`.

This is a useful wrapper finding rather than a benchmark failure: a future
LoopX MLE-bench runner should either use an isolated dependency
environment or inspect CLI syntax through source/AST until the owner approves
real setup.

## Runner Surface

The source surface confirms the main CLI commands and gates:

- `mlebench prepare` downloads and prepares competition data;
- `mlebench grade` grades a JSONL submission manifest;
- `mlebench grade-sample` grades one CSV submission for one competition;
- developer commands include leaderboard download support;
- `run_agent.py` uses Docker, agent registry entries, prepared datasets, and
  run directories.

Real execution remains gated because it requires at least one of:

- Kaggle credential access;
- dataset preparation or existing prepared data;
- Docker build/run access;
- agent/model/Codex invocation;
- grading submissions and raw reports;
- leaderboard aggregation or submission.

## Decision

MLE-bench is source-preflight ready but not execution-ready. The next
autonomous benchmark-readiness scan should move to another public candidate
unless the owner approves the Kaggle/data/compute route or a smaller explicit
MLE-bench task-material route.
