"""KunlunCode stdio MCP entrypoint."""

from __future__ import annotations

from pathlib import Path

from loopx.goal_mode_mcp import GoalModeMCPConfig, create_fastmcp_server
from loopx.kunluncode_goal_mode.context import goal_context
from loopx.kunluncode_goal_mode.guards import guard_native_controller_writeback


CONFIG = GoalModeMCPConfig(
    server_name="loopx-kunluncode",
    runtime_profile="kunluncode",
    legacy_host_surface="kunluncode",
    setup_hint="run loopx-kunluncode connect --project <dir> --goal-id <goal>",
)
mcp, control = create_fastmcp_server(CONFIG, lambda: goal_context(Path.cwd()))
guard_native_controller_writeback(control)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
