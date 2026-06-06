# Interface Budget Contract

Goal Harness keeps hot-path worker surfaces small enough that a short heartbeat
can route work without reading raw run history or long chat context. This is a
restraint contract, not an encouragement to add more state surfaces. Each
surface below has a single owner, a named consumer action, a cold-path fallback,
and size/count budgets.

| Surface | Owner | Consumer Action | Cold Path | Size Budget | Nested Budget | Count Budget |
| --- | --- | --- | --- | --- | --- | --- |
| `heartbeat_prompt_json` | heartbeat automation | wake and route one bounded turn | `quota should-run`, `status`, or `review-packet --handoff-only` | `json_chars <= 3500` plus `interface_budget.within_budget=true` | `nested_keys <= 40` | `top_level_keys <= 25` |
| `review_packet_handoff_only_json` | project-agent handoff | forward the smallest sufficient task packet | full `review-packet` or run-history artifact | `json_chars <= 3000` plus `handoff_interface_budget.within_budget=true` | `nested_keys <= 40` | `top_level_keys <= 18` |
| `quota_should_run_json` | quota guard | decide whether the selected goal may spend compute | `status`, `history`, or active state | `json_chars <= 7000` | `nested_keys <= 180` | `top_level_keys <= 45` |
| `dashboard_status_json` | operator dashboard | render first-screen operator state | `history`, run artifacts, or project-local adapter output | `json_chars <= 13000` | `nested_keys <= 260` | `top_level_keys <= 20` |

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
