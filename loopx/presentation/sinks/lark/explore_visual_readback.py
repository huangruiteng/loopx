"""Small parsing helpers for Explore visual marker readback."""

from __future__ import annotations

import json
from typing import Any, Mapping


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
