"""Small parsing helpers for Explore visual marker readback."""

from __future__ import annotations

import json
import time
from typing import Any, Mapping, Sequence

from .kanban import CommandRunner, _command_error, _run_command


VISUAL_READBACK_RETRY_DELAYS_SECONDS = (0.25, 0.5, 1.0, 2.0, 4.0)


def whiteboard_raw_texts(payload: Any) -> list[str]:
    if not isinstance(payload, Mapping):
        return []
    data = payload.get("data")
    nodes = data.get("nodes") if isinstance(data, Mapping) else None
    texts: list[str] = []
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, Mapping):
            continue
        text_node = node.get("text")
        if isinstance(text_node, Mapping) and str(text_node.get("text") or "").strip():
            texts.append(str(text_node.get("text")))
    return texts


def structured_command_error(result: Mapping[str, Any]) -> Mapping[str, Any]:
    parsed = result.get("json")
    if not isinstance(parsed, Mapping):
        try:
            parsed = json.loads(str(result.get("stderr") or ""))
        except (TypeError, json.JSONDecodeError):
            parsed = None
    error = parsed.get("error") if isinstance(parsed, Mapping) else None
    return error if isinstance(error, Mapping) else {}


def is_retryable_marker_readback_error(
    *, error_code: Any, error_message: str
) -> bool:
    if error_code == 4003101 and "doc is applying" in error_message:
        return True
    # Lark can briefly return ``invalid arg`` from the raw-node query
    # immediately after accepting a whiteboard overwrite. This helper is
    # called only by that post-publish marker path, so it does not generalize
    # every API 2890002 response into a transient error.
    return error_code == 2890002 and "invalid arg" in error_message


def readback_visual_delivery_marker(
    *,
    cli_bin: str,
    identity: str,
    whiteboard_token: str,
    marker: str,
    runner: CommandRunner,
    retry_delays: Sequence[float] | None = None,
) -> dict[str, Any]:
    command = [
        cli_bin,
        "whiteboard",
        "+query",
        "--as",
        identity,
        "--whiteboard-token",
        whiteboard_token,
        "--output_as",
        "raw",
        "--format",
        "json",
    ]
    attempts: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    texts: list[str] = []
    marker_observed = False
    effective_retry_delays = tuple(
        VISUAL_READBACK_RETRY_DELAYS_SECONDS
        if retry_delays is None
        else retry_delays
    )
    for attempt_index in range(len(effective_retry_delays) + 1):
        result = _run_command(command, execute=True, runner=runner)
        texts = whiteboard_raw_texts(result.get("json"))
        marker_observed = marker in texts
        error = structured_command_error(result)
        error_code = error.get("code")
        is_retryable = is_retryable_marker_readback_error(
            error_code=error_code,
            error_message=str(error.get("message") or ""),
        ) or bool(result.get("ok") and not marker_observed)
        attempts.append(
            {
                "attempt": attempt_index + 1,
                "ok": bool(result.get("ok")),
                "marker_observed": marker_observed,
                "error_code": error_code,
                "retryable": is_retryable,
            }
        )
        if marker_observed or not is_retryable:
            break
        if attempt_index < len(effective_retry_delays):
            time.sleep(effective_retry_delays[attempt_index])
    command_receipt = {
        key: result.get(key)
        for key in (
            "command",
            "executed",
            "ok",
            "returncode",
            "timed_out",
            "stderr",
        )
        if result.get(key) not in (None, "")
    }
    return {
        "ok": bool(result.get("ok") and marker_observed),
        "schema_version": "loopx_lark_explore_visual_readback_v0",
        "performed": True,
        "verified": marker_observed,
        "source": "whiteboard_raw_nodes",
        "expected_marker": marker,
        "observed_marker": marker if marker_observed else None,
        "remote_text_node_count": len(texts),
        "attempt_count": len(attempts),
        "attempts": attempts,
        "retryable": bool(
            not marker_observed and attempts and attempts[-1].get("retryable")
        ),
        "command": command_receipt,
        "error": (
            None
            if result.get("ok") and marker_observed
            else _command_error(result)
            if not result.get("ok")
            else "remote whiteboard raw nodes do not contain the expected delivery marker"
        ),
    }


def _merge_readback_attempts(
    previous: Mapping[str, Any], current: Mapping[str, Any]
) -> dict[str, Any]:
    attempts = [
        dict(item)
        for item in previous.get("attempts") or []
        if isinstance(item, Mapping)
    ]
    for item in current.get("attempts") or []:
        if isinstance(item, Mapping):
            attempts.append(dict(item, attempt=len(attempts) + 1))
    merged = dict(current)
    merged["attempts"] = attempts
    merged["attempt_count"] = len(attempts)
    return merged


def _apply_stage_readback(
    stage_result: dict[str, Any], readback: Mapping[str, Any]
) -> None:
    command = stage_result.get("command")
    command_ok = bool(isinstance(command, Mapping) and command.get("ok"))
    delivery_ok = bool(command_ok and readback.get("ok"))
    retryable = bool(command_ok and readback.get("retryable"))
    stage_result.update(
        {
            "ok": delivery_ok,
            "status": "published" if delivery_ok else "publish_unverified",
            "published": delivery_ok,
            "readback": dict(readback),
            "retryable": retryable,
            "required_action": (
                "retry Explore visual sync; post-publish marker readback did not settle"
                if retryable
                else None
            ),
            "error": None
            if delivery_ok
            else str(readback.get("error") or "visual marker readback failed"),
        }
    )


def settle_visual_stage_readbacks(
    *,
    cli_bin: str,
    identity: str,
    stage_targets: Sequence[tuple[dict[str, Any], str]],
    runner: CommandRunner,
    retry_delays: Sequence[float] | None = None,
) -> None:
    """Verify every published stage within one shared settling window."""

    effective_retry_delays = tuple(
        VISUAL_READBACK_RETRY_DELAYS_SECONDS
        if retry_delays is None
        else retry_delays
    )
    pending = list(stage_targets)
    for attempt_index in range(len(effective_retry_delays) + 1):
        next_pending: list[tuple[dict[str, Any], str]] = []
        for stage_result, whiteboard_token in pending:
            previous = stage_result.get("readback")
            previous = previous if isinstance(previous, Mapping) else {}
            readback = readback_visual_delivery_marker(
                cli_bin=cli_bin,
                identity=identity,
                whiteboard_token=whiteboard_token,
                marker=str(previous.get("expected_marker") or ""),
                runner=runner,
                retry_delays=(),
            )
            merged = _merge_readback_attempts(previous, readback)
            _apply_stage_readback(stage_result, merged)
            if merged.get("retryable"):
                next_pending.append((stage_result, whiteboard_token))
        pending = next_pending
        if not pending:
            break
        if attempt_index < len(effective_retry_delays):
            time.sleep(effective_retry_delays[attempt_index])
