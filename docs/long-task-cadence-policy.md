# Long-Task Cadence Hint

LoopX should not let a recurring heartbeat turn long-running agent work into
tiny status-only turns. The cadence hint is a small, derived signal that tells a
host or controller whether recent work looks blocked, thin, material, or
unknown.

It is intentionally not a scheduler policy. Quota, gates, goal boundaries,
permissions, public/private scans, and user/controller decisions remain the
source of truth.

## Why It Exists

Heartbeat automation is useful because it keeps goals alive, but frequent
wakeups can fragment work when every turn is treated as a separate tiny task.
The hint helps product surfaces notice patterns such as:

- repeated status or single-surface writeback without a coherent artifact;
- a real gate where widening would be unsafe;
- recent validated progress where the current cadence can stay as-is;
- missing or incomplete metadata where the product should avoid strong claims.

The hint should steer the next turn gently. It must not grant permissions, skip
gates, authorize destructive git, start production actions, copy private
material, or expose conversation transcripts, raw local logs, credentials,
benchmark task text, verifier output, or local absolute paths.

## Public Fields

Status and quota may expose this compact projection:

```json
{
  "long_task_cadence_hint": {
    "schema_version": "cadence_hint_v0",
    "signal": "thin_progress",
    "recommendation": "widen",
    "reason_codes": ["repeated_surface_only"]
  }
}
```

Stable fields:

| Field | Values | Meaning |
| --- | --- | --- |
| `schema_version` | `cadence_hint_v0` | The public projection shape. |
| `signal` | `blocked`, `thin_progress`, `material_progress`, `unknown` | What the recent control-plane evidence suggests. |
| `recommendation` | `wait`, `widen`, `keep` | A lightweight host/controller hint. |
| `reason_codes` | compact strings | Machine-readable explanation for the signal. |

Typical examples:

```json
{
  "schema_version": "cadence_hint_v0",
  "signal": "blocked",
  "recommendation": "wait",
  "reason_codes": ["quota_state_operator_gate", "open_user_todos_visible"]
}
```

```json
{
  "schema_version": "cadence_hint_v0",
  "signal": "material_progress",
  "recommendation": "keep",
  "reason_codes": ["implementation_plus_validation_latest_turn"]
}
```

```json
{
  "schema_version": "cadence_hint_v0",
  "signal": "unknown",
  "recommendation": "keep",
  "reason_codes": ["missing_recent_runs"]
}
```

## How It Is Derived

The hint is derived from existing public-safe control-plane metadata:

- recent run `delivery_batch_scale`, `delivery_outcome`, and
  `delivery_turn_kind`;
- the configured execution profile's small-step threshold;
- quota state;
- whether open user todos are already visible.

The current "thin progress" detector is deliberately conservative. It is based
on agent writeback metadata, not a perfect measure of actual agent-loop runtime.
Elapsed wall time may become an optional future input, but it should not be the
primary judge: a short validated fix can be valuable, and a long turn can still
be stuck.

## Controller Use

- `blocked` + `wait`: do not widen; show the concrete gate or blocker.
- `thin_progress` + `widen`: the next eligible turn should try for a coherent
  artifact plus validation/writeback, or write a blocker explaining why widening
  is unsafe.
- `thin_progress` + `keep`: the latest turn was small, but the streak is not yet
  strong enough to steer the next turn.
- `material_progress` + `keep`: recent work produced a broader artifact,
  validation, or milestone.
- `unknown` + `keep`: metadata is missing or insufficient; avoid strong
  automation changes.

The current smoke for this contract is
`python3 examples/long-task-cadence-policy-smoke.py`.
