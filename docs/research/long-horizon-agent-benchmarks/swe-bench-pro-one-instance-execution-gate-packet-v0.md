# SWE-Bench Pro One-Instance Execution Gate Packet V0

Date: 2026-06-12

## Scope

This packet defines the no-run execution gate for the selected SWE-Bench Pro
public instance. It follows the hash-only selected-row packet and the no-run
launch packet, and turns the remaining real-execution boundary into explicit
phases and stop conditions.

This packet is not a benchmark attempt. It does not create private sample
material, invoke Codex CLI, call model APIs, generate a patch, acquire a Docker
image, start a container, evaluate a patch, upload, submit, touch public
ranking paths, read credentials, inspect raw trajectories, open screenshots,
or publish raw task text, gold changes, test changes, test selections,
requirements, setup actions, local paths, command argv, or environment dumps.

## Prior Packet Chain

The gate builds on two validated no-run packets:

- `swe-bench-pro-selected-row-compaction-v0.md`: selected public row reduced to
  compact metadata plus field hashes/counts;
- `swe-bench-pro-one-instance-launch-packet-v0.md`: public image metadata,
  local Docker metadata-only provider facts, and platform mismatch risk.

Selected instance:

- Repository: `NodeBB/NodeBB`
- Instance id:
  `instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan`
- Base commit: `1e137b07052bc3ea0da44ed201702c94055b8ad2`
- Dataset revision: `7ab5114912baf22bb098818e604c02fe7ad2c11f`
- Runner source commit: `ca10a60a5fcae51e6948ffe1485d4153d421e6c5`
- Image repository: `jefzda/sweap-images`
- Image tag:
  `nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5`
- Image digest:
  `sha256:e49637ebe82a479ca43b4663525955bc9cdd58c457140ee31c20958d621d3cf7`
- Planned platform for any future real attempt: `linux/amd64`

## Execution Phases

### Private Sample Reducer Phase

A future execution, if separately authorized, needs a private sample artifact
for the official evaluator. Public artifacts may record only compact
metadata, hashes, byte counts, and stable selectors.

Current gate state:

- execution gate required: `true`
- private material allowed now: `false`
- private sample created: `false`
- task text public: `false`
- gold change public: `false`
- test change public: `false`
- test selection public: `false`
- setup action public: `false`

Allowed public reducer fields after a future gate:

- `sample_sha256`
- `sample_bytes`
- `instance_id`
- `base_commit`
- `image_tag`

### Trusted-Local Patch Producer Phase

A future execution, if separately authorized, should run only on a trusted
local host with existing Codex authorization. Auth material must remain local
and must not be copied to a shared remote host, benchmark container, public
artifact, or source checkout.

Current gate state:

- execution gate required: `true`
- Codex surface: `local_codex_cli`
- Codex auth local-only: `true`
- Codex auth copied: `false`
- Codex CLI invoked: `false`
- model API invoked: `false`
- prompt text public: `false`
- completion text public: `false`
- patch generated: `false`
- patch content public: `false`

### Selected Image And Container Phase

The selected image is public metadata-only at this stage:

- repository: `jefzda/sweap-images`
- digest:
  `sha256:e49637ebe82a479ca43b4663525955bc9cdd58c457140ee31c20958d621d3cf7`
- size: `845713884` bytes
- planned platform: `linux/amd64`
- current local provider architecture: `arm64/aarch64`

The platform mismatch means a future real attempt needs explicit platform
handling or a provider recheck. Runtime emulation is not verified in this
packet because verification would cross the image acquisition/container-start
boundary.

Current gate state:

- image acquisition allowed now: `false`
- container start allowed now: `false`
- host credential mount allowed: `false`
- broad cleanup allowed: `false`
- image acquired: `false`
- container started: `false`

### Official Evaluator Phase

The official evaluator remains gated on private inputs and patch generation.

Current gate state:

- raw sample input ready: `false`
- patch input ready: `false`
- scripts input ready: `false`
- private output directory required: `true`
- network blocking policy required: `true`
- patch evaluation allowed now: `false`
- patch evaluated: `false`

## Result Reducer Contract

Future result reduction should write compact `benchmark_run_v0` and
`benchmark_result_v0` evidence only.

Allowed compact fields after a future gated attempt:

- instance id;
- dataset revision;
- runner commit;
- image digest;
- patch hash;
- private sample hash;
- evaluation status;
- resolved or unresolved result;
- duration seconds;
- no-upload marker;
- no-submit marker;
- no-public-ranking marker.

Forbidden public surfaces:

- raw logs;
- private evaluator output;
- patch content;
- task material;
- local paths;
- command argv;
- environment dumps;
- credentials;
- raw trajectories;
- screenshots.

Official score claims remain disallowed before a protocol-matching evaluation
has actually run.

## Executable Fixture

The executable fixture is:

```bash
python3 examples/swe-bench-pro-one-instance-execution-gate-smoke.py
```

It emits:

- `swe_bench_pro_one_instance_execution_gate_packet_v0`;
- `benchmark_run_v0` with `mode=one_instance_execution_gate_packet_no_run`;
- `benchmark_result_v0` with `official_task_score.status=not_run` and a
  separate `control_plane_score_core_v0`.

## Validation

Targeted validation:

```bash
python3 examples/swe-bench-pro-one-instance-execution-gate-smoke.py
python3 -m py_compile examples/swe-bench-pro-one-instance-execution-gate-smoke.py
loopx check \
  --scan-path examples/swe-bench-pro-one-instance-execution-gate-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/swe-bench-pro-one-instance-execution-gate-packet-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

The fixture asserts:

- prior packets are ready;
- private sample material has not been created;
- Codex/model invocation has not occurred;
- patch generation and evaluation have not occurred;
- image acquisition and container start have not occurred;
- explicit `linux/amd64` handling remains required;
- no upload, submit, or public ranking path is allowed;
- credentials, local paths, raw artifacts, trajectories, and screenshots are
  absent from public outputs.

## Decision

The SWE-Bench Pro one-instance execution gate is ready as a no-run boundary
artifact. A real pilot remains a separate execution-scope decision because it
would cross at least five boundaries: private sample reduction, trusted-local
Codex patch generation, selected image acquisition, container start, and patch
evaluation.

If a real pilot is later selected, the smallest safe shape is:

1. create a private sample artifact and publish only its hash/count metadata;
2. run trusted-local patch generation and publish only patch hash/count
   metadata;
3. acquire and start only the selected image with explicit `linux/amd64`
   handling;
4. run the official evaluator with private output reduction;
5. publish compact result evidence only, with no upload, no submit, and no
   public ranking claim unless separately authorized.
