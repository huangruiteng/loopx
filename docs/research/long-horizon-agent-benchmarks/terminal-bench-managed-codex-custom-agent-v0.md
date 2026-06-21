# Terminal-Bench Managed Codex Custom Agent V0

Checked at: 2026-06-08T19:52:00+08:00.

This note records the first concrete Harbor custom-agent bridge for the core
LoopX managed Terminal-Bench treatment. It is still a private
single-task pilot surface, not a full benchmark run, not leaderboard evidence,
not a public score claim, and not proof of LoopX uplift.

## What Changed

Harbor exposes a custom agent hook through:

```text
--agent-import-path
```

LoopX now provides the import target:

```text
loopx.terminal_bench_agent:GoalHarnessManagedCodex
```

The custom agent subclasses Harbor's built-in Codex adapter. It keeps the
native Codex setup, auth handoff, execution, session ingestion, and token/cost
backfill behavior, while wrapping the benchmark task instruction with a minimal
LoopX managed policy envelope. Managed metadata is deferred until
`populate_context_post_run()` so Harbor still sees an empty `AgentContext` and
can run the built-in Codex session ingestion path.

## Managed Policy Surface

The managed worker records:

| Field | Value |
| --- | --- |
| Mode | `loopx_managed_codex` |
| Policy version | `loopx_terminal_bench_policy_v0` |
| Behavior spec | `terminal_bench_loopx_managed_codex_v0` |
| Trace publicness | `private_raw_trace_compact_public_summary` |
| `loopx_inside_case` | `true` |
| `case_semantics_changed_by_harness` | `true` |
| `official_score_comparable_to_native_codex` | `false` |
| `model_plus_harness_pair` | `true` |
| `context_metadata_deferred_until_post_run` | `true` |
| Usage source after ingestion | `codex_cli_session_token_count_event` or `unavailable` |

The adapter records only compact metadata such as policy/version ids, booleans,
prompt length, and a short task-instruction hash. It does not store raw task
prompts, raw managed prompts, raw Codex sessions, credential values, auth files,
Docker logs, host-local paths, or task artifacts in public LoopX notes.

## Usage Ingestion Guard

Harbor only calls an agent's post-run context backfill when the trial
`AgentContext` is still empty after `run()`. The managed adapter therefore does
not write metadata into the context during `run()`. After the runner downloads
agent logs, the adapter lets Harbor parse Codex session JSONL and then appends
LoopX metadata. If Harbor trajectory conversion fails, the adapter has a
public-safe fallback that reads only the last session `event_msg/token_count`
totals and copies compact usage fields into `AgentContext`.

This guard is meant to preserve the same usage provenance as the bare and
passive sample lanes:

```text
usage_source=codex_cli_session_token_count_event
```

The fallback does not record raw session lines, raw prompts, tool outputs,
local paths, or credential material.

## Private Pilot Command Shape

Run from the LoopX repository root, or otherwise make the repository
package importable to the Harbor process. The command shape is:

```text
uvx --from git+https://github.com/harbor-framework/harbor@a56546feb7d2da0b3196bbd7b05adacb72449391 harbor run --dataset terminal-bench@2.0 --agent-import-path loopx.terminal_bench_agent:GoalHarnessManagedCodex --model gpt-5.5 --env docker --n-attempts 1 --n-concurrent 1 --jobs-dir <private-jobs-dir> --job-name terminal-bench_2_0_build_cython_ext_loopx_managed_codex_cli_dry_run --agent-env CODEX_FORCE_AUTH_JSON=true --agent-kwarg loopx_policy_version=loopx_terminal_bench_policy_v0 --agent-kwarg loopx_behavior_spec_id=terminal_bench_loopx_managed_codex_v0 --agent-kwarg loopx_mode=loopx_managed_codex --agent-kwarg loopx_goal_id=<goal-id> --agent-kwarg loopx_ablation_mode=loopx_managed --include-task-name build-cython-ext
```

No upload, publish, share, public, private upload-visibility, or leaderboard flag
belongs in the first managed pilot. The raw jobs directory remains private.

## Claim Boundary

This custom-agent bridge may support the claim:

```text
Harbor can import a LoopX managed Codex agent for the official private
no-upload Terminal-Bench pilot surface.
```

It must not support these claims yet:

- managed pilot success or failure;
- Terminal-Bench official score;
- leaderboard readiness;
- LoopX score uplift;
- token/cost improvement;
- paper-ready evidence.

## Next Action

Run exactly one private no-upload managed Codex single-task pilot for
`terminal-bench@2.0` task `build-cython-ext`, using the custom
`--agent-import-path` above. If the pilot cannot start or finish, record the
first concrete blocker as a compact `benchmark_run_v0` event without copying
raw logs, local paths, credentials, or task artifacts into public notes.

## Smoke

```bash
python3 examples/terminal-bench-managed-codex-custom-agent-smoke.py
```

The smoke validates the public command shape, custom-agent import path,
managed-policy metadata, deferred context write, token-count fallback parser,
no-upload boundary, and dependency-free adapter behavior with fake Harbor
modules. A separate targeted `uvx` probe validates that the real commit-pinned
Harbor environment can import the adapter.
