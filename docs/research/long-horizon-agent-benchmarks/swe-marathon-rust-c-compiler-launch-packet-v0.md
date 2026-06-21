# SWE-Marathon rust-c-compiler Launch Packet v0

Date: 2026-06-12

Purpose: define the smallest public-safe, no-execution launch packet for the
first SWE-Marathon CPU shell-only pilot candidate. This packet is not a scored
run and must not be used as proof of benchmark uplift.

## Boundary

This packet does not execute a benchmark task, Docker task build, Docker task
start, Codex worker, model/API call, upload, leaderboard action, submission,
credential read, raw trajectory read, screenshot, hidden reference, task
solution, or task test body.

Allowed inputs for this packet:

- official source pins and runner docs;
- task-level `task.toml` fields needed for routing;
- directory and filename existence checks;
- Harbor CLI help surfaces already captured in the setup-readiness preflight.

Forbidden inputs for this packet:

- `instruction.md` task body text;
- files under `solution/`;
- contents of files under `tests/` or `environment/`;
- raw verifier logs, trajectories, screenshots, credentials, or hidden refs.

## Source Pins

- SWE-Marathon source:
  `abundant-ai/swe-marathon@0128be1c2f05fe0255dc2ffb083d503c6913486e`.
- Harbor fork:
  `RishiDesai/harbor@7bfd77d79de43faec698fb8aba1c1a8f8fc23196`.
- Harbor CLI preflight:
  `harbor --version` returned `0.13.1`; `harbor run --help` exposes `codex`
  as an allowed `--agent/-a` value; upload is explicit through `--upload`.

## Candidate Metadata

| Field | Value |
| --- | --- |
| Task id | `rust-c-compiler` |
| Category | `systems` |
| Difficulty | `hard` |
| Tags | `rust`, `compiler`, `c`, `codegen`, `x86-64` |
| Expert estimate | `30` hours |
| Agent timeout | `21600` seconds / `6h` |
| Verifier timeout | `2400` seconds / `40m` |
| Build timeout | `1200` seconds / `20m` |
| CPUs | `4` |
| Memory | `16384` MB |
| Storage | `20480` MB |
| GPUs | `0` |
| Internet | `allow_internet = true` |
| CUA required | no CUA marker in task metadata |
| Declared grader restore path | `artifacts/compiler` to `/app/compiler` |

Routing verdict: suitable as the first SWE-Marathon launch-packet candidate
because it is CPU-only, has no CUA marker, and is the official README example.

## Directory-Level Material Check

Observed top-level task entries:

- `task.toml`
- `instruction.md`
- `environment/`
- `tests/`
- `solution/`

Observed environment filenames:

- `Dockerfile`
- `filter.json`
- `run_tests.py`
- `run_tests.sh`
- `utils.py`

Observed tests filenames:

- `filter.json`
- `run_tests.py`
- `test.sh`
- `utils.py`

Only names were inspected for `environment/` and `tests/`. File contents remain
out of scope for this packet.

## Command Preview

Do not execute this command from a heartbeat. It is a future launch shape only:

```bash
harbor run -p tasks/rust-c-compiler -a codex -m openai/gpt-5.5 --env docker
```

Before a real run, resolve these open fields:

- whether the model string maps to the owner's intended formal
  `5.5-xhigh` profile in the local Codex/Harbor configuration;
- whether the run should use benchmark-managed Codex or a host-authorized
  Codex CLI bridge;
- where compact `benchmark_run_v0` and `benchmark_result_v0` artifacts will be
  written;
- whether local Docker/Colima capacity can satisfy 4 CPUs, 16 GB memory, and
  20 GB storage without evicting other work.

## No-Upload Guard

Harbor exposes upload as an explicit `--upload` option. A local pilot must:

- omit `--upload`;
- omit leaderboard/publish/submission commands;
- avoid `harbor upload`, `harbor publish`, `harbor leaderboard`, and any
  external artifact sync;
- keep artifacts local and reduce them to compact metadata before LoopX
  ingestion.

## LoopX Evidence Path

A future approved run should reduce output to these compact fields only:

- source pins and command shape;
- task id and resource class;
- official reward or explicit verifier failure state;
- partial metric summary when produced by the official verifier;
- elapsed wall time and timeout class;
- failure taxonomy: setup, Docker, agent, model, verifier, resource, boundary,
  or reward;
- LoopX control-plane counters: status reads, todo reads, state writes,
  validation checks, restarts, stale-state avoidance, and boundary stops.

Do not ingest raw terminal logs, trajectories, screenshots, hidden refs, task
solutions, or task test bodies.

## Stop Rules

Stop and do not spend benchmark execution quota if any of these are true:

- Harbor would run with `--upload` or any publish/leaderboard path.
- The task requires GPU, CUA, paid cloud, or external credentials not already
  approved for this benchmark lane.
- The selected model/profile cannot be mapped to the owner-approved formal run
  setting.
- Docker/Colima cannot satisfy the declared CPU, memory, or storage envelope.
- The runner requires reading credentials, raw trajectories, screenshots,
  hidden refs, task solution content, or task test body content.
- The command would start `harbor run -p ...` from an automatic heartbeat
  without a fresh explicit execution decision.

## Next Action

Run a no-execution provider/capacity preflight for the local Docker path:

1. check Docker/Colima availability and capacity without starting the
   SWE-Marathon task image;
2. confirm the Harbor command can be represented as a no-upload plan;
3. produce a compact approval packet for the first actual baseline/treatment
   run, or write a blocker if local capacity is insufficient.
