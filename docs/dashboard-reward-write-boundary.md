# Dashboard Reward Write Boundary

Goal Harness can already validate a dashboard reward draft through
`POST /reward/dry-run`. A browser-side append path is a separate capability and
must stay opt-in. The default dashboard must remain read-mostly: status export,
run-history inspection, and dry-run validation are allowed; writing compact
reward overlays is not enabled by loading the dashboard.

This document defines the boundary for a future `POST /reward/append` endpoint.
It is a design gate, not an implementation promise.

## Current State

- `goal-harness reward` is the canonical writer.
- `goal-harness serve-status` serves `GET /status.json` and
  `POST /reward/dry-run` on loopback.
- The dry-run endpoint validates goal id, selected run timestamp, reward value,
  public-safe text, and run artifact availability.
- Dry-run responses are compact and return `appended=false`.
- The dashboard can show the CLI command and the dry-run result, but cannot
  append to `index.jsonl`.

## Append Preconditions

A browser append endpoint may be implemented only when all of these are true:

- The server is started with an explicit write flag, for example
  `--enable-reward-write-api`. The flag must default to off.
- The server binds to loopback only. A non-loopback bind should reject enabling
  reward writes.
- The operator supplies or confirms a capability token for the browser session.
  The token must not appear in public examples, status JSON, or logs.
- The append request targets an exact `goal_id` and `run_generated_at`; appending
  to an implicit latest run from the browser is not allowed.
- The payload has already passed the same validation as `/reward/dry-run`.
- The response remains compact and does not return `index_path`, `json_path`,
  `markdown_path`, local absolute paths, or raw private evidence.

## Preview Handshake

Append should be a two-step flow:

1. The dashboard calls `POST /reward/dry-run` with the selected goal, selected
   run timestamp, and compact reward fields.
2. The server returns a `preview_id` derived from the selected run key, compact
   reward payload, and current raw index record count.
3. The dashboard can enable an append control only for that exact preview.
4. `POST /reward/append` recomputes the preview id and rejects the request if
   the payload changed, the selected run changed, or the raw index record count
   changed since preview.

This keeps the UI from appending feedback to a stale or different run after the
operator has reviewed a dry-run result.

## Request Shape

Future append requests should accept only compact fields:

```json
{
  "goal_id": "example-experiment-goal",
  "run_generated_at": "2026-06-01T00:00:00+00:00",
  "preview_id": "opaque-preview-id",
  "decision": "continue_route",
  "reward": "positive",
  "reason_summary": "comparable validation improved and the route is worth extending",
  "follow_up": "promote the route to the next longer-window check"
}
```

The endpoint should reject unknown or private-looking fields rather than ignore
them silently. Rejected text should reuse the same private-pattern checks as
`goal-harness reward`.

## Origin And Capability Checks

The write path needs stricter browser checks than the dry-run path:

- Allow CORS for the append endpoint only from configured loopback dashboard
  origins, such as `http://127.0.0.1:5173`.
- Require a write capability token in a header or explicit field.
- Do not expose the token through `GET /`, `GET /status.json`, dashboard demo
  JSON, or generated static artifacts.
- Return `403` for missing capability and `409` for stale preview.
- Keep `GET /status.json` and `POST /reward/dry-run` usable without enabling
  append writes.

## UI Rules

The dashboard should not make reward writes feel like ordinary form submission:

- Default state is `Dry-run Check`.
- A write control appears only after a successful preview and explicit server
  capability.
- The control label should name the consequence, for example
  `Append reward overlay`.
- The confirmation copy should say that the action appends one compact
  `human_reward` row to the selected run index.
- After append, the dashboard should refresh status and show the new compact
  reward signal from `goal-harness status`.

## Validation Before Implementation

An implementation PR should prove:

- Starting `serve-status` without the write flag exposes no append endpoint.
- Starting with the write flag on a non-loopback host fails.
- Append without capability fails and leaves the index unchanged.
- Append with a stale preview fails and leaves the index unchanged.
- Append with a changed payload fails and leaves the index unchanged.
- Append with public-safe text writes exactly one JSONL overlay row.
- The status export shows `human_reward` after append and still hides local
  paths.
- The dashboard can complete dry-run -> append -> refresh in a browser smoke
  test.

Until those checks exist, the CLI remains the only reward writer.
