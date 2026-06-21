# SWE-Marathon Setup Readiness v0

Date: 2026-06-12

Purpose: decide whether SWE-Marathon is a plausible next long-horizon
benchmark lane for LoopX after the Agents' Last Exam local/non-GCP
route was paused.

This note is a setup-readiness scan only. It does not execute any benchmark
task, model agent, verifier, Docker task environment, upload, leaderboard
path, raw trajectory, credential read, or paid cloud run.

## Source Pins

- Official benchmark repo:
  [abundant-ai/swe-marathon](https://github.com/abundant-ai/swe-marathon),
  observed at `0128be1c2f05fe0255dc2ffb083d503c6913486e`.
- Required Harbor fork:
  [RishiDesai/harbor](https://github.com/RishiDesai/harbor), observed at
  `7bfd77d79de43faec698fb8aba1c1a8f8fc23196`.
- Public website and paper:
  [swe-marathon.org](https://www.swe-marathon.org/) and
  [arXiv:2606.07682](https://arxiv.org/abs/2606.07682).

The official README points to the RishiDesai Harbor fork rather than stock
Harbor because the fork adds CUA verifiers and closed-internet task support.

## Codex CLI Baseline Evidence

SWE-Marathon has direct Codex CLI evidence. Public score trackers synced from
the official SWE-Marathon leaderboard report `Codex CLI + GPT-5.5` at `12.0%`
pass@1. The paper also reports 1,300 real-agent rollouts and states that no
evaluated configuration exceeds `30%` pass@1.

This is stronger evidence than most other candidate lanes because the low
success signal is for the intended agent surface, not merely for an OpenAI
model behind another harness.

## Readiness Verdict

SWE-Marathon is the strongest next candidate among the scanned benchmarks, but
the next safe step is still a runner preflight, not a scored run.

Reasons it fits LoopX:

- Horizon is real: task metadata spans roughly 4 to 400 expert-hours, and
  agent timeouts range from 2 hours to 10 hours for many tasks.
- Scoring is concrete: task verifiers write reward artifacts, and the
  contributor guide requires binary `reward.txt` plus normalized
  `metrics.json.partial_score` for partial diagnostics.
- Failure attribution is rich enough for LoopX: tasks encode verifier
  timeouts, agent timeouts, resource requirements, network policy, CUA stages,
  and metadata explanations.
- Codex is a first-class runner target in the Harbor fork's review guide and
  tool layer.

Current blockers before a useful run:

- `harbor` is not installed on this host PATH.
- The official path requires the RishiDesai Harbor fork, so stock Harbor parity
  is not enough.
- CUA-stage tasks require Anthropic-backed verifier judging. Those are not good
  first pilots for a local Codex-only LoopX comparison.
- GPU tasks require T4, A100, or H100 resources. Those should be deferred until
  the CPU shell-only path is proven.
- Logs are public-bucket based but the README says to message for S3
  credentials. LoopX should not depend on those logs for the first
  reproducible local lane.

## Runner Surface

Documented install:

```bash
uv tool install harbor@git+https://github.com/RishiDesai/harbor.git
```

Documented trial shape:

```bash
harbor run -p tasks/rust-c-compiler --agent claude-code --model anthropic/claude-opus-4-7
```

The Harbor fork review guide also documents Codex as:

```bash
harbor run -p <task_path> -a codex -m openai/gpt-5.5
```

and lists these relevant knobs:

- `--path` / `-p` for local task path.
- `--agent` / `-a` and `--model` / `-m`.
- `--env` / `-e` for `docker`, `daytona`, `e2b`, `modal`, `runloop`, or `gke`.
- `--agent-env` and `--agent-kwarg`.
- resource overrides for CPUs, memory, and storage.
- `--background` and `--json` for async machine-readable execution.

The fork's agent tools layer installs `@openai/codex@latest` inside hosted
agent environments, which means the benchmark expects a Codex CLI-like
surface. The local LoopX route should still prefer the already
authorized host Codex CLI and prove the exact command/config bridge before any
model run.

## Harbor CLI Preflight Result

Preflight completed 2026-06-12 from the pinned local Harbor fork checkout
`RishiDesai/harbor@7bfd77d79de43faec698fb8aba1c1a8f8fc23196` with
`uv run`, not a global install.

Observed safe commands:

```bash
uv run harbor --version
uv run harbor --help
uv run harbor run --help
```

Result:

- `harbor --version` returned `0.13.1`.
- `uv` created the fork-local ignored `.venv`, downloaded CPython `3.13.13`,
  built the Harbor packages, and installed 237 packages.
- `harbor --help` exposed the expected command surface, including `run`,
  `adapter`, `task`, `dataset`, `job`, `trial`, `auth`, and `leaderboard`.
- `harbor run --help` confirmed `run` is the `harbor job start` alias and
  supports `--path/-p`, `--agent/-a`, `--model/-m`, `--env`, `--agent-env`,
  `--agent-kwarg`, resource overrides, verifier options, and local/host agent
  controls.
- `codex` is an allowed `--agent/-a` value on the runner surface.
- Upload is explicit through `--upload`; the no-upload route is enforceable by
  omitting upload flags.
- `harbor agents --help` is not a valid command in this fork, so agent
  discovery should use `harbor run --help` or source-level adapter docs.

Boundary observed: no benchmark task was executed, no `harbor run -p ...` was
launched, no Docker task image was built or started, no Codex/model call was
made, no credential value was read, no upload/leaderboard/submit path was used,
and no raw trajectory, screenshot, hidden ref, task solution, or task test body
was consumed.

## Task Inventory

Metadata-only scan found 20 public tasks.

CPU shell-only first-pilot candidates:

| Task | Category | Expert hours | Agent timeout | Internet | Why it is plausible |
| --- | --- | ---: | ---: | --- | --- |
| `rust-c-compiler` | systems | 30 | 6h | yes | Official README example, CPU-only, rich compiler/test attribution. |
| `rust-java-lsp` | systems | 20 | 3h | yes | CPU-only, deterministic protocol/verifier shape. |
| `stripe-clone` | backend | 14 | 4h | yes | Backend API clone with many pytest gates and no CUA stage. |
| `wasm-simd` | systems | 12 | 5h | yes | CPU-only, large deterministic test suite and metrics. |
| `zstd-decoder` | c | 12 | 5h | no | CPU-only, no-internet policy, strong anti-cheat checks. |
| `find-network-alignments` | optimization | 20 | 5h | yes | CPU-only, compact optimization artifact outputs. |
| `vliw-kernel-optimization` | optimization | 8 | 8h | yes | CPU-only, long enough to test persistence/restart discipline. |

Defer for first run:

- CUA/multi-stage tasks: `excel-clone`, `mastodon-clone`, `s3-clone`,
  `slack-clone`.
- GPU tasks: `embedding-eval`, `jax-pytorch-rewrite`, `parameter-golf`,
  `trimul-cuda`.
- Very large rewrite tasks such as `nextjs-vite-rewrite`,
  `kubernetes-rust-rewrite`, `ruby-rust-port`, and
  `biofabric-rust-rewrite` until runner, writeback, and cost controls are
  proven.

## LoopX Experiment Shape

First real experiment should be a local/no-upload paired pilot:

1. Hardened Codex baseline: Harbor `codex` agent, same task and model, with
   LoopX only observing runner-side compact artifacts.
2. LoopX treatment: same Codex model and task, but with LoopX
   access packet, todo/status/history/check commands, compact writeback, and
   explicit interruption/recovery evidence.
3. Compare official task reward separately from control-plane score. Do not
   claim uplift from runner success alone.

Required compact evidence before spending a scored benchmark attempt:

- exact Harbor fork version and CLI help/agent surface;
- Docker local provider readiness or explicit cloud provider decision;
- no-upload/no-leaderboard command boundary;
- host Codex CLI route or benchmark-managed Codex route, with credential names
  redacted and values never read;
- selected task metadata: task id, CPU/GPU/CUA, timeout, network policy,
  expected artifact files, and whether official-comparable timeout/resources
  are unchanged;
- post-run artifact materialization path reduced to compact reward, metrics,
  cost/time, and failure taxonomy only.

## Next Bounded Step

Build a no-execution launch packet for the first CPU shell-only pilot.

Recommended first candidate: `rust-c-compiler`, because it is the official
README example, CPU-only, and likely to expose deterministic compiler/test
attribution without CUA or GPU dependencies.

The launch packet should include only compact public metadata and command
boundaries:

1. task id, category, expected timeout, internet policy, CPU/GPU/CUA class;
2. intended no-upload runner shape using `harbor run -p tasks/rust-c-compiler
   -a codex -m <model>` without executing it;
3. required environment and artifact locations at the directory/filename level,
   excluding task solution/test content and raw trajectories;
4. explicit stop rules for Docker task build/start, Codex/model invocation,
   credential reads, uploads, leaderboard paths, screenshots, hidden refs, and
   paid/cloud execution.

## Decision

Continue with SWE-Marathon through a no-execution CPU pilot launch packet. Do
not spend fresh benchmark execution quota until that packet proves the selected
task, no-upload boundary, Codex agent surface, local provider assumptions, and
compact evidence path are ready.
