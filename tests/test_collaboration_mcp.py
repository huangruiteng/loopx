"""The real stdio bridge binds identity and rechecks revocation per call."""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_scoped_stdio_tools_do_not_offer_shell_or_sender_override(tmp_path):
    registry = tmp_path / "registry.json"
    config = {
        "goals": [
            {
                "id": "delivery",
                "repo": str(tmp_path),
                "coordination": {"registered_agents": ["builder", "reviewer"]},
            }
        ]
    }
    registry.write_text(json.dumps(config))
    brief = {
        "schema_version": "collaboration_brief_v0",
        "purpose": "Review the allocation",
        "context": "The owner rejected proportional rounding.",
        "constraints": ["No orders"],
        "inputs": [],
        "acceptance": ["Check coupled capacity limits"],
        "return_requirement": "Findings",
    }

    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "loopx.collaboration_mcp",
                "--runtime-root",
                str(tmp_path),
                "--registry",
                str(registry),
                "--goal-id",
                "delivery",
                "--agent-id",
                "builder",
                "--workspace",
                str(tmp_path),
            ],
        )
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "read_context",
                "assess_request",
                "request_peer",
                "return_result",
                "consume_peer_result",
            }
            for tool in tools.tools:
                assert not {
                    "agent_id",
                    "goal_id",
                    "runtime_root",
                    "command",
                    "path",
                } & set(tool.inputSchema.get("properties", {}))
            result = await session.call_tool(
                "request_peer",
                {
                    "peer_agent_id": "reviewer",
                    "operation_id": "review-1",
                    "brief": brief,
                },
            )
            assert not result.isError
            result = await session.call_tool(
                "request_peer",
                {
                    "peer_agent_id": "unknown",
                    "operation_id": "review-2",
                    "brief": brief,
                },
            )
            assert result.isError
            # Changing registration affects this already-running server.
            config["goals"][0]["coordination"]["registered_agents"] = ["reviewer"]
            registry.write_text(json.dumps(config))
            result = await session.call_tool("read_context", {})
            assert result.isError
            result = await session.call_tool(
                "request_peer",
                {
                    "peer_agent_id": "reviewer",
                    "operation_id": "review-3",
                    "brief": brief,
                },
            )
            assert result.isError

    asyncio.run(exercise())
