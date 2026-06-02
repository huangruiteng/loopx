from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_prompt import render_quota_guard_command, render_quota_spend_command


DEFAULT_MATERIAL_QUEUE_RULE = "Do not consume the learning material queue unless the user explicitly asks."
DEFAULT_PERMISSION_RULE = "Do not ask for permissions when the current Codex session is already trusted."


def build_heartbeat_prompt(
    *,
    goal_id: str,
    active_state: Path,
    material_queue_rule: str | None = None,
    permission_rule: str | None = None,
) -> dict[str, Any]:
    active_state_text = str(active_state.expanduser())
    resolved_material_rule = material_queue_rule or DEFAULT_MATERIAL_QUEUE_RULE
    resolved_permission_rule = permission_rule or DEFAULT_PERMISSION_RULE
    quota_guard_command = render_quota_guard_command(goal_id)
    quota_spend_command = render_quota_spend_command(goal_id, source="heartbeat")
    task_body = render_heartbeat_task_body(
        goal_id=goal_id,
        active_state=active_state_text,
        quota_guard_command=quota_guard_command,
        quota_spend_command=quota_spend_command,
        material_queue_rule=resolved_material_rule,
        permission_rule=resolved_permission_rule,
    )
    return {
        "ok": True,
        "goal_id": goal_id,
        "active_state": active_state_text,
        "quota_guard_command": quota_guard_command,
        "quota_spend_command": quota_spend_command,
        "material_queue_rule": resolved_material_rule,
        "permission_rule": resolved_permission_rule,
        "task_body": task_body,
    }


def render_heartbeat_task_body(
    *,
    goal_id: str,
    active_state: str,
    quota_guard_command: str,
    quota_spend_command: str,
    material_queue_rule: str,
    permission_rule: str,
) -> str:
    return f"""Advance `{goal_id}` using `{active_state}`.

Before spending delivery compute, run:

```bash
{quota_guard_command}
```

If the result says `should_run=false`, do not do implementation work, adapter
work, file edits, research, or project exploration in this turn. Return a quiet
heartbeat `DONT_NOTIFY` response with the skip reason.

If the result says `should_run=true`:

1. Read the active state and Priority Stack.
2. Choose exactly one bounded, verifiable step.
3. Do that step only. Keep public/private boundaries intact.
4. Run the smallest useful validation.
5. Write back changed files, validation, critic, and next action to the active
   state.
6. If the dashboard or controller needs to see a state-only update, run:

   ```bash
   goal-harness refresh-state --goal-id {goal_id}
   ```

7. After validation and required state refresh are complete, append exactly one
   spend event:

   ```bash
   {quota_spend_command}
   ```

   Do not append spend for `should_run=false` skips, preflight failures, pure
   dry-run previews, or duplicate accounting attempts.

8. Return a compact final report. Use heartbeat `NOTIFY` only for meaningful
   user visibility, such as a committed artifact, a user gate, or a real
   blocker. Otherwise use `DONT_NOTIFY`.

{material_queue_rule}
{permission_rule}"""


def render_heartbeat_prompt_markdown(payload: dict[str, Any]) -> str:
    return f"""# Heartbeat Automation Prompt

Copy this task body into a Codex App heartbeat automation.

````text
{payload.get("task_body", "")}
````

## Generator Inputs

- goal_id: `{payload.get("goal_id")}`
- active_state: `{payload.get("active_state")}`
- quota_guard_command: `{payload.get("quota_guard_command")}`
- quota_spend_command: `{payload.get("quota_spend_command")}`
"""
