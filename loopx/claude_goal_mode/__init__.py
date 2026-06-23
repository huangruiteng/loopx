"""Claude Code goal-mode integration for loopx.

loopx is a deterministic (no-LLM) control plane. Codex has a native goal API;
Claude Code's native ``/goal`` decides completion by a model reading the
transcript, which conflicts with loopx deciding continuation deterministically —
so goal-mode for Claude Code is *constructed* from Claude Code extension points
and packaged here in the loopx package:

- ``hooks/goal_policy.py``   — PreToolUse permission gate (deterministic allow/deny)
- ``hooks/goal_state.py``    — registry-driven goal context + "armed" (heartbeat) check
- ``mcp/loopx_mcp.py``       — MCP server exposing loopx state to the agent
- ``scripts/heartbeat_timer.py`` — launchd heartbeat (the Codex recurring-automation analogue)
- ``scripts/goal_run.py``    — one heartbeat tick: should_run -> heartbeat-prompt -> claude -p
- ``scripts/goalmode_cmd.py``— the ``/loopx`` slash-command entry
- ``scripts/install.py``     — wires the above into ~/.claude
- ``plugin``-style assets    — ``.claude-plugin/plugin.json``, ``hooks/hooks.json``,
  ``commands/loopx.md``, ``statusline/goal_status.py``

The honest backend contract lives in :mod:`loopx.claude_goal_baseline`.
"""

__all__: list[str] = []
