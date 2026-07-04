# event_store_migration_bridge_v0

`event_store_migration_bridge_v0` is the fail-closed bridge between the
Markdown active-state read model and a future event projection read model.

It does not make the event projection canonical. It records the gates that must
be clean before a reviewed runtime change may prefer event projection for
status, quota, review packets, dashboards, or slash-command reads.

## Contract

The bridge packet is built by
`loopx.control_plane.runtime.event_store_migration_bridge.build_event_store_migration_bridge`
and carries:

- `source_of_truth`: currently `markdown_active_state`;
- `candidate_source`: currently `event_projection`;
- `stage`: one of `wait_for_event_read_path`, `dual_read_shadow`,
  `bounded_canary`, or `promotion_candidate`;
- `promotion_allowed`: always `false` in this bridge contract;
- `promotion_candidate`: true only when all pre-promotion checks are clean;
- `checks`: compact booleans for read-path, parity, rollback, canary,
  idempotency, projection-head, and public-boundary readiness;
- `missing_for_shadow`, `missing_for_canary`, and `missing_for_promotion`;
- `dual_read`, `rollback`, and `canary` subcontracts.

## Stages

`wait_for_event_read_path` means the event read path or structured
active-state projection is not ready. The only safe action is to finish those
prerequisites.

`dual_read_shadow` means both read models may be compared, but Markdown remains
the source of truth. Any parity delta must prefer Markdown and record a compact
delta rather than silently promoting event projection.

`bounded_canary` means parity, rollback, idempotency, projection-head, and
public-boundary checks are clean enough to run a small read-only canary. The
canary uses a limited goal set and duration, with event write preference still
disabled.

`promotion_candidate` means the bridge has enough evidence to propose a
separate reviewed runtime PR. It is not an automatic promotion state.

## Required Gates

Promotion requires all of these to be clean:

- event read path ready;
- active-state structured projection ready;
- dual-read parity clean for todo ids, status, priority/planner order,
  `claimed_by`, gate refs, and projection head sequence;
- event projection head matches the event store head;
- rollback plan recorded;
- bounded canary passed;
- idempotency conflicts clean;
- public boundary clean.

## Rollback

Rollback is mandatory. The fallback source is always the Markdown active-state
parser until a later reviewed write-path change changes the source of truth.

Rollback triggers include:

- parity delta;
- projection head mismatch;
- event append conflict;
- public boundary warning;
- canary regression.

The rollback action is to disable event projection preference and keep the
Markdown parser as canonical read fallback.

## Canary

The bounded canary is read-only:

- small goal limit, default 1;
- short duration, default 30 minutes;
- event write path disabled;
- read preference remains Markdown;
- observe status todo summaries, quota selected todo, review packet todo refs,
  dashboard/frontstage projection, and event projection head sequence.

Success requires no parity delta, no idempotency conflict, no private-boundary
warning, and a one-command-safe rollback.
