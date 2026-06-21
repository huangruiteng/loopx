# SWE-Bench Pro Prelaunch Blocker v0

Date: 2026-06-12

Status: compact blocker evidence; no benchmark run started.

## Scope

This packet records the first post-approval prelaunch check for the selected
SWE-Bench Pro one-instance e2e pilot. It follows
`benchmark-e2e-owner-decision-v0.md` and tests whether the selected pilot can
launch without crossing raw task material, credential, or shared-host auth
boundaries.

This packet does not read raw problem statements, gold patches, test patches,
test lists, requirements, setup commands, source file contents, generated patch
content, raw logs, local paths, credentials, raw trajectories, screenshots, or
environment dumps. It does not acquire Docker images, start containers, invoke
Codex, call model APIs, evaluate patches, upload, submit, or touch public
ranking paths.

## Prelaunch Findings

Ready signals:

- host `codex` CLI is present and reports `codex-cli 0.128.0`;
- Docker daemon is reachable through the current benchmark context;
- the selected SWE-Bench Pro instance, public image metadata, route-selection
  packet, execution gate packet, and owner decision packet are all recorded.

Blocking signals:

- no private sample artifact has been created for the official evaluator;
- no attempt patch artifact exists for the selected instance;
- no evaluator `scripts_dir` has been staged for a real local run;
- no LoopX SWE-Bench Pro launch wrapper exists yet to connect the
  selected sample, attempt patch, selected image, official evaluator, and
  compact reducer;
- the current local Docker provider is `aarch64` while the selected image is
  `linux/amd64`;
- current local Docker capacity is 4 CPUs and 8,308,088,832 bytes of memory;
- current workspace free space observed through the provider check is
  12,963,604 KiB, which is below the safer 20 to 30 GiB envelope used by the
  benchmark route notes.

## Decision

Do not start the SWE-Bench Pro pilot from this heartbeat. The selected route is
approved, but launch readiness is blocked by missing private run artifacts and
local provider capacity/platform risk.

The next bounded step should be one of:

1. implement a credential-isolated local launch wrapper that first creates a
   private sample artifact and a trusted-local attempt patch, then runs only
   the selected official evaluator and reduces compact result evidence; or
2. use Route B only for no-auth helper/provider plumbing while keeping Codex
   auth local-only; or
3. if neither launch path is ready, keep appending compact blocker evidence
   rather than selecting a new benchmark.

## Compact Evidence

The deterministic fixture is:

```bash
python3 examples/swe-bench-pro-prelaunch-blocker-smoke.py
```

It emits `swe_bench_pro_prelaunch_blocker_v0`, including a compact
`benchmark_run_v0` and `benchmark_result_v0` blocker with:

- official task score status `not_run`;
- terminal state `blocked_prelaunch_prerequisites`;
- host Codex CLI available;
- private sample, attempt patch, evaluator script, Docker image, container,
  Codex/model invocation, patch evaluation, upload, submit, and public ranking
  all absent.

## Validation

Targeted validation:

```bash
python3 examples/swe-bench-pro-prelaunch-blocker-smoke.py
python3 -m py_compile examples/swe-bench-pro-prelaunch-blocker-smoke.py
loopx check \
  --scan-path examples/swe-bench-pro-prelaunch-blocker-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/swe-bench-pro-prelaunch-blocker-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

## Claim Boundary

This packet is not benchmark performance evidence. It may claim only that the
selected SWE-Bench Pro route is approved but currently blocked before launch by
missing private run artifacts and provider readiness risk. It must not be used
to claim the selected instance was attempted, solved, failed, or scored.
