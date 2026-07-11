from __future__ import annotations

from typing import Any

from ..markdown import markdown_code, markdown_table_row, markdown_table_separator


def render_trajectory_hygiene_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return "# LoopX Trajectory Hygiene\n\n- ok: `False`\n- error: " + str(payload.get("error"))

    sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    boundary = (
        payload.get("training_boundary")
        if isinstance(payload.get("training_boundary"), dict)
        else {}
    )
    lines = [
        "# LoopX Trajectory Hygiene",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- goal_filter: `{payload.get('goal_filter')}`",
        f"- compact_history_rows: `{sample.get('compact_history_row_count')}`",
        f"- source: `{sample.get('source')}`",
        f"- seed_model_training_eligible: `{boundary.get('seed_model_training_eligible')}`",
        f"- boundary: {boundary.get('reason')}",
        "",
        markdown_table_row(["metric", "value"]),
        markdown_table_separator(2),
    ]
    for name, value in metrics.items():
        lines.append(markdown_table_row([markdown_code(name), markdown_code(value)]))

    lines.extend(["", "## Channels"])
    for name, value in (payload.get("channel_counts") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    return "\n".join(lines)
