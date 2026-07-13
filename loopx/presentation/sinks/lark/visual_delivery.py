"""Idempotent Lark whiteboard publish and delivery readback helpers."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping, Protocol

from .kanban import CommandRunner, _command_error, _run_command

_VISUAL_READBACK_RETRY_DELAYS_SECONDS = (0.25, 0.5, 1.0, 2.0, 4.0)
_VISUAL_PUBLISH_RETRY_DELAYS_SECONDS = (0.5, 1.0, 2.0, 4.0)


class _VisualDeliveryConfig(Protocol):
    cli_bin: str
    identity: str


def _delivery_marker_id(marker: str) -> str:
    return f"loopx_delivery_{hashlib.sha256(marker.encode('utf-8')).hexdigest()[:20]}"


def _mermaid_with_delivery_marker(source: str, marker: str) -> str:
    return "\n".join([source.rstrip(), f"    %% {marker}"])


def _stamp_whiteboard_openapi_delivery_marker(path: Path, marker: str) -> str:
    """Stamp converted raw board data with an ID that survives Lark readback."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid converted whiteboard OpenAPI payload: {exc}") from exc
    nodes = payload.get("nodes") if isinstance(payload, Mapping) else None
    if not isinstance(nodes, list) or not nodes or not isinstance(nodes[0], dict):
        raise ValueError("converted whiteboard OpenAPI payload has no root node")
    marker_id = _delivery_marker_id(marker)
    nodes[0]["id"] = marker_id
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return marker_id


def _whiteboard_raw_ids(payload: Any) -> list[str]:
    if not isinstance(payload, Mapping):
        return []
    data = payload.get("data")
    nodes = data.get("nodes") if isinstance(data, Mapping) else None
    if not isinstance(nodes, list):
        return []
    return [
        str(node.get("id"))
        for node in nodes
        if isinstance(node, Mapping) and str(node.get("id") or "").strip()
    ]


def _whiteboard_code(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return ""
    data = payload.get("data")
    return str(data.get("code") or "") if isinstance(data, Mapping) else ""


def _structured_command_error(result: Mapping[str, Any]) -> Mapping[str, Any]:
    parsed = result.get("json")
    if not isinstance(parsed, Mapping):
        try:
            parsed = json.loads(str(result.get("stderr") or ""))
        except (TypeError, json.JSONDecodeError):
            parsed = None
    error = parsed.get("error") if isinstance(parsed, Mapping) else None
    return error if isinstance(error, Mapping) else {}


def _readback_visual_delivery_marker(
    config: _VisualDeliveryConfig,
    *,
    whiteboard_token: str,
    marker: str,
    renderer: str,
    runner: CommandRunner,
) -> dict[str, Any]:
    output_as = "code" if renderer == "mermaid" else "raw"
    command = [
        config.cli_bin,
        "whiteboard",
        "+query",
        "--as",
        config.identity,
        "--whiteboard-token",
        whiteboard_token,
        "--output_as",
        output_as,
        "--format",
        "json",
    ]
    attempts: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    marker_observed = False
    expected_remote_value = (
        marker if renderer == "mermaid" else _delivery_marker_id(marker)
    )
    for attempt_index in range(len(_VISUAL_READBACK_RETRY_DELAYS_SECONDS) + 1):
        result = _run_command(command, execute=True, runner=runner)
        payload = result.get("json")
        if renderer == "mermaid":
            marker_observed = marker in _whiteboard_code(payload)
        else:
            marker_observed = expected_remote_value in _whiteboard_raw_ids(payload)
        error = _structured_command_error(result)
        error_code = error.get("code")
        is_applying = error_code == 4003101 and "doc is applying" in str(
            error.get("message") or ""
        )
        attempts.append(
            {
                "attempt": attempt_index + 1,
                "ok": bool(result.get("ok")),
                "marker_observed": marker_observed,
                "error_code": error_code,
                "retryable": is_applying,
            }
        )
        if result.get("ok") or not is_applying:
            break
        if attempt_index < len(_VISUAL_READBACK_RETRY_DELAYS_SECONDS):
            time.sleep(_VISUAL_READBACK_RETRY_DELAYS_SECONDS[attempt_index])
    command_receipt = {
        key: result.get(key)
        for key in ("command", "executed", "ok", "returncode", "timed_out", "stderr")
        if result.get(key) not in (None, "")
    }
    return {
        "ok": bool(result.get("ok") and marker_observed),
        "schema_version": "loopx_lark_explore_visual_readback_v0",
        "performed": True,
        "verified": marker_observed,
        "source": f"whiteboard_{output_as}",
        "expected_marker": marker,
        "expected_remote_value": expected_remote_value,
        "observed_marker": marker if marker_observed else None,
        "attempt_count": len(attempts),
        "attempts": attempts,
        "command": command_receipt,
        "error": (
            None
            if result.get("ok") and marker_observed
            else _command_error(result)
            if not result.get("ok")
            else f"remote whiteboard {output_as} does not contain the expected delivery marker"
        ),
    }


def _is_retryable_visual_publish_error(result: Mapping[str, Any]) -> bool:
    if result.get("ok"):
        return False
    error = _structured_command_error(result)
    return error.get("code") == 4003101 and "doc is applying" in str(
        error.get("message") or ""
    )


def _publish_visual_with_retry(
    command: list[str],
    *,
    runner: CommandRunner,
    cwd: Path,
) -> dict[str, Any]:
    """Publish idempotently across Lark's whiteboard applying window."""

    attempts: list[dict[str, Any]] = []
    applied_delays: list[float] = []
    for attempt_index in range(len(_VISUAL_PUBLISH_RETRY_DELAYS_SECONDS) + 1):
        result = _run_command(
            command,
            execute=True,
            runner=runner,
            cwd=cwd,
        )
        attempts.append(result)
        if result.get("ok") or not _is_retryable_visual_publish_error(result):
            break
        if attempt_index < len(_VISUAL_PUBLISH_RETRY_DELAYS_SECONDS):
            delay = _VISUAL_PUBLISH_RETRY_DELAYS_SECONDS[attempt_index]
            applied_delays.append(delay)
            time.sleep(delay)
    final = dict(attempts[-1])
    final["attempt_count"] = len(attempts)
    final["retry_delays_seconds"] = applied_delays
    if len(attempts) > 1:
        final["first_attempt_error"] = _command_error(attempts[0])
    return final
