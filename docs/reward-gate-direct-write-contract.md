# Reward And Gate Direct-Write Contract

LoopX has two operator decision writes that must stay distinct:
run-bound `human_reward` overlays and `operator_gate` decision runs. Both turn a
human decision into durable runtime evidence, but neither grants write-control,
production access, or permission to skip the next state/registry/quota read.

This document defines the minimal `decision_write_contract_v0` planning slice for
local operator decisions. It is intentionally narrow: use existing CLI and
loopback preview/apply paths before adding any new dashboard control.

## Contract Fields

Every direct-write decision path must expose these public-safe fields before a
write is enabled:

- `decision_kind`: `human_reward` or `operator_gate`.
- `goal_id`: exact goal id.
- `target_ref`: exact selected run timestamp for `human_reward`, or exact
  `gate_id` for `operator_gate`.
- `decision`: compact public-safe decision string.
- `reason_summary`: one compact public-safe reason.
- `follow_up`: optional public-safe next condition.
- `preview_id`: required for browser reward append; omitted for CLI-only gate
  append until a separate gate preview endpoint exists.
- `source_of_truth`: `goal_reward_event_ledger`,
  `run_bound_human_reward_overlay` (legacy compatibility), or
  `operator_gate_decision_run`.
- `write_effect`: what will be appended and what remains unchanged.
- `project_agent_visibility`: the read path a target project agent should use
  after the write.

Unknown fields and private-looking text must be rejected instead of silently
ignored.

## Run-Bound Overlay

A run-bound overlay is a compact append-only annotation attached to one exact
run index row. It is "run-bound" because its target is a specific run, usually
identified by `goal_id` plus `run_generated_at` / run path. It is an "overlay"
because it annotates that prior run without rewriting the original run payload,
active goal state, or every future decision.

For `human_reward`, the overlay records the operator's judgment of that exact
run or route outcome: decision label, reward value, reason summary, follow-up,
and timestamp. Later status, dashboard, and controller-readiness projections may
summarize the overlay, but the run-bound overlay remains the durable source of
truth. It does not grant write-control, production access, public submission
permission, or permission to skip a fresh registry/state/quota read.

## Human Reward

`human_reward` judges one exact run or route outcome. The canonical writer is
`loopx reward`; local dashboards may validate the same compact payload via
`POST /reward/dry-run`.

Browser append is allowed only when all of these are true:

- `serve-status` is running on loopback.
- The server was started with `--enable-reward-write-api`.
- The append request reuses the exact `preview_id` from `/reward/dry-run`.
- The selected `run_generated_at`, compact reward payload, and raw index count
  still match the preview.

Successful append writes one run-bound `human_reward` overlay row for backward
compatibility and one idempotent `user_reward_event_v0` row under the goal's
local reward-event ledger. The event ledger preserves multiple corrections that
target the same run; the run overlay remains the compact dashboard annotation.
Source adapters persist only a source kind and SHA-256 digest, never the raw
message id or source text.

A reward lesson may be `advisory` or `required`, and scoped to a goal,
workspace, repository, or delivery surface. Required lessons are projected into
the next `quota should-run` interaction contract as operating constraints.
Later corrections may list prior `reward_id` values in `supersedes`; superseded
lessons stay auditable but leave the active lesson projection.

For a configured Lark event inbox, use the generic atomic projection path:

```bash
loopx lark-inbox project-reward \
  --project . \
  --config .loopx/config/lark/event-inbox.json \
  --goal-id your-project-goal \
  --message-id om_example \
  --decision owner_correction \
  --reward negative \
  --reason-summary "The current route violates an explicit operating rule." \
  --lesson-kind operating_rule \
  --lesson-summary "Keep new deliveries in the required review state." \
  --lesson-strength required \
  --lesson-scope workspace \
  --execute
```

This command appends or reuses the idempotent reward event, writes the compact
active-state summary, and only then acknowledges the inbox message. A retry is
safe: the source digest resolves to the same reward id and cannot duplicate the
event. Raw inbox content remains local-private and is not copied into reward
state.

## Operator Gate

`operator_gate` answers whether a gated handoff or command may proceed. The
canonical writer is `loopx operator-gate`. The review packet may show a
local `operator_gate_dry_run_command`, but that command belongs to the operator
or controller, not to the target project agent.

There is no dashboard `operator_gate` apply endpoint in this contract. Before
adding one, implement a separate stale-preview handshake equivalent to reward
append and prove that the target agent sees only an approved handoff after the
gate decision run exists.

Approved gates must include an `operator_gate_resume_contract` with the fresh
state check. The receiving agent must re-read current registry, active state,
quota, repo snapshot, policy, and run status before executing the approved
command.

## Dashboard Boundary

The default dashboard remains read-mostly:

- It may render status, run history, review packets, reward CLI drafts,
  `/reward/dry-run`, and control-plane setting dry-runs.
- It may append reward only through loopback `--enable-reward-write-api`.
- It must not expose gate append, reward append, or control-plane apply unless
  the corresponding explicit local write API is enabled.

Adding a new write surface requires a smoke that proves disabled-by-default
behavior, stale-preview rejection, public-safe text validation, exactly one
runtime append, status refresh, and no local path leakage in compact responses.
