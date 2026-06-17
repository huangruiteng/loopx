# Protocol Action Packet Router Comparison v0

`protocol_action_packet_v0` is the rule-only hot-path baseline for executor
action clarity. It intentionally stays small: `schema_version` plus one compact
`summary` string inside `quota should-run`.

The next experiment must run off the hot path. A comparison record uses schema
`protocol_router_comparison_v0` and checks whether a Codex CLI or optional
LLM-router summary can beat the rule packet on three public-safe criteria:

- `payload_shrinkage`: router summary is meaningfully shorter than the rule
  packet summary.
- `action_clarity`: the primary actor, user-action requirement,
  agent-action requirement, quiet-noop allowance, lane, and no-API boundary are
  preserved.
- `boundary_safety`: the comparison does not read credentials, environment
  variables, private traces, raw session history, model APIs, local artifact
  paths, or benchmark runner logs.

The first fixture is deterministic and does not invoke Codex CLI, direct LLM
API, Harbor, Terminal-Bench, Docker, cloud sandboxes, paid compute, or
leaderboard paths. Direct LLM API wiring remains deferred until this cold-path
comparison shows a measurable clarity or shrinkage gain while preserving the
`quota_should_run_json` hot-path budget.
