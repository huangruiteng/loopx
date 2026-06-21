# Interface Budget Contract

LoopX keeps hot-path worker surfaces small enough that a short heartbeat
can route work without reading raw run history or long chat context. This is a
restraint contract, not an encouragement to add more state surfaces. Each
surface below has a single owner, a named consumer action, a cold-path fallback,
and size/count budgets.

| Surface | Owner | Consumer Action | Cold Path | Size Budget | Nested Budget | Count Budget |
| --- | --- | --- | --- | --- | --- | --- |
| `heartbeat_prompt_json` | heartbeat automation | wake and route one bounded turn | `quota should-run`, `status`, or `review-packet --handoff-only` | `json_chars <= 3500` plus `interface_budget.within_budget=true` | `nested_keys <= 40` | `top_level_keys <= 25` |
| `review_packet_handoff_only_json` | project-agent handoff | forward the smallest sufficient task packet | full `review-packet` or run-history artifact | `json_chars <= 3000` plus `handoff_interface_budget.within_budget=true` | `nested_keys <= 40` | `top_level_keys <= 18` |
| `quota_should_run_json` | quota guard | decide whether the selected goal may spend compute | `status`, `history`, or active state | `json_chars <= 8500` | `nested_keys <= 220` | `top_level_keys <= 45` |
| `dashboard_status_json` | operator dashboard | render first-screen operator state | `history`, run artifacts, or project-local adapter output | `json_chars <= 13500` | `nested_keys <= 260` | `top_level_keys <= 20` |

These budgets are intentionally about the machine payloads, not the full
archival facts. When a surface needs more detail, put that detail behind a
queryable cold-path command or a linked run-history artifact instead of making
the recurring heartbeat prompt carry it. `nested_keys` counts dictionary keys
through three payload levels and samples at most 20 list items per level; it is a
hot-path structure budget, not an archival record-size budget.

Restraint rules for new fields:

1. Prefer adding evidence to run history, then projecting only the smallest
   decision summary into a hot-path surface.
2. A hot-path field must answer a current consumer action. If the consumer only
   says "nice to inspect", keep the field in the cold path.
3. A new nested object must either stay within the nested budget above or retire
   / compact an older field in the same surface.
4. Do not add prompt branches to compensate for an unclear payload. Clarify the
   status/quota/review-packet contract instead.
5. If a short worker would need to read more than one hot-path payload before it
   can choose the next action, demote the extra detail to a cold-path command.

The regression entrypoint is:

```bash
python3 examples/hot-path-interface-budget-smoke.py
```

Cadence contract:

The same smoke also emits and validates an `interface_budget_cadence` summary
for clean drift checks. A drift-check run may record that summary in run
history; `loopx status` projects it under
`attention_queue.items[].project_asset.interface_budget_cadence`, and
`quota should-run` mirrors the selected goal summary at top level. This lets a
short heartbeat quiet-skip a still-fresh clean check without losing the ongoing
guard todo.

Stable cadence fields:

- `checked_at`: when the hot-path budget check was run.
- `freshness_hours`: how long the clean check remains fresh.
- `next_check_due_at`: when the next check is due.
- `overdue`: whether the current summary is past `next_check_due_at`.
- `within_budget`: whether all measured hot-path surfaces fit their budgets.
- `minimum_headroom_ratio`, `tightest_surface`, `tightest_metric`, and
  `headroom_remaining`: compact headroom evidence for the tightest observed
  surface.
- `recommendation`: either `quiet_skip_until_next_check_due` or
  `rerun_hot_path_interface_budget_smoke`.

Do not add a heartbeat prompt branch for this cadence. Store exact measurements
in run history, project only this compact decision summary, and rerun the smoke
when `overdue=true` or when a prompt/status/quota/review-packet/dashboard
contract changes.
