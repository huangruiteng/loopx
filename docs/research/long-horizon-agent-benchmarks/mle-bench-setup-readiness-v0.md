# MLE-bench Setup Readiness

Date: 2026-06-12

Scope: public-safe setup-readiness scan for MLE-bench. This scan used the
official repository metadata, official README, public split metadata, and
public leaderboard text. It stopped before Kaggle credential use, Git LFS
fetch, dataset preparation, Docker build/run, agent/model invocation, grading,
uploads, leaderboard submission, raw run reports, and private data.

## Public Sources

- Official repository: https://github.com/openai/mle-bench
- Paper: https://arxiv.org/abs/2410.07095
- README leaderboard and setup guide:
  https://github.com/openai/mle-bench/blob/main/README.md
- Lite split source:
  https://github.com/openai/mle-bench/blob/main/experiments/splits/low.txt

## Difficulty And Codex Signal

MLE-bench remains a strong long-horizon benchmark, but it is no longer a
low-score-only frontier in the public leaderboard. The benchmark covers 75
Kaggle competitions and asks agents to perform machine-learning engineering
under competition-style constraints.

Current public leaderboard evidence includes:

- top listed main-table result: `Famou-Agent 2.0` with
  `Gemini-3-Pro-Preview`, `64.44%` All;
- `Thesis` with `gpt-5-codex`, `65.15%` Low/Lite and `48.44%` All;
- older baseline-like rows from the original paper period remain much lower,
  such as OpenHands with `gpt-4o-2024-08-06` at `4.89%` All and MLAB with
  `gpt-4o-2024-08-06` at `1.60%` All.

This is useful for LoopX only if the experiment question is about
long-horizon ML workflow management, artifact discipline, data/compute
planning, and failure attribution. It is less ideal if the immediate goal is a
cheap local Codex CLI win/loss signal, because public SOTA has climbed and the
full evaluation budget is large.

There is a direct `gpt-5-codex` public leaderboard row, but no direct
`codex` CLI score was found in this scan. Treat the `Thesis` row as a
Codex-model-in-agent result, not a host Codex CLI runner result.

## Setup Findings

Source transport is healthy:

- `git ls-remote https://github.com/openai/mle-bench.git HEAD` resolved to
  `507f92e1138bb6e40dac5c6ee7a6758e6424bf97`;
- GitHub API returned HTTP 200 for the repository and root contents;
- repository metadata reports `openai/mle-bench`, public visibility, default
  branch `main`, latest push timestamp `2026-04-24T17:33:44Z`, and no asserted
  SPDX license in the GitHub API response;
- the root contains `agents`, `environment`, `examples`, `experiments`,
  `extras`, `mlebench`, `run_agent.py`, `runs`, and `tests`;
- the Git tree API returned a non-truncated tree with `1262` paths;
- `pyproject.toml` defines package `mlebench`, Python `>=3.11`, console script
  `mlebench = mlebench.cli:main`, and dependencies including `docker`,
  `kaggle`, `openai`, `tensorflow`, `pandas`, `fastparquet`, and `pymongo`;
- `.gitattributes` marks CSV files, top solutions, and `runs/**/*.json/jsonl`
  as Git LFS-managed.

The setup is heavy and not heartbeat-runnable by default:

- canonical benchmark resources are 24 hours, 36 vCPUs, 440 GB RAM, and one
  24 GB A10 GPU;
- the full dataset is described as 75 Kaggle competitions;
- the README says preparing from scratch can take two days;
- full dataset size is described as about `3.3 TB`;
- the Lite/Low split is still about `158 GB`;
- data preparation requires Kaggle credentials in the Kaggle API's default
  credential location;
- the environment uses a Docker image built from `environment/Dockerfile`;
- the public leaderboard is temporarily closed to new submissions while the
  maintainers improve their comparability process.

The lite split file has 22 non-empty entries. A naive `wc -l` returns 21
because the final line has no trailing newline, so future automation should
count non-empty lines rather than line breaks.

## Execution Boundary

Do not run MLE-bench from heartbeat automation until separately approved.
Stop before:

- Git LFS fetch or pull;
- `mlebench prepare --all`, `--lite`, or `-c <competition-id>`;
- reading or writing Kaggle credentials;
- Kaggle API dataset download;
- Docker build or container start;
- agent/model/Codex invocation;
- grading submissions;
- reading raw run reports or LFS-managed `runs/**/*.json/jsonl`;
- upload, leaderboard submission, private data, hidden references, screenshots,
  or raw trajectories.

## Decision

MLE-bench is source-visible and useful as a long-horizon ML engineering
benchmark, but it is resource- and credential-gated for real runs. The next
safe autonomous step is a no-LFS/no-data source preflight that inspects only
the CLI and package surface, verifies a sparse checkout can avoid LFS-managed
run/data artifacts, and stops before any Kaggle, Docker, or model action.
