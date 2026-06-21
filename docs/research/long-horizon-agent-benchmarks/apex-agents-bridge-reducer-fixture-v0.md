# APEX-Agents Bridge/Reducer Fixture V0

Date: 2026-06-12

## Scope

This note records the first deterministic no-run fixture for the APEX-Agents
host-Codex bridge/reducer route described in
`apex-agents-codex-bridge-reducer-packet-v0.md`.

The fixture is deliberately not an APEX run. It proves only that LoopX
can reduce a redacted Archipelago/APEX bridge observation into compact public
`benchmark_run_v0` and `benchmark_result_v0` events while preserving the
official-score versus control-plane-score boundary.

## Fixture Shape

The executable fixture is
`examples/apex-agents-bridge-reducer-smoke.py`.

It constructs a private in-memory `apex_agents_bridge_fixture_v0` object with:

- one redacted task selector hash and one redacted world selector hash;
- a compact MCP readiness map summarized into count plus hash;
- private trajectory metadata with zero raw messages;
- compact grading metadata that records `not_run_fixture_only`;
- explicit false markers for gated dataset access, task material access,
  Docker start, dependency install, Codex/model invocation, real grading,
  upload, submit, public ranking path, credential read, raw artifact read, and
  shared-host workload inspection.

The reducer emits:

- `benchmark_run_v0` with `source_runner=archipelago`,
  `benchmark_id=apex-agents`, the current benchmark and Archipelago revisions,
  `mode=host_codex_external_mcp_adapter`, one pending blocked trial, zero token
  and cost metrics, and no-upload/no-submit/no-public-ranking validation flags;
- `benchmark_result_v0` with `official_task_score.status=not_run` separated
  from `control_plane_score_core_v0`, plus claim-boundary flags that disallow
  official-score and real-run claims.

## Validation

The smoke asserts:

- both public events have the expected schema versions;
- no Archipelago import, Docker start, dependency install, Codex/model call,
  real grading, upload, submit, public ranking path, credential read, raw
  artifact read, or shared-host workload inspection occurred;
- forbidden public field names such as task body, instruction, rubric, gold,
  world file, raw message, trajectory, screenshot, credential, session, and
  local path are absent from the public events;
- forbidden public text markers such as local user paths, Codex auth/config
  paths, common key environment names, Hugging Face download calls, Docker
  start commands, public ranking text, and submission text are absent.

Targeted validation:

```bash
python3 examples/apex-agents-bridge-reducer-smoke.py
python3 -m py_compile examples/apex-agents-bridge-reducer-smoke.py
loopx check \
  --scan-path examples/apex-agents-bridge-reducer-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/apex-agents-bridge-reducer-fixture-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

## Boundary

This fixture does not remove the APEX real-run gates. Before a real pilot,
owner approval is still required for gated Hugging Face dataset access, task
material access, Docker or remote provider execution, Codex/model invocation,
grading, artifact handling, and any upload or public ranking surface.

The next autonomous APEX step should stay no-run unless those gates change.
Useful no-run follow-up would be to reuse this reducer shape for another
external-MCP benchmark bridge or to wire a generic benchmark-run append path
against a synthetic `benchmark_run_v0` / `benchmark_result_v0` pair.
