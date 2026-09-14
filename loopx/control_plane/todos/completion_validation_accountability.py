"""Accountable refresh fence for controller-validated Todos."""

from __future__ import annotations

from typing import Any

from ..turn_driver.delivery_continuity import DELIVERY_BOUNDARY_IN_FLIGHT
from ..work_items.delivery_outcome import DeliveryOutcome
from .active_state_todo_parser import parse_active_state_todos
from .completion_validation_projection import pending_completion_validation_todo


def require_accountable_completion_validation(
    state_text: str,
    *,
    todo_id: str | None,
    agent_id: str | None,
    todo_fields: dict[str, Any] | None = None,
    delivery_boundary: str | None = None,
    delivery_outcome: str | None = None,
) -> None:
    """Reject accountable evidence while its exact validation Todo is open."""

    if (
        delivery_boundary == DELIVERY_BOUNDARY_IN_FLIGHT
        and delivery_outcome == DeliveryOutcome.OUTCOME_PROGRESS.value
    ):
        return
    fields = todo_fields if todo_fields is not None else parse_active_state_todos(state_text, item_limit=None)
    summary = fields.get("agent_todos")
    pending = pending_completion_validation_todo(
        summary,
        todo_id=todo_id,
        agent_id=agent_id,
    )
    if pending is not None:
        raise ValueError(
            "accountable refresh is blocked until controller-declared completion "
            f"validation durably completes todo {pending.get('todo_id')}"
        )
