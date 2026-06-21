# Terminal-Bench Probe V0

Checked at: 2026-06-07T18:12:55+08:00

## Scope

This probe answers one narrow setup question for the long-horizon benchmark
program: where can LoopX attach to Terminal-Bench or Harbor without
changing official benchmark semantics?

The answer is deliberately conservative. LoopX should first behave as a
passive control-plane wrapper around official runner outputs. A custom agent
wrapper is possible, but it should not be the first leaderboard-facing path.

## Sources Inspected

- Terminal-Bench public repository:
  `https://github.com/harbor-framework/terminal-bench`, commit
  `1a6ffa9674b571da0ed040c470cb40c4d85f9b9b`.
- Harbor public repository:
  `https://github.com/laude-institute/harbor`, commit
  `8cfac6ad91c5c566ff14040cc4acbfe94ad42356`.
- Current LoopX authority/material handoff summary for
  `loopx-meta`: redacted authority context reports current
  benchmark/material authority with no owner-review requirement and low
  conflict risk. This was used only as a planning constraint; private source
  paths, internal document links, and raw agent-harness material are not copied
  here.

## Runner Boundary Findings

Terminal-Bench has two relevant surfaces:

- The legacy `tb` package runner supports built-in agents and
  `--agent-import-path some.module:AgentClass`. The custom class must subclass
  Terminal-Bench `BaseAgent` and implement `perform_task(instruction, session,
  logging_dir)`.
- The built-in `codex` agent in the `tb` runner invokes `codex exec` inside the
  task terminal, requires OpenAI authentication, and records token counts and a
  `FailureMode` through the Terminal-Bench `AgentResult`.
- The `tb` run lock records replay-affecting fields in `tb.lock`, including
  harness version, dataset source, agent import path, model, concurrency,
  attempts, timeout overrides, and output path.
- Trial outputs are structured enough for passive ingestion: per-trial
  `results.json`, command history, pane logs, agent logs, and run-level
  `run_metadata.json` / benchmark result JSON are the first LoopX read
  surface.

Harbor is the current official harness path for Terminal-Bench 2.0:

- Harbor README describes `harbor run --dataset terminal-bench@2.0` as the
  official Terminal-Bench 2.0 path.
- Harbor supports built-in `codex` plus `--agent-import-path` for custom
  agents. Agent configs also carry model, extra env, skills, MCP config,
  timeout overrides, and allowed host additions.
- Harbor job outputs have a stable passive surface: job `config.json`,
  `lock.json`, job `result.json`, per-trial `config.json`, per-trial
  `result.json`, trial logs, agent logs, verifier logs, artifact manifests,
  and reward files.
- Harbor's Codex agent already converts Codex CLI session JSONL into ATIF
  `trajectory.json`, captures token and cost metrics when available, supports
  optional skills/MCP registration, and writes Codex stdout to agent logs.

## LoopX Attachment Strategy

Use a three-step boundary:

1. Passive observer first. Read `lock.json`, `result.json`, trial
   `result.json`, `trajectory.json`, verifier reward files, and trial logs.
   Write a LoopX `benchmark_run_v0` event only after parsing and
   validating those official outputs.
2. Local comparison second. Run the same small official or official-like task
   once with bare Codex CLI and once with LoopX passive observation,
   without changing benchmark prompts, task files, timeouts, resources, or
   scoring.
3. Custom agent wrapper last. Only after passive metrics show a concrete gap,
   consider a local-only `--agent-import-path` wrapper that subclasses the
   runner's `BaseAgent`, delegates execution to the built-in Codex agent or the
   Codex CLI, and adds LoopX state markers. Do not present this wrapper
   as an official leaderboard agent until benchmark rules and submission
   semantics are checked.

## Candidate Local Commands

Do not run these automatically in a heartbeat. They are next-step examples once
credentials, Docker/runtime readiness, model budget, and benchmark terms are
explicitly acceptable.

For Harbor Terminal-Bench 2.0 passive observation:

```bash
harbor run \
  --dataset terminal-bench@2.0 \
  --agent codex \
  --model <openai-codex-model> \
  --n-concurrent 1 \
  --jobs-dir <local-private-output-dir> \
  --job-name terminal_bench_probe_v0_codex_builtin
```

For a future local-only custom wrapper probe:

```bash
harbor run \
  --dataset terminal-bench@2.0 \
  --agent-import-path loopx_terminal_bench.agent:GoalHarnessCodexAgent \
  --model <openai-codex-model> \
  --n-concurrent 1 \
  --jobs-dir <local-private-output-dir> \
  --job-name terminal_bench_probe_v0_loopx_wrapper
```

For the older `tb` runner compatibility path:

```bash
tb run \
  --dataset terminal-bench-core==0.1.1 \
  --agent codex \
  --model <openai-codex-model> \
  --n-concurrent 1 \
  --output-path <local-private-output-dir> \
  --run-id terminal_bench_probe_v0_tb_codex_builtin
```

## Stop Condition

Stop before any of the following:

- paid model execution or external cloud sandbox use;
- official leaderboard submission or upload;
- changing benchmark task files, test scripts, timeouts, resource limits, or
  scoring;
- copying credentials, private run logs, Codex session content, internal
  project paths, or raw agent-harness documents into a public artifact;
- claiming LoopX improves benchmark score before a paired run and a
  public-safe `benchmark_run_v0` comparison exist.

## Next Slice

Implement a public-safe `benchmark_run_v0` ingestion sketch or smoke fixture for
Harbor job outputs. The fixture should validate only official output structure:
job lock, job result, trial result, reward/verifier evidence, agent trajectory
presence, token/cost fields when present, retry/progress counts, and the command
line needed to resume or inspect the run. It should not invoke Docker, Codex, a
model API, or a leaderboard upload by default.
