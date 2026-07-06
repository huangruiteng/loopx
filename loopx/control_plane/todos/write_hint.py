from __future__ import annotations


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
            "--task-class user_action --text '<non-blocking user todo>'"
        ),
        "agent_todo_command_template": (
            f"loopx todo add --goal-id {goal_id} --role agent --text '<agent action>'"
        ),
        "section": "User Todo / Owner Review Reading Queue",
    }
