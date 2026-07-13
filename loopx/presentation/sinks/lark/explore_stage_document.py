"""Maintain one Lark document section and whiteboard per Evidence Stage."""

from __future__ import annotations

import html
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

from .kanban import CommandRunner, _command_error, _run_command


class StageDocumentConfig(Protocol):
    cli_bin: str
    identity: str


LocalConfigReader = Callable[[Path], dict[str, Any]]
LocalConfigWriter = Callable[[Path, Mapping[str, Any]], None]


def _stage_section_xml(stage: Mapping[str, Any]) -> str:
    stage_index = int(stage.get("stage_index") or 0)
    lane_labels = {
        "fix_pr": "PR issue-fix",
        "capability": "LoopX capability",
        "default": "Explore work",
    }
    lanes = (
        ", ".join(
            lane_labels.get(str(item), str(item).replace("_", " ").title())
            for item in stage.get("lanes") or []
        )
        or "Explore work"
    )
    return (
        f"<h2>Evidence Stage {stage_index:02d}</h2>"
        "<p>"
        f"本阶段包含 {int(stage.get('primary_node_count') or 0)} 个主节点、"
        f"{int(stage.get('context_node_count') or 0)} 个关系上下文节点；"
        f"主线：{html.escape(lanes)}；"
        f"跨主线真实关系：{int(stage.get('cross_lane_edge_count') or 0)} 条。"
        "完整 Nodes / Edges / Findings 仍以同一 Base 为准。"
        "</p><whiteboard type=\"blank\"></whiteboard>"
    )


def _created_whiteboard_block(command: Mapping[str, Any]) -> dict[str, Any] | None:
    payload = command.get("json")
    data = payload.get("data") if isinstance(payload, Mapping) else None
    document = data.get("document") if isinstance(data, Mapping) else None
    blocks = document.get("new_blocks") if isinstance(document, Mapping) else None
    return next(
        (
            dict(block)
            for block in blocks or []
            if isinstance(block, Mapping)
            and str(block.get("block_type") or "") == "whiteboard"
            and str(block.get("block_token") or "").strip()
        ),
        None,
    )


def ensure_stage_whiteboards(
    config: StageDocumentConfig,
    *,
    role: str,
    role_sink: Mapping[str, Any],
    stage_views: list[Mapping[str, Any]],
    config_path: Path,
    execute: bool,
    runner: CommandRunner,
    read_local_config: LocalConfigReader,
    write_local_config: LocalConfigWriter,
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]], str | None]:
    """Resolve or create the stage boards and checkpoint each created token."""

    configured = {
        int(item.get("stage_index") or 0): dict(item)
        for item in role_sink.get("stage_whiteboards") or []
        if isinstance(item, Mapping)
        and int(item.get("stage_index") or 0) > 0
        and str(item.get("whiteboard_token") or "").strip()
    }
    if not configured and str(role_sink.get("whiteboard_token") or "").strip():
        configured[1] = {
            "stage_index": 1,
            "whiteboard_token": str(role_sink.get("whiteboard_token") or "").strip(),
        }
    missing = [
        stage
        for stage in stage_views
        if int(stage.get("stage_index") or 0) not in configured
    ]
    if not missing:
        return configured, [], None
    docx_token = str(role_sink.get("docx_token") or "").strip()
    if not docx_token:
        return configured, [], (
            "docx_token is required to create missing Evidence Stage sections"
        )

    def persist_configured_stages() -> None:
        local = read_local_config(config_path)
        updated = {
            key: value
            for key, value in local.items()
            if key not in {"ok", "exists", "path", "updated_at"}
        }
        sinks = dict(updated.get("visual_sinks") or {})
        persisted_sink = dict(sinks.get(role) or role_sink)
        persisted_sink["stage_whiteboards"] = [
            configured[index] for index in sorted(configured)
        ]
        sinks[role] = persisted_sink
        updated["visual_sinks"] = sinks
        write_local_config(config_path, updated)

    commands = []
    for stage in missing:
        stage_index = int(stage.get("stage_index") or 0)
        command = _run_command(
            [
                config.cli_bin,
                "docs",
                "+update",
                "--as",
                config.identity,
                "--doc",
                docx_token,
                "--command",
                "append",
                "--content",
                _stage_section_xml(stage),
                "--format",
                "json",
            ],
            execute=execute,
            runner=runner,
            cwd=config_path.parent,
        )
        commands.append(command)
        if not command.get("ok"):
            return configured, commands, _command_error(command)
        if execute:
            block = _created_whiteboard_block(command)
            if not block:
                return configured, commands, (
                    f"Evidence Stage {stage_index:02d} section was created "
                    "without a whiteboard token"
                )
            configured[stage_index] = {
                "stage_index": stage_index,
                "section_title": f"Evidence Stage {stage_index:02d}",
                "whiteboard_block_id": (
                    str(block.get("block_id") or "").strip() or None
                ),
                "whiteboard_token": str(block.get("block_token") or "").strip(),
            }
            persist_configured_stages()
        else:
            configured[stage_index] = {
                "stage_index": stage_index,
                "section_title": f"Evidence Stage {stage_index:02d}",
                "whiteboard_token": f"planned-stage-{stage_index:02d}",
            }
    return configured, commands, None
