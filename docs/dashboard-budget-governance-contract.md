# Dashboard Budget Governance Contract

Status: public-safe v0 contract for the LoopX ops dashboard.

LoopX budget and governance are already present in the kernel objects: quota,
scheduler hints, todo ownership, gates, run history, and evidence pointers. The
dashboard contract turns those machine fields into operator concepts without
creating a browser-side source of truth.

## Operator Concepts

| Operator concept | Source fields | Meaning in the dashboard |
| --- | --- | --- |
| Budget | `quota.compute`, `quota.allowed_slots`, `quota.spent_slots`, `quota.state` | How much automatic agent time this goal may consume in the current quota window, and whether it can run now. |
| Cadence | `scheduler_hint.codex_app`, `scheduler_hint.local_scheduler`, `scheduler_hint.reset_policy` | How often the host should wake the agent, when backoff applies, and when user feedback or new work resets the interval. |
| Spend rule | `interaction_contract.cli_channel.spend_policy`, `scheduler_hint.*.no_spend_*`, `work_lane_contract` | Which transitions spend quota and which lifecycle checks are no-spend. |
| Human controls | user todos, operator gates, `local_dashboard_api`, future control-plane dry-run/apply paths | What a human can approve, pause, override, or resume, and whether the browser is allowed to preview or apply a change. |
| Evidence | todo ids, run ids, quota spend events, compact artifacts, source warnings | Why the dashboard believes the current budget/governance state and where to audit it. |

The dashboard should phrase these concepts for operators, but drill-down views
may still show the exact machine tokens for debugging.

## Control Semantics

- **Pause automatic work:** projected as a quota/control-plane policy change,
  not as a hidden browser flag. Apply paths require local loopback opt-in and a
  preview id, or the equivalent CLI command.
- **Run now / override cadence:** starts with a fresh `quota should-run`; it
  does not skip gates, claims, write scope, or capability checks.
- **Reset cadence:** follows `scheduler_hint.reset_policy`. User feedback, new
  or reassigned todos, gate resolution, and material state transitions reset the
  host interval to the profile's initial value before backoff resumes.
- **Stop or final-check loops:** Codex CLI TUI and Claude Code loop final
  checks, loop exits, cadence changes, and monitor-only quiet polls are
  no-spend transitions unless they produce validated work and writeback.
- **Spend quota:** only after durable writeback: todo/state/evidence update,
  `refresh-state`, then one `quota spend-slot` event.

## Dashboard Projection

The ops frontstage may render a compact `Budget & Governance` panel derived
from `goal_channel_projection_v0`:

```json
{
  "quota": {
    "state": "eligible",
    "spent_slots": "2",
    "allowed_slots": "10",
    "scheduler_rrule": "FREQ=MINUTELY;INTERVAL=3",
    "scheduler_reset_token": "fixture-reset-token",
    "spend_policy": "spend after validated writeback",
    "pause_policy": "control-plane policy only",
    "override_policy": "fresh quota guard required",
    "latest_evidence_ref": "run:validated_progress_fixture"
  }
}
```

The panel is read-only. It may link to todo ids, run events, local dry-run
capabilities, and source warnings, but it must not mutate project truth directly.

## Acceptance Anchors

- `frontstage-budget-governance` renders budget, cadence, spend rule, controls,
  and evidence from compact projection fields.
- The copy says cadence/final-check/monitor-only transitions are no-spend.
- Write affordances remain behind `local_dashboard_api` loopback opt-in and
  preview-locked APIs.
- Public docs link this contract from the dashboard/status docs index.

## Related Contracts

- [Quota allocation](quota-allocation.md)
- [Status data contract](status-data-contract.md)
- [Long-task cadence hint](long-task-cadence-policy.md)
- [Frontstage dashboard interaction baseline](product/frontstage-dashboard-interaction-baseline.md)
- [Runtime connector catalog](runtime-connector-catalog.md)
