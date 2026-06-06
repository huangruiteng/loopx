# Interface Budget Contract

Goal Harness keeps hot-path worker surfaces small enough that a short heartbeat
can route work without reading raw run history or long chat context. Each
surface below has a single owner, a size budget, and a count budget.

| Surface | Owner | Size Budget | Count Budget |
| --- | --- | --- | --- |
| `heartbeat_prompt_json` | heartbeat automation | `json_chars <= 3500` plus `interface_budget.within_budget=true` | `top_level_keys <= 25` |
| `review_packet_handoff_only_json` | project-agent handoff | `json_chars <= 3000` plus `handoff_interface_budget.within_budget=true` | `top_level_keys <= 18` |
| `quota_should_run_json` | quota guard | `json_chars <= 7000` | `top_level_keys <= 45` |
| `dashboard_status_json` | operator dashboard | `json_chars <= 13000` | `top_level_keys <= 20` |

These budgets are intentionally about the machine payloads, not the full
archival facts. When a surface needs more detail, put that detail behind a
queryable cold-path command or a linked run-history artifact instead of making
the recurring heartbeat prompt carry it.

The regression entrypoint is:

```bash
python3 examples/hot-path-interface-budget-smoke.py
```
