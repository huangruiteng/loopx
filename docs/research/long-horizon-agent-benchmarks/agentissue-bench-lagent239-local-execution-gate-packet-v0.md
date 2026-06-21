# AgentIssue-Bench `lagent_239` Local Execution Gate Packet V0

Date: 2026-06-12

## Scope

This packet defines the no-run local execution gate for AgentIssue-Bench tag
`lagent_239`.

It builds on four prior no-run packets:

- one-tag launch packet;
- manifest/context gate;
- public issue context packet;
- public source-sync plan.

This packet is not a real benchmark attempt. It does not invoke Codex CLI, call
model APIs, generate a patch, pull Docker, start Docker, evaluate a patch,
upload, submit, touch public ranking paths, read credentials, read raw
trajectories, open screenshots, or publish raw issue text, source diffs,
generated patch content, solutions, gold material, test patches, or test
bodies.

## Execution Phases

### Trusted-Local Codex Patch Phase

Future execution, if separately authorized, should run only on a trusted local
host with existing Codex CLI authorization.

Required invariants:

- Codex auth stays local-only.
- Codex auth, API keys, session files, shell history, and `~/.codex` are never
  copied to a shared remote host or benchmark container.
- Public artifacts record compact metadata and hashes, not prompts,
  completions, source diffs, or patch content.
- The only intended patch output path is:
  `Patches/lagent_239/attempt.patch`.

Current gate state:

- execution gate required: `true`
- Codex CLI invoked: `false`
- model API invoked: `false`
- patch generated: `false`
- patch content public: `false`

### Single-Tag Docker Evaluation Phase

Future execution, if separately authorized, should evaluate only the selected
tag:

```text
alfin06/agentissue-bench:lagent_239
```

Required invariants:

- Pull at most the selected image.
- Mount only `Patches/lagent_239/`.
- Do not run all-tag loops.
- Do not perform global Docker cleanup.
- Do not mount host credentials.
- Do not upload, submit, or touch public ranking paths.

Current gate state:

- image manifest route ready: `true`
- image pull allowed now: `false`
- container start allowed now: `false`
- patch evaluation allowed now: `false`
- Docker pulled: `false`
- Docker started: `false`
- patch evaluated: `false`

## Result Reducer Contract

Future result reduction should write compact `benchmark_run_v0` and
`benchmark_result_v0` evidence only.

Allowed compact fields after a real gated attempt:

- selected tag;
- target source HEAD SHA;
- patch hash;
- Docker image ref;
- evaluation status;
- resolved or unresolved result;
- duration seconds;
- no-upload marker;
- no-submit marker;
- no-public-ranking marker.

Forbidden public surfaces:

- raw logs;
- patch content;
- raw issue text;
- source diffs;
- test bodies;
- credentials;
- raw trajectories;
- screenshots;
- local paths;
- command argv;
- environment dumps.

Official score claims remain disallowed before a protocol-matching evaluation
has actually run.

## Executable Fixture

The executable fixture is:

```bash
python3 examples/agentissue-bench-lagent239-local-execution-gate-smoke.py
```

It emits:

- `agentissue_bench_local_execution_gate_packet_v0`;
- `benchmark_run_v0` with `mode=local_execution_gate_packet_no_run`;
- `benchmark_result_v0` with `official_task_score.status=not_run` and a
  separate `control_plane_score_core_v0`.

## Validation

Targeted validation:

```bash
python3 examples/agentissue-bench-lagent239-local-execution-gate-smoke.py
python3 -m py_compile examples/agentissue-bench-lagent239-local-execution-gate-smoke.py
loopx check \
  --scan-path examples/agentissue-bench-lagent239-local-execution-gate-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-lagent239-local-execution-gate-packet-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

The fixture asserts:

- prior packets are ready;
- source checkout and file-content reads have not occurred;
- Codex/model invocation has not occurred;
- patch generation and evaluation have not occurred;
- Docker pull/run has not occurred;
- no upload, submit, or public ranking path is allowed;
- credentials, local paths, raw artifacts, trajectories, and screenshots are
  absent from public outputs.

## Decision

The local execution gate packet is ready as a no-run boundary artifact. A real
pilot remains a separate decision because it would cross at least four
execution boundaries: source checkout/content reads, Codex patch generation,
Docker image pull/run, and patch evaluation.

If a real pilot is later selected, the smallest safe shape is:

1. trusted-local ephemeral source checkout;
2. local Codex patch generation into `Patches/lagent_239/attempt.patch`;
3. single-tag Docker evaluation;
4. compact result reduction;
5. no upload, no submit, and no public ranking claim unless a later explicit
   approval says otherwise.
