# SWE-Marathon vliw-kernel-optimization Launch Packet v0

Date: 2026-06-22

Purpose: define the public-safe, no-execution launch packet for the next
SWE-Marathon CPU/no-CUA case. This packet is not a scored run and must not be
used as benchmark uplift evidence.

## Boundary

This packet does not execute a benchmark task, Docker task build, Docker task
start, Codex worker, model/API call, upload, leaderboard action, submission,
credential read, raw trajectory read, screenshot, hidden reference, task
solution, or task test body.

Allowed inputs for this packet:

- public SWE-Marathon suite metadata already reduced into the full-suite status
  catalog;
- compact public benchmark ledger summaries;
- Harbor/Codex runner contract surfaces already represented in this repo;
- directory and command-shape requirements, without reading task bodies.

Forbidden inputs for this packet:

- `instruction.md` task body text;
- files under `solution/`;
- contents of files under `tests/` or `environment/`;
- raw verifier logs, trajectories, screenshots, credentials, hidden refs, or
  local private paths.

## Source Pins

- SWE-Marathon source:
  `abundant-ai/swe-marathon@0128be1c2f05fe0255dc2ffb083d503c6913486e`.
- Case catalog:
  `swe-marathon-full-suite-status-20260622.json`.

## ECS Cloud-Host Alignment

This packet is now aligned with the dedicated ECS benchmark-host route in
`docs/benchmark-developer-workflow.md`. A future cloud run should use the same
case metadata and no-upload boundary, but first prove the shared host substrate:

1. run `scripts/benchmark_ecs_bootstrap.py` on the benchmark host;
2. select the Harbor-family `swe-marathon` profile from
   `scripts/benchmark_agent_runtime_layer.py --benchmark all`;
3. use a source-locked SWE-Marathon checkout or materialized source with a
   public-safe `.loopx-upstream` marker;
4. mount the Harbor agent tools bundle rather than installing Codex or npm
   packages inside the task container;
5. reduce any launch failure with the generic Harbor reducer and
   `--benchmark-id swe-marathon`.

Do not start a new SWE-Marathon scored task from an automatic heartbeat while
the shared route still lacks a compact no-upload cloud-host result or precise
blocker from Terminal-Bench or SkillsBench.

## Candidate Metadata

| Field | Value |
| --- | --- |
| Task id | `vliw-kernel-optimization` |
| Category | `optimization` |
| Difficulty | `hard` |
| Tags | `python`, `performance`, `simd` |
| Expert estimate | `8` hours |
| Agent timeout | `28800` seconds / `8h` |
| Verifier timeout | `600` seconds / `10m` |
| Build timeout | `300` seconds / `5m` |
| CPUs | `4` |
| Memory | `16384` MB |
| Storage | `20480` MB |
| GPUs | `0` |
| Internet | `allow_internet = true` |
| CUA required | no CUA lane marker in the public catalog |

Routing verdict: suitable as the next fresh SWE-Marathon CPU/no-CUA case
because it has no prior public compact run, no GPU requirement, a short expert
estimate, and fewer attribution layers than browser/full-stack, ML-training, or
large-rewrite cases.

## Command Preview

Do not execute this command from an automatic heartbeat. It is a future launch
shape only:

```bash
harbor run -p tasks/vliw-kernel-optimization -a codex -m <approved-codex-profile> --env docker
```

The comparable LoopX treatment should use the Harbor host Codex Goal route with
the custom host agent, not a prompt-only packet. Required treatment properties:

- `reasoning_effort=high`;
- timeout envelope at least `21600` seconds and preferably matching the case
  catalog's `28800` second agent timeout;
- `loopx_*` treatment arguments only;
- isolated case-local LoopX state and todo;
- completion source of truth is no active case-local LoopX todo;
- no separate completion marker file;
- compact controller trace and rollout events for quota, todo claim/update,
  state read/write, validation, refresh, spend, and case result.

## Structured Run Permission Policy

```json
{
  "schema_version": "run_permission_policy_v0",
  "policy_id": "swe_marathon_vliw_local_no_upload_20260622",
  "allowed_actions": [
    "codex_model_invocation",
    "local_docker_runner",
    "local_harbor_runner",
    "benchmark_dependency_fetch",
    "compact_result_reduction"
  ],
  "forbidden_actions": [
    "public_result_upload",
    "leaderboard_submission",
    "public_benchmark_claim",
    "production_cloud_action",
    "credential_sync",
    "raw_artifact_publication"
  ],
  "max_wall_time_minutes": 480,
  "no_upload_required": true,
  "submit_allowed": false,
  "leaderboard_claim_allowed": false,
  "public_benchmark_claim_allowed": false,
  "production_cloud_allowed": false,
  "observation_boundary": {
    "compact_only": true,
    "raw_logs_public": false,
    "raw_task_text_public": false,
    "raw_trajectory_public": false,
    "local_paths_public": false
  },
  "operator_gate_required_for": [
    "public_result_upload",
    "leaderboard_submission",
    "public_benchmark_claim",
    "production_cloud_action",
    "credential_sync",
    "raw_artifact_publication"
  ]
}
```

This policy records the no-upload local execution boundary. It does not by
itself authorize launch from an automatic heartbeat; the stop rules below still
apply.

## No-Upload Guard

A scored local or remote pilot must:

- omit `--upload`;
- omit leaderboard/publish/submission commands;
- avoid `harbor upload`, `harbor publish`, `harbor leaderboard`, and any
  external artifact sync;
- keep artifacts local to the runner and reduce them to compact metadata before
  LoopX ingestion.

## Evidence Path

A future run should reduce output to these public-safe fields only:

- source pin, case id, resource class, route, and command shape;
- official reward or explicit verifier failure state;
- elapsed wall time and timeout class;
- setup/build/agent/verifier/result lifecycle stage;
- public-safe phase counters: edit/build/test/verify/self-declared-done and
  final active-todo count;
- LoopX control-plane counters: quota reads, todo claim/update, state reads,
  state writes, refreshes, validation checks, and boundary stops.

Do not ingest raw terminal logs, task text, diffs, trajectories, screenshots,
hidden refs, task solutions, or task test bodies.

## Stop Rules

Stop and write a precise blocker instead of launching if any of these are true:

- the run would upload, publish, submit, or touch leaderboard paths;
- the execution host cannot satisfy 4 CPUs, 16 GB memory, and 20 GB storage;
- the selected model/profile cannot be mapped to the owner-approved formal run
  setting;
- the runner would need raw credentials, task text, trajectories, hidden refs,
  solution files, or test body content;
- the treatment route cannot pass case-local `loopx_*` state/todo arguments;
- an automatic heartbeat is the only launch authority.

## Next Action

Use this packet as the handoff for the first real `vliw-kernel-optimization`
baseline/treatment run. If launch authority or host capacity is absent, record
that precise blocker and continue with public-safe SWE-Marathon phase-counter
instrumentation instead of repeating older cases.
