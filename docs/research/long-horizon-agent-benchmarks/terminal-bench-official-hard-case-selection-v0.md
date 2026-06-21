# Terminal-Bench Official Hard-Case Selection V0

Checked at: 2026-06-09T13:30:00+08:00.

This note switches the LoopX benchmark research lane from
`terminal-bench-sample@2.0` to the official `terminal-bench@2.0` benchmark
surface. It is a selection and run-order contract only. It does not run Harbor,
Terminal-Bench, Docker, Codex, model APIs, paid compute, uploads, shares, or
leaderboard submission.

## Why Switch

`terminal-bench-sample@2.0` is useful for runner, Docker, Codex auth, artifact
ingest, and worker-bridge smoke testing. It is not the benchmark surface for
research conclusions. The official Harbor registry lists `terminal-bench@2.0`
as Terminal-Bench version 2.0 with 89 tasks, and describes it as a harder and
higher-quality successor to 1.0.

LoopX should therefore stop using sample-only tasks as the next evidence
target. The sample results remain valuable as adapter readiness and ingest
evidence, but future model-plus-harness claims should be grounded in selected
official `terminal-bench@2.0` cases.

## Selection Policy

Do not run all 89 tasks first. Select two or three high-value long-horizon
cases where the Codex goal-mode baseline is plausibly brittle and where Goal
Harness could help through state, todo, checkpoint, replan, or compact evidence
discipline.

Selection criteria:

1. Prefer tasks with multi-step debugging, dependency repair, system state, or
   cross-file reasoning.
2. Prefer tasks where failure attribution is useful even when both modes fail.
3. Avoid tasks that are mainly quick parsing, simple command execution, or
   already solved sample calibration.
4. Avoid tasks likely to be dominated by external downloads, hardware, or
   benchmark environment flakiness unless the goal is explicitly to study
   long-run environment recovery.
5. Keep the first batch small enough to inspect trajectories and failure modes
   manually before scaling.

## Primary Batch

| Rank | Task | Why this belongs in the first official batch | First comparison |
| --- | --- | --- | --- |
| 1 | `fix-code-vulnerability` | Security debugging is long-horizon: the agent must inspect code, infer exploit/failure mechanics, patch narrowly, and verify. The sample metadata for this same task family marked it hard and long. | Run Codex goal-mode baseline and Codex+LoopX treatment in parallel. |
| 2 | `modernize-scientific-stack` | Dependency modernization is close to the `build-cython-ext` readiness lane but broader and more failure-prone: version constraints, scientific packages, compile/runtime errors, and repeated verification. | Run after `fix-code-vulnerability` unless the first pair exposes a runner blocker. |
| 3 | `llm-inference-batching-scheduler` | ML systems scheduling is likely to require code comprehension, performance/shape reasoning, and careful tests. It is aligned with LoopX's intended long-horizon engineering niche. | Run as the third paired case or replace a blocked case. |

## Backup Queue

Use these if the primary batch is blocked by environment or verifier issues:

| Task | Use when |
| --- | --- |
| `qemu-startup` | We want a system-state recovery task with high setup/debug friction. |
| `qemu-alpine-ssh` | We want another system-state recovery task but should expect higher environment-risk noise. |
| `compile-compcert` | We want a compile/toolchain-heavy task that stresses long build and dependency reasoning. |
| `git-leak-recovery` | We want a source-control forensic task with state reconstruction and careful rollback boundaries. |

## Paired Run Protocol

For each selected task, run the same official task id under two cells:

1. `codex-goal-mode`: Harbor launches Codex with its native goal-mode surface,
   the original task prompt, and no LoopX packet, bridge, or state.
2. `codex-loopx`: Harbor launches the same goal-mode Codex worker with
   the LoopX access packet and active worker bridge enabled.

Keep the two cells aligned on:

- benchmark id: `terminal-bench@2.0`;
- task id;
- model and Codex goal-mode invocation surface;
- Harbor runner source;
- no-upload/private jobs boundary;
- attempts and concurrency;
- task prompt, tests, scoring, and resources;
- timeout tier recorded explicitly.

The treatment cell is a model-plus-harness pair, not a native Codex baseline.
Its official verifier reward is still useful, but any comparison must carry
`case_semantics_changed_by_harness=true`,
`loopx_inside_case=true`, and
`official_score_comparable_to_native_codex=false`.

The Codex goal-mode baseline is the paired baseline for this experiment because
it answers whether LoopX adds value beyond Codex's own goal execution
mode while withholding LoopX state. Hardened or bare Codex evidence may
still be recorded as startup/install calibration, but it is not the primary
paired baseline.

## Metrics

Each compact `benchmark_run_v0` must record:

- official verifier reward and completion state;
- runner return status and timeout/interruption policy;
- wall time and timeout tier;
- Codex token/cost metrics when Harbor exposes them;
- LoopX CLI calls inside the worker;
- Codex runtime goal-tool calls, kept separate from LoopX CLI calls;
- worker benchmark-run writeback and schema validity;
- pre-worker setup failure count;
- verifier dependency failure attribution when reward is zero or missing;
- raw-trace, raw-path, credential, Docker-log, and upload boundaries.

## Stop Conditions

Stop before:

- running all 89 tasks;
- uploading, sharing, publishing, or submitting leaderboard results;
- recording raw task prompts, raw Codex sessions, raw logs, Docker logs, local
  host paths, or credential values in public artifacts;
- changing task prompt, tests, scoring, resource limits, or task files;
- claiming paper-style uplift from fewer than the selected paired cases;
- treating sample-only results as official benchmark evidence.

## Next Slice

Run a private no-upload official paired pilot on
`terminal-bench@2.0` / `fix-code-vulnerability`:

1. launch `codex-goal-mode` after verifying the local Codex goal-mode
   invocation surface and its private no-upload launch summary
   (`codex_goal_mode_invocation_surface=slash_command`,
   `loopx_access_packet_mode=none`, no worker bridge);
2. launch `codex-loopx` with the active worker bridge in parallel;
3. ingest compact Harbor results for both arms;
4. write one paired comparison event with reward, wall time, usage, worker
   interaction counters, and failure attribution.

If the first task hits a runner or verifier blocker, write the blocker as a
compact benchmark event and move to `modernize-scientific-stack` only after the
blocker is classified.

## Smoke

```bash
python3 examples/terminal-bench-official-hard-case-selection-smoke.py
```

The smoke validates the public-safe selection payload and this no-run document.
