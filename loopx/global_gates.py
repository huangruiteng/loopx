from __future__ import annotations

from pathlib import Path
from typing import Any

from .summary_all import (
    BOUNDARY,
    SCHEMA_VERSION,
    SOURCE_SURFACES,
    _as_dict,
    _as_list,
    _now_iso,
    _redact_text,
    build_summary_all,
)

COMMAND = "/loopx-global-gates"
LEGACY_COMMAND_ALIASES = {
    "/loop-global-gates": COMMAND,
}


def build_global_gates(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    scan_roots: list[Path],
    agent_id: str | None,
    limit: int,
) -> dict[str, Any]:
    """Build the read-only global manager view for currently open gates."""
    summary = build_summary_all(
        registry_path=registry_path,
        runtime_root_override=runtime_root_override,
        scan_roots=scan_roots,
        agent_id=agent_id,
        time_range="24h",
        limit=limit,
    )
    if not summary.get("ok"):
        return {
            "ok": False,
            "schema_version": SCHEMA_VERSION,
            "request": {
                "schema_version": "global_manager_command_request_v0",
                "command": COMMAND,
                "legacy_aliases": list(LEGACY_COMMAND_ALIASES),
                "cli_command": "loopx global-gates",
                "privacy_mode": "public_safe_summary",
                "dry_run": True,
            },
            "error": _redact_text(summary.get("error")),
        }

    gates = [
        gate
        for gate in _as_list(summary.get("gates"))
        if isinstance(gate, dict)
    ][:limit]
    summary_payload = _as_dict(summary.get("summary"))
    payload: dict[str, Any] = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "request": {
            "schema_version": "global_manager_command_request_v0",
            "command": COMMAND,
            "legacy_aliases": list(LEGACY_COMMAND_ALIASES),
            "cli_command": "loopx global-gates",
            "include": ["gates", "next_actions"],
            "privacy_mode": "public_safe_summary",
            "dry_run": True,
        },
        "generated_at": _now_iso(),
        "summary": {
            "headline": f"{len(gates)} open user/controller gates.",
            "open_gate_count": len(gates),
            "source_surfaces": SOURCE_SURFACES,
            "quota_states": summary_payload.get("quota_states", {}),
        },
        "groups": {"user_gates": gates},
        "gates": gates,
        "actions": [
            {
                "action_id": "act_read_gate_detail",
                "kind": "read_more",
                "requires_user_approval": False,
                "requires_maintainer_authority": False,
                "preview": "Run `loopx review-packet --goal-id <goal>` for one gate's compact context.",
            }
        ],
        "omissions": [
            "Raw logs, raw transcripts, connector payloads, credential values, local paths, and private source bodies were intentionally omitted."
        ],
        "boundary": BOUNDARY,
    }
    return payload


def render_global_gates_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return "# LoopX Global Gates\n\n- ok: `False`\n- error: " + _redact_text(
            payload.get("error")
        )

    summary = _as_dict(payload.get("summary"))
    lines = [
        "# LoopX Global Gates",
        "",
        f"- command: `{_as_dict(payload.get('request')).get('command')}`",
        f"- open gates: `{summary.get('open_gate_count')}`",
        "",
        "## Gates",
    ]
    gates = [item for item in _as_list(payload.get("gates")) if isinstance(item, dict)]
    if not gates:
        lines.append("- none")
    for gate in gates:
        lines.append(
            "- "
            f"`{gate.get('goal_id')}` owner=`{gate.get('owner')}` "
            f"blocks=`{','.join(str(item) for item in gate.get('blocks') or [])}`: "
            f"{gate.get('question')}"
        )
    lines.extend(["", "## Boundary", "- raw/private material omitted; local paths are not recorded."])
    return "\n".join(lines)
