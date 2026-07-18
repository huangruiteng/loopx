from __future__ import annotations

from typing import Any


def build_todo_write_hint(goal_id: str) -> dict[str, str]:
    return {
        "rule": "Write user/owner actions to User Todo, not Next Action/docs/chat.",
        "user_gate_command_template": (
            f"loopx todo add --goal-id {goal_id} --role user "
            "--task-class user_gate --blocks-agent <agent-id> "
            "--text '<blocking user decision>'"
        ),
        "user_action_command_template": (
            f"loopx todo add --goal-id {goal_id} --role user "
            "--task-class user_action --bound-agent <id> --text '<action>'"
        ),
        "agent_todo_command_template": (
            f"loopx todo add --goal-id {goal_id} --role agent --text '<agent action>'"
        ),
        "section": "User Todo / Owner Review Reading Queue",
    }


def build_capability_resolution_writeback_actions(
    capability_gate: Any,
    *,
    goal_id: str,
    agent_id: str | None,
    limit: int = 3,
) -> list[str]:
    if not isinstance(capability_gate, dict):
        return []
    bindings = capability_gate.get("resolution_bindings")
    if not isinstance(bindings, list):
        return []
    targeted_capabilities = {
        str(capability)
        for candidate in capability_gate.get("runnable_candidates") or []
        if isinstance(candidate, dict)
        for capability in candidate.get("target_capabilities") or []
        if str(capability).strip()
    }
    actions: list[str] = []
    agent = agent_id or "<registered-agent>"
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        owner = str(binding.get("owner") or "").strip()
        capability = str(binding.get("capability") or "").strip()
        todo_id = str(binding.get("primary_blocked_todo_id") or "").strip()
        priority = str(binding.get("priority") or "P1").strip().upper()
        if not capability or not todo_id:
            continue
        if priority not in {"P0", "P1", "P2"}:
            priority = "P1"
        if owner == "user":
            text = (
                f"[{priority}-user] Provide or authorize capability {capability} "
                f"required by {todo_id}."
            )
            actions.append(
                f"loopx todo add --goal-id {goal_id} --role user "
                "--task-class user_gate --action-kind provide_capability "
                f"--target-capability {capability} --blocks-agent {agent} "
                f"--unblocks-todo-id {todo_id} --text '{text}'"
            )
        elif owner == "agent" and capability not in targeted_capabilities:
            text = (
                f"[{priority}] Observe or materialize and real-callsite verify "
                f"capability {capability} required by {todo_id}."
            )
            claimed_arg = f" --claimed-by {agent_id}" if agent_id else ""
            actions.append(
                f"loopx todo add --goal-id {goal_id} --role agent "
                "--task-class advancement_task --action-kind materialize_capability "
                "--required-capability shell "
                f"--target-capability {capability}{claimed_arg} "
                f"--unblocks-todo-id {todo_id} --text '{text}'"
            )
        if len(actions) >= limit:
            break
    return actions
