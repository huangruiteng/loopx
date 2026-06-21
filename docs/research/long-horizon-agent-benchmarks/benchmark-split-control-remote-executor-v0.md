# Benchmark Split-Control Remote Executor V0

Status: readiness contract + launch-plan contract + runner-batch contract +
smoke-tested public gate.

This contract defines the benchmark route used when Codex and LoopX stay
on the local trusted machine while a remote development host provides Docker,
runner dependencies, task-data staging, bounded command execution, and compact
result reduction.

## Boundary

Local agent owns:

- Codex CLI and Codex auth;
- LoopX state, quota, todo projection, and writeback;
- model invocation, planning, and patch generation;
- public/private filtering before any artifact becomes durable.

Remote executor owns:

- Docker/container runtime;
- benchmark runner dependencies;
- task-data or image staging;
- bounded command/file execution requested by the local agent;
- compact result reduction that does not expose raw task text, trajectories,
  verifier logs, credentials, uploads, or submit paths.

The remote host must not be treated as an agent-auth environment. Missing
remote `codex`, `codex-acp`, or model credentials is a diagnostic fact, not a
cross-benchmark blocker. A benchmark is blocked only by one of the actual
split-control gates:

- local agent not ready;
- remote executor base missing;
- split-control adapter missing;
- remote runner tooling missing;
- task data or image missing;
- remote node runtime missing only when a specific runner declares that it
  requires remote Node/npm.

The gate is a matrix, not a single all-or-nothing flag. When at least one
benchmark family is ready, `readiness_matrix.next_ready_batch_benchmark_ids`
selects the bounded launch subset while `readiness_matrix.next_repair_target`
names the first blocked family to repair. This lets the controller run a small
parallel batch such as Terminal-Bench plus SkillsBench while ALE remains
task-data-gated, without pretending the whole three-benchmark rotation is
ready.

## Launch Plan V0

`build_split_control_remote_executor_launch_plan(...)` turns a readiness matrix
into a non-executing launch packet:

- `launch_cases` contains only ready benchmark families, with a compact command
  label rather than a shell script or raw runner command.
- each launch case requires a fresh readiness re-check and compact evidence
  writeback before any score or uplift claim.
- `third_gate` keeps ALE provider/task-data validation visible when Terminal
  Bench and SkillsBench are launchable but ALE is not.
- `post_launch_evidence_contract` names the public-safe fields a later runner
  must report: benchmark id, route, readiness re-check, compact result or
  blocker, and explicit no raw material/upload/submit flags.

The launch plan is still a control-plane artifact. It does not execute remote
commands, copy credentials, read task bodies, expose raw logs, or grant upload
or submit rights.

## Runner Batch V0

`build_split_control_remote_executor_runner_batch(...)` is the narrow bridge
from a launch packet to runner execution:

- it requires a fresh readiness payload before producing any `runner_cases`;
- if a planned benchmark is no longer in the fresh ready batch, it blocks with
  `fresh_readiness_recheck_changed` instead of executing a stale launch case;
- each runner case keeps Codex/auth/model ownership local and allows the remote
  executor only dependency checks, bounded command execution, and compact
  result reduction;
- post-launch evidence keeps only compact result fields and records raw-key or
  unsafe-flag violations without copying raw values.

This keeps the benchmark runner interface close to the real split-control
route while avoiding a second benchmark harness that hides stale readiness,
raw logs, task text, uploads, or submit attempts.

## Execution Seam V1

`build_split_control_remote_executor_execution_seam(...)` adds the missing
product layer between a runner batch and real execution. A runner batch can say
that a benchmark family is ready in principle; the execution seam says whether
that family has a command adapter and compact result reducer that can actually
materialize a bounded no-upload run.

The seam records only labels and handle contracts:

- command adapter readiness and blocker labels;
- result reducer readiness and accepted compact fields;
- required public handle shape such as runner handle, poll label, cleanup
  label, readiness re-check, and compact artifact ref;
- explicit proof that shell commands, argv, local paths, remote paths, raw task
  text, logs, trajectories, uploads, and submit paths are not embedded.

This prevents the controller from treating a control-plane launch packet as a
real runnable benchmark route. Missing command adapters or reducers remain
first-class blockers until a benchmark family exposes a public-safe execution
surface.

## Current Use

The same route applies to the three active benchmark families:

- Terminal-Bench: local Codex/LoopX drives the attempt; the remote side
  supplies Docker, Harbor or a runner wrapper, and compact result ingestion.
- SkillsBench: local Codex/LoopX drives the attempt; the runner must no
  longer assume Codex ACP starts inside the remote worker before a
  split-control adapter exists. The current public adapter surface is a
  local-driver/A2A contract: Codex auth, model invocation, LoopX state,
  and raw reasoning stay local; the remote executor owns Docker, BenchFlow task
  data, bounded command execution, cleanup, and compact result reduction. A
  no-upload mini-pair is not launch-ready until the local Codex A2A participant
  is materialized.
- Agents' Last Exam: local Codex/LoopX and local auth remain trusted;
  the remote side handles Docker, source/task-data staging, CUA/provider
  capacity where applicable, and compact result reduction.

## Validation

Run:

```bash
python3 examples/benchmark-split-control-remote-executor-smoke.py
```

The smoke asserts that missing remote Codex/Codex-ACP is non-blocking, while
adapter, runner-tooling, and task-data blockers remain explicit. It also checks
that a partial-ready route can produce a launchable subset, a concrete repair
target, a public-safe non-executing launch plan, and a runner batch that refuses
to execute without a fresh readiness re-check.
