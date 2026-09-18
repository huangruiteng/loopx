"""Explicit, identity-scoped stdio tools for a sandboxed working Agent.

The configured host owns the registry/runtime/Goal/Agent binding. Model tool
arguments cannot choose another sender, filesystem root or external audience.
These tools expose the same inbox operations as the trusted local CLI; they
never expose a shell, Todo writes, execution grants or a network listener.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

from .control_plane.collaboration.inbox import acknowledge, _entry
from .control_plane.collaboration.peers import (
    _goal,
    consume_return,
    read_inbox,
    request,
)


def create_server(
    root: Path, registry: Path, goal_id: str, agent_id: str, workspace: Path
) -> FastMCP:
    _goal(registry, goal_id, agent_id)
    server = FastMCP("loopx-collaboration")

    def check_scope():
        # Revocation is read on every tool call, including a long-lived server.
        _goal(registry, goal_id, agent_id)

    @server.tool()
    def read_context() -> dict:
        """Read pending requests, material version checks and unconsumed peer results."""
        return read_inbox(root, registry, goal_id, agent_id, workspace=workspace)

    @server.tool()
    def assess_request(
        request_id: str,
        decision: Literal["adopt", "defer", "reject", "no_change"],
        reason: str,
    ) -> dict:
        """Record your independent decision; this does not change task ownership or priority."""
        check_scope()
        return acknowledge(root, goal_id, agent_id, request_id, decision, reason)

    @server.tool()
    def request_peer(
        peer_agent_id: str,
        operation_id: str,
        brief: dict,
        parent_request_id: str | None = None,
    ) -> dict:
        """Request same-Goal peer help/review with a collaboration_brief_v0 and stable retry id.

        Brief fields: schema_version, purpose, context, constraints (strings), inputs
        (relative ref, description, optional sha256), acceptance (nonempty strings),
        return_requirement. Preserve relevant corrections and rejected approaches.
        New review rounds use new operation ids. No worker is launched by this tool.
        """
        check_scope()
        return request(
            root,
            registry,
            goal_id,
            agent_id,
            peer_agent_id,
            operation_id,
            brief,
            parent_request_id,
        )

    @server.tool()
    def return_result(request_id: str, text: str) -> dict:
        """Save an evidence-backed conclusion or explicit blocker for the original requester."""
        check_scope()
        row = _entry(root, goal_id, agent_id, request_id)
        if row.get("source_kind") == "peer":
            from .control_plane.collaboration.peers import return_result as save_result

            return save_result(root, goal_id, agent_id, request_id, text)
        # The host adapter selects Chat/Lark transport; the shared collaboration
        # owner never depends on presentation or manager capabilities.
        from .capabilities.manager_context.roundtrip import report

        return report(root, goal_id, agent_id, request_id, "conclusion", text)

    @server.tool()
    def consume_peer_result(request_id: str) -> dict:
        """Acknowledge a peer result after reading and using/rejecting it; no work-state mutation."""
        check_scope()
        return consume_return(root, goal_id, agent_id, request_id)

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--goal-id", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    create_server(
        args.runtime_root.resolve(),
        args.registry.resolve(),
        args.goal_id,
        args.agent_id,
        args.workspace.resolve(),
    ).run(transport="stdio")


if __name__ == "__main__":
    main()
