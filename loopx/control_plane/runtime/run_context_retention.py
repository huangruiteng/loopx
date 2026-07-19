from __future__ import annotations

from typing import Any


PER_AGENT_CONTEXT_RUN_FIELDS = (
    "agent_vision",
    "vision_checkpoint",
    "autonomous_replan_ack",
)


def latest_runs_with_agent_context(
    runs: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Keep recent runs plus each agent's newest durable context per field."""

    bounded = max(0, limit)
    selected = list(runs[:bounded])
    selected_ids = {id(run) for run in selected}
    retained_context_fields: set[tuple[str, str]] = set()
    retired_agent_visions: set[str] = set()

    for run in runs:
        agent_id = str(run.get("agent_id") or "").strip()
        if not agent_id:
            continue
        fields_to_retain: list[str] = []
        checkpoint = (
            run.get("vision_checkpoint")
            if isinstance(run.get("vision_checkpoint"), dict)
            else {}
        )
        if (
            checkpoint.get("satisfied") is True
            and str(checkpoint.get("decision") or "").strip()
            == "retired_or_superseded"
        ):
            retired_agent_visions.add(agent_id)
            retained_context_fields.add((agent_id, "agent_vision"))

        for field in PER_AGENT_CONTEXT_RUN_FIELDS:
            context_key = (agent_id, field)
            if context_key in retained_context_fields:
                continue
            if not isinstance(run.get(field), dict):
                continue
            if field == "agent_vision" and agent_id in retired_agent_visions:
                continue
            retained_context_fields.add(context_key)
            fields_to_retain.append(field)

        if fields_to_retain and id(run) not in selected_ids:
            selected.append(run)
            selected_ids.add(id(run))
    return selected
