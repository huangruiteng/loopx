# SWE-Bench Pro Launch Wrapper Contract v0

Date: 2026-06-12

Status: public-safe wrapper/preflight contract; no benchmark run started.

## Scope

This packet resolves the missing public launch-wrapper contract identified by
`swe-bench-pro-prelaunch-blocker-v0.md`. It defines how a future selected
SWE-Bench Pro one-instance pilot may join private run artifacts, provider
readiness, the selected image, the official evaluator, and compact result
reduction without leaking raw task material or credentials.

This packet does not create a private sample, generate an attempt patch, read
evaluator script bodies, acquire Docker images, start containers, invoke
Codex, call model APIs, evaluate patches, upload, submit, touch public ranking
paths, read credentials, inspect raw trajectories, open screenshots, or record
local paths.

## Contract

The wrapper accepts only redacted descriptors at the public boundary:

- selected instance id;
- dataset revision and runner commit;
- selected image digest and platform;
- private sample descriptor: hash, byte count, and readiness boolean;
- attempt patch descriptor: hash, byte count, and readiness boolean;
- evaluator scripts descriptor: manifest hash and readiness boolean;
- provider descriptor: selected provider, platform, capacity, and no-auth
  boundary booleans;
- output reducer policy: compact `benchmark_run_v0` and
  `benchmark_result_v0` only.

It must never expose:

- raw problem statement;
- gold patch;
- test patch;
- test list;
- setup command;
- generated patch content;
- evaluator logs;
- local paths;
- command argv;
- environment dumps;
- credentials or Codex auth state;
- trajectories or screenshots.

## Provider Policy

The contract supports two provider surfaces:

1. `local_docker_trusted_host_codex`: preferred when local capacity, platform,
   private sample, attempt patch, evaluator scripts, and no-upload/no-submit
   boundaries are all ready.
2. `remote_gpu_route_b_noauth_helper`: allowed only for no-auth helper/provider
   plumbing. It may not receive local Codex auth, API keys, shell history,
   local LoopX runtime, private task material, or raw output.

Provider selection fails closed when:

- the selected image platform is not supported by the chosen provider;
- local CPU, memory, or disk floors are below the configured threshold;
- private sample, attempt patch, or evaluator scripts are missing;
- the only available remote path would require Codex auth or credential sync;
- upload, submit, or public ranking behavior is not disabled.

## Current Contract Evaluation

The current public-safe fixture marks:

- wrapper contract ready: `true`;
- host Codex surface available: `true`;
- private sample ready: `false`;
- attempt patch ready: `false`;
- evaluator scripts ready: `false`;
- local provider selected: `false`;
- Route B helper eligible: `true` for no-auth plumbing only;
- pilot launch authorized now: `false`.

This is progress over the previous blocker because the missing wrapper
contract is now explicit and executable. It still does not authorize the
pilot: private artifact staging and provider readiness remain unresolved.

## Executable Fixture

The deterministic fixture is:

```bash
python3 examples/swe-bench-pro-launch-wrapper-contract-smoke.py
```

It emits `swe_bench_pro_launch_wrapper_contract_v0`, including compact
`benchmark_run_v0` and `benchmark_result_v0` evidence with:

- `launch_wrapper_contract_ready=true`;
- `pilot_launch_authorized=false`;
- `official_task_score.status=not_run`;
- failure attribution focused on missing private artifact descriptors and
  provider readiness, not raw task material.

## Validation

Targeted validation:

```bash
python3 examples/swe-bench-pro-launch-wrapper-contract-smoke.py
python3 -m py_compile examples/swe-bench-pro-launch-wrapper-contract-smoke.py
loopx check \
  --scan-path examples/swe-bench-pro-launch-wrapper-contract-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/swe-bench-pro-launch-wrapper-contract-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

## Claim Boundary

This packet may claim only that the public launch-wrapper/preflight contract is
now defined and tested. It must not claim the selected SWE-Bench Pro instance
was attempted, solved, failed, scored, or ready to submit.
