from __future__ import annotations

import shutil
from collections.abc import Mapping
from typing import Any

from ..content_ops.social_browser_x import build_social_browser_x_provider_packet


VALUE_CONNECTOR_INSTALL_CHECK_PACKET_SCHEMA_VERSION = (
    "value_connector_install_check_packet_v0"
)


def build_value_connector_install_check_packet(
    *, connector: str = "all"
) -> dict[str, Any]:
    checks = [
        {
            "connector_id": "github_public_channel",
            "status": "ready" if shutil.which("python3") else "needs_python3",
            "install": [
                "python3 -m pip install -e .",
                "loopx value-connectors github-public-probe --url https://github.com/owner/repo/issues/1 --format json",
                "loopx value-connectors github-public-probe --url https://github.com/owner/repo/issues/1 --fetch-metadata --format json",
                "loopx value-connectors github-reply-monitor --issue-url https://github.com/owner/repo/issues/1 --after-comment-url https://github.com/owner/repo/issues/1#issuecomment-1 --fetch-metadata --format json",
            ],
            "optional_tools": [
                {
                    "tool": "gh",
                    "installed": shutil.which("gh") is not None,
                    "needed_for": "discussion metadata fetch and reply-monitor metadata fetch",
                    "install_hint": "Install GitHub CLI and run `gh auth login` if discussion metadata is needed.",
                }
            ],
            "external_write_capability": False,
        },
        {
            "connector_id": "agent_reach_ops_source_map",
            "status": "ready" if shutil.which("agent-reach") else "needs_agent_reach",
            "install": [
                "Install Agent-Reach when available, then run `agent-reach doctor --json`.",
                "Use `loopx value-connectors source-map --connector agent_reach_ops_source_map --format json` before drafting from external signals.",
                "Keep Agent-Reach routes read-only; use LoopX evidence cards, maturity scores, and publish/audit gates for action.",
            ],
            "optional_tools": [
                {
                    "tool": "agent-reach",
                    "installed": shutil.which("agent-reach") is not None,
                    "needed_for": "source routing across public/read-only external channels",
                    "install_hint": "Install Agent-Reach in the active agent environment and rerun `agent-reach doctor --json`.",
                },
                {
                    "tool": "gh",
                    "installed": shutil.which("gh") is not None,
                    "needed_for": "GitHub-backed source routes and public repository search",
                    "install_hint": "Install GitHub CLI and authenticate if GitHub source routes are needed.",
                },
            ],
            "external_write_capability": False,
        },
        {
            "connector_id": "finance_market_snapshot",
            "status": "probed_candidate",
            "install": [
                "Use `loopx value-connectors source-map --connector finance_market_snapshot --format json` for the boundary packet.",
                "Plan finance information pulls as public/reference snapshots, not advice or trading actions.",
                "Stop for credentials, AK/SK, paid feeds, private portfolio data, or trading intent.",
            ],
            "optional_tools": [],
            "external_write_capability": False,
        },
        {
            "connector_id": "botmail_identity",
            "status": "host_connector_required",
            "install": [
                "Install or enable a host email/Botmail connector.",
                "Use LoopX only to plan the exact sender, recipient, subject, body, metric, and stop condition before sending.",
            ],
            "optional_tools": [],
            "external_write_capability": True,
            "write_gate": "exact sender/recipient/subject/body approval required before send",
        },
        {
            "connector_id": "community_channel",
            "status": "host_or_browser_connector_required",
            "install": [
                "Enable a browser or community connector owned by the user.",
                "Run `loopx value-connectors plan` before signup, posting, or replies.",
            ],
            "optional_tools": [],
            "external_write_capability": True,
            "write_gate": "channel rules, account identity, exact message, and value metric required",
        },
        build_social_browser_x_provider_packet()["install_check"],
    ]
    selected = [
        item
        for item in checks
        if connector == "all" or item["connector_id"] == connector
    ]
    if not selected:
        raise ValueError("unknown connector install check")
    return {
        "ok": True,
        "schema_version": VALUE_CONNECTOR_INSTALL_CHECK_PACKET_SCHEMA_VERSION,
        "mode": "value-connector-install-check",
        "connector": connector,
        "checks": selected,
        "truth_contract": {
            "installation_check_only": True,
            "external_reads_performed": False,
            "external_writes_performed": False,
            "restricted_material_recorded": False,
        },
    }


def render_value_connector_install_check_markdown(payload: dict[str, Any]) -> str:
    lines = ["# LoopX Value Connector Install Check", ""]
    for item in payload.get("checks") or []:
        if not isinstance(item, Mapping):
            continue
        lines.extend(
            [
                f"## {item.get('connector_id')}",
                "",
                f"- status: `{item.get('status')}`",
                f"- external_write_capability: `{item.get('external_write_capability')}`",
            ]
        )
        if item.get("write_gate"):
            lines.append(f"- write_gate: {item.get('write_gate')}")
        lines.extend(["", "Install / use:"])
        for command in item.get("install") or []:
            lines.append(f"- `{command}`")
        for tool in item.get("optional_tools") or []:
            if not isinstance(tool, Mapping):
                continue
            lines.append(
                f"- optional `{tool.get('tool')}` installed=`{tool.get('installed')}`: {tool.get('needed_for')}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
