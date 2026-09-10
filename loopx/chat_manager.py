"""The built-in machine manager's shared conversation service and audience boundary."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

MANAGER_AGENT_GOAL_ID = "loopx-manager"
MANAGER_AGENT_OBJECTIVE = (
    "Serve as the user's LoopX Goal manager. Answer only the current user message in concise Chinese. "
    "Summarize and clarify Goal state, and convert requested durable changes into bounded proposals. "
    "Do not inspect repositories, modify files, run commands, or mutate LoopX state in this Chat Turn. "
    "Goal, Todo, Agent, heartbeat, monitor, gate, and correction changes must be presented through "
    "the typed preview and explicit apply control plane. Never claim that a durable change happened "
    "until the control plane returns a verified receipt. "
    "Background work belongs to the selected worker Agent; respond in this conversation without waiting for a heartbeat."
)


def manager_channel(*, provider: str = "", audience: str = "") -> str:
    """One manager service, separate owner and external-audience transcripts."""
    if not provider and not audience:
        return "manager"
    if not provider or not audience:
        raise ValueError(
            "an external manager conversation requires a provider and audience"
        )
    digest = hashlib.sha256(f"{provider}\0{audience}".encode()).hexdigest()[:24]
    return f"manager.external.{digest}"


def is_manager_channel(value: Any) -> bool:
    return value == "manager" or str(value or "").startswith("manager.external.")


def open_manager_session(
    *,
    controller: Any,
    goal_id: str,
    work_dir: Path,
    executor_endpoint_id: str = "codex",
    provider: str = "",
    audience: str = "",
) -> tuple[dict[str, Any], bool]:
    return controller.open_session(
        goal_id=goal_id,
        agent_id=executor_endpoint_id,
        work_dir=work_dir,
        objective=MANAGER_AGENT_OBJECTIVE,
        mode="resume_latest",
        channel_id=manager_channel(provider=provider, audience=audience),
        agent_goal_id=MANAGER_AGENT_GOAL_ID,
    )
