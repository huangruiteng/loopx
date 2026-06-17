# Protocol Action Packet Decision v0

## Decision

Keep `protocol_action_packet_v0` as the hot-path protocol simplification
contract for `quota should-run`.

The hot path remains deterministic and rule-only:

- `llm=no_api`
- primary actor: user or agent
- user-action requirement
- agent-action requirement
- quiet-noop allowance
- work lane
- compact action label

Use the Codex CLI wrapper only as an explicit cold-path sidecar experiment. Do
not run it during routine quota/status/heartbeat routing.

Defer direct LLM API wiring until a separate backend-comparison experiment
proves a measurable gain over deterministic labels on payload size,
user/agent-action clarity, and public-boundary safety.

## Evidence

The decision is based on four public-safe slices:

1. `protocol_action_packet_v0` made `quota should-run` expose a compact
   rule-only summary while preserving the detailed guard payload.
2. `protocol_router_comparison_v0` compared advancement, user-action, and
   monitor-only scenarios and kept the minimum payload shrinkage above the
   acceptance floor without model calls.
3. `protocol_action_packet_codex_cli_wrapper_v0` proved the Codex CLI command
   envelope can be represented as a fake-contract smoke without invoking a
   model.
4. The opt-in real Codex CLI probe ran once in an isolated fixture and produced
   a compact sidecar while leaving the default smoke path fake/no-model.

## Operating Rule

`quota should-run`, dashboard status, and recurring heartbeat routing should
consume `protocol_action_packet_v0` directly. They should not call Codex CLI,
direct LLM APIs, runner adapters, Docker/cloud environments, or paid compute.

Cold-path experiments may call Codex CLI only when the command is explicit,
isolated, ephemeral, and sidecar-only. The sidecar may record a final compact
summary, prompt length, return code, and stdout/stderr character counts; it
must not persist raw stderr, raw session history, private traces, credentials,
or local auth material.

## Next Work

The protocol simplification spike is complete enough for the current meta
lane. Future work should move back to the long-horizon benchmark program unless
a concrete protocol regression appears.

The next benchmark-side step is the approved Terminal-Bench/Harbor execution
environment readiness lane: check whether local Docker or an approved cloud
execution environment is available, then attempt a single-task no-submit Harbor
Codex pilot only after the environment and benchmark rules are clear.
