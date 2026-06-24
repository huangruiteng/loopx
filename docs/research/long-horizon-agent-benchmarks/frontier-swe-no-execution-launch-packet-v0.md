# FrontierSWE No-Execution Launch Packet v0

Date: 2026-06-24

Purpose: define the public-safe launch packet FrontierSWE must satisfy before
any scored ECS benchmark-host run. This packet is a readiness and blocker
surface only; it is not benchmark uplift evidence.

## Boundary

This packet does not execute a benchmark task, Docker build, Docker container,
Codex worker, model/API call, upload, leaderboard action, submission, credential
read, raw trajectory read, screenshot, hidden reference, task solution, or task
test body.

Allowed inputs for this packet:

- public FrontierSWE setup-readiness notes already in this repository;
- public repository shape from the setup-readiness scan;
- shared ECS benchmark-host workflow contracts;
- Harbor-family runner contracts used by SWE-Marathon and Terminal-Bench;
- command shape and stop conditions, without reading task bodies.

Forbidden inputs for this packet:

- private task prompts or instructions;
- hidden tests, solutions, reference implementations, raw verifier output, raw
  trajectories, screenshots, credentials, local private paths, or host run
  directories;
- upload-capable artifacts, leaderboard submissions, or public score claims.

## Source And Runner Contract

| Field | Value |
| --- | --- |
| Benchmark id | `frontier-swe` |
| Public source | `Proximal-Labs/frontier-swe` |
| Runner family | Harbor-family / Docker-heavy SWE route |
| ECS route | dedicated benchmark host with Codex CLI, Docker, benchmark source, task data, private artifacts, and compact reducers colocated |
| Current launch readiness | blocked before scored execution |
| First blocker | `frontier_swe_source_commit_unpinned_on_benchmark_host` |

The first cloud-host action is source pinning, not task launch. A future run
must record a public-safe source lock with the upstream repo, commit, clean
status, runner entrypoint, and whether a wrapper or upstream patch is needed.
If a patch is needed, it must follow the Remote Checkout Patch Protocol in
`docs/benchmark-developer-workflow.md` and prove that scorer, task truth,
prompts, hidden references, and official result parsing were not changed.

FrontierSWE should inherit the Harbor-family ECS workflow shape:

1. Run `scripts/benchmark_ecs_bootstrap.py` on the benchmark host.
2. Select the `swe-marathon` / Harbor-family profile from
   `scripts/benchmark_agent_runtime_layer.py --benchmark all`.
3. Materialize the benchmark source into `loopx-bench/sources/` and record a
   source lock.
4. Produce a task inventory summary without reading task bodies.
5. Choose at most one cheap smoke candidate, then stop for operator launch
   authority.

## Task Inventory Gate

The task inventory must be compact and public-safe. It may include counts and
metadata categories, but must not include task instructions, hidden references,
solutions, raw tests, verifier output, or private paths.

Required inventory fields before any launch:

- task count;
- task id allowlist for the first candidate;
- resource lane: CPU, GPU, browser/CUA, network, and expected wall time bucket;
- runner entrypoint and Docker/backend requirement;
- no-upload/no-submit command shape;
- result reducer or precise blocker reducer;
- whether official result parsing is already understood;
- whether the first task can be run without Prime Intellect, external upload,
  leaderboard publication, or non-public credential material.

If these fields cannot be produced from public metadata and source structure,
the run must close as `frontier_swe_task_inventory_unavailable` rather than
starting a task.

## Command Preview

Do not execute this command from an automatic heartbeat. It is a future command
shape only, after source and task-inventory gates are satisfied:

```bash
harbor run -p tasks/<selected-frontier-swe-task> \
  -a codex \
  -m <approved-codex-profile> \
  --env docker
```

The comparable LoopX treatment should use the same Harbor host Codex Goal route
and the same no-upload boundary as SWE-Marathon. It must expose compact
case-local lifecycle counters before it can be compared:

- quota read count;
- todo claim/update count;
- case-state read/write count;
- validation or official result count;
- refresh/spend count;
- final active-todo count;
- compact failure attribution when any stage blocks before score materializes.

## Structured Readiness Packet

```json
{
  "schema_version": "frontier_swe_no_execution_launch_packet_v0",
  "benchmark_id": "frontier-swe",
  "packet_id": "frontier_swe_ecs_no_execution_launch_packet_20260624",
  "route": "cloud_ecs_harbor_family",
  "ready_for_scored_launch": false,
  "first_blocker": "frontier_swe_source_commit_unpinned_on_benchmark_host",
  "source": {
    "repo": "Proximal-Labs/frontier-swe",
    "source_commit_pinned": false,
    "source_lock_required_before_run": true,
    "upstream_patch_allowed_without_review": false
  },
  "runner": {
    "family": "harbor",
    "prefer_wrapper_or_reducer_over_runner_patch": true,
    "official_result_parser_understood": false,
    "first_required_probe": "source_and_inventory_no_execution_probe"
  },
  "task_inventory": {
    "inventory_required_before_run": true,
    "inventory_status": "not_materialized",
    "task_body_read": false,
    "hidden_references_read": false,
    "candidate_task_selected": false
  },
  "boundary": {
    "task_started": false,
    "docker_started": false,
    "model_api_invoked": false,
    "upload_enabled": false,
    "leaderboard_enabled": false,
    "raw_logs_public": false,
    "raw_task_text_public": false,
    "raw_trajectory_public": false,
    "verifier_output_public": false,
    "local_paths_public": false,
    "credentials_public": false
  }
}
```

## Structured Run Permission Policy

```json
{
  "schema_version": "run_permission_policy_v0",
  "policy_id": "frontier_swe_no_execution_launch_packet_20260624",
  "allowed_actions": [
    "local_docker_runner",
    "local_harbor_runner",
    "benchmark_dependency_fetch",
    "compact_result_reduction"
  ],
  "forbidden_actions": [
    "codex_model_invocation",
    "public_result_upload",
    "leaderboard_submission",
    "public_benchmark_claim",
    "production_cloud_action",
    "credential_sync",
    "raw_artifact_publication"
  ],
  "max_wall_time_minutes": 0,
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
    "codex_model_invocation",
    "public_result_upload",
    "leaderboard_submission",
    "public_benchmark_claim",
    "production_cloud_action",
    "credential_sync",
    "raw_artifact_publication"
  ]
}
```

The policy allows only no-execution source, dependency, runner-shape, and
compact-reduction preparation. It explicitly forbids model invocation because
this packet has not selected a task or launch authority. A quota projection may
still treat those preparation actions as allowed; scored benchmark readiness is
controlled by `ready_for_scored_launch=false` in the structured readiness
packet above.

## Stop Rules

Stop and write a compact blocker instead of launching if any of these are true:

- the source commit is not pinned on the benchmark host;
- the task inventory cannot be summarized without private task material;
- the command shape would upload, submit, publish, or touch leaderboard paths;
- a runner patch would alter scorer, task truth, prompts, hidden references, or
  official result parsing;
- the selected candidate requires non-public credentials, Prime Intellect
  setup, GPU capacity, or external services that are not already authorized;
- Terminal-Bench or SkillsBench still lacks a compact no-upload cloud-host
  result or blocker for the shared route;
- an automatic heartbeat is the only launch authority.

## Next Action

After the SSH/GSSAPI benchmark-host gate is restored and the immediate
SkillsBench evidence lane is unblocked, run a no-execution FrontierSWE source
and task-inventory probe on the dedicated ECS host. Do not start a FrontierSWE
task until the probe fills this packet's source lock, task inventory, reducer,
and no-upload command fields with public-safe compact evidence.
