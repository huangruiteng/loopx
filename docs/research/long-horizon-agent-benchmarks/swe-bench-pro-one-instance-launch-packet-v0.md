# SWE-Bench Pro One-Instance Launch Packet V0

Date: 2026-06-12

## Scope

This packet prepares the selected SWE-Bench Pro public instance for a future
one-instance local-Docker pilot without executing the benchmark. It connects
the prior hash-only selected-row packet to public Docker image metadata and a
metadata-only local Docker provider check.

This packet does not record raw problem text, gold patch content, test patch
content, test lists, requirements, setup commands, file contents, local paths,
credentials, raw trajectories, screenshots, command argv, or environment
dumps. It also does not pull Docker images, start containers, invoke Codex CLI,
call model APIs, generate patches, evaluate patches, upload, submit, or touch
public ranking paths.

## Source Evidence

Selected instance:

- Dataset: `ScaleAI/SWE-bench_Pro`
- Dataset revision: `7ab5114912baf22bb098818e604c02fe7ad2c11f`
- Runner repository: `scaleapi/SWE-bench_Pro-os`
- Runner source commit: `ca10a60a5fcae51e6948ffe1485d4153d421e6c5`
- Repository: `NodeBB/NodeBB`
- Instance id:
  `instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan`
- Base commit: `1e137b07052bc3ea0da44ed201702c94055b8ad2`
- Task material mode: hash-only, inherited from
  `swe-bench-pro-selected-row-compaction-v0.md`

Public image metadata from the Docker Hub tag API:

- Repository: `jefzda/sweap-images`
- Tag:
  `nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5`
- Digest:
  `sha256:e49637ebe82a479ca43b4663525955bc9cdd58c457140ee31c20958d621d3cf7`
- Platform: `linux/amd64`
- Status: `active`
- Size: `845713884` bytes
- Last pushed: `2025-08-29T20:27:42.72333Z`

Metadata-only local Docker provider check:

- Docker context: `colima-loopx-bench`
- Client version: `29.2.0`
- Server version: `28.4.0`
- Server OS: `linux`
- Server architecture: `arm64/aarch64`
- Server CPUs: `4`
- Server memory: `8308088832` bytes
- Workspace free space observed: `17140224000` bytes
- Running containers observed: `0`

The image is `linux/amd64`, while the current local Docker server reports an
arm64/aarch64 architecture. A future real pilot must either specify
`linux/amd64` explicitly or recheck a native/remote provider. This packet does
not verify runtime emulation because that would require a pull/run gate.

## Runner Boundary

The official evaluator source-preflight showed that real local evaluation
requires these input classes:

- `raw_sample_path`
- `patch_path`
- `output_dir`
- `dockerhub_username`
- `scripts_dir`

For this no-run packet:

- `dockerhub_username` is known from the public image repository namespace;
- `raw_sample_path` is not ready, because it would require a private reducer
  or explicit execution-scope material file;
- `patch_path` is not ready, because no Codex/model patch producer has been
  run;
- `scripts_dir` is not ready, because run-script material remains outside this
  no-run packet;
- no candidate command values are recorded.

## Executable Fixture

The executable fixture is:

```bash
python3 examples/swe-bench-pro-one-instance-launch-packet-smoke.py
```

It emits:

- `swe_bench_pro_one_instance_launch_packet_v0`;
- a no-run `benchmark_run_v0` projection with
  `mode=one_instance_launch_packet_no_run`.

The `benchmark_run_v0` projection keeps:

- selected instance id;
- public image repository, tag, digest, and size;
- local Docker context and architecture metadata;
- one pending blocked trial;
- `hash_only_task_material=true`;
- `no_docker_pull=true`;
- `no_docker_run=true`;
- `no_codex_cli_invocation=true`;
- `no_model_call=true`;
- `no_patch_generation=true`;
- `no_patch_evaluation=true`;
- `no_upload=true`;
- `no_submit=true`;
- `no_public_ranking_path=true`;
- `execution_gate_required=true`.

## Validation

Targeted validation:

```bash
python3 examples/swe-bench-pro-one-instance-launch-packet-smoke.py
python3 -m py_compile examples/swe-bench-pro-one-instance-launch-packet-smoke.py
loopx check \
  --scan-path examples/swe-bench-pro-one-instance-launch-packet-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/swe-bench-pro-one-instance-launch-packet-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

The fixture asserts that public outputs do not contain local paths,
credentials, raw task material, patch content, test bodies, Docker output,
Codex auth material, sessions, raw trajectories, screenshots, command argv, or
environment dumps.

## Decision

SWE-Bench Pro now has a no-run one-instance launch packet. It is not execution
ready: the next step needs a separate execution gate that decides whether to
create a private raw-sample reducer, run a trusted-local Codex patch producer,
pull/start the selected image under the explicit `linux/amd64` platform, and
reduce result artifacts without upload, submit, public ranking, credentials,
raw trajectories, or screenshots.
