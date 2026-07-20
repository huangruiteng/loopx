from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...extensions.runtime import (
    default_extension_state_file,
    resolve_capability_binding,
)


FINANCE_VALUE_DISCOVERY_CAPABILITY_ID = "finance-value-discovery"
FINANCE_VALUE_DISCOVERY_PROVIDER_PROTOCOL = "finance_value_discovery_provider_v0"
FINANCE_VALUE_DISCOVERY_PERMISSION = "finance.discovery.reduce"
FINANCE_VALUE_DISCOVERY_PACKET_SCHEMA_VERSION = "finance_value_discovery_packet_v0"
FINANCE_VALUE_DISCOVERY_ERROR_SCHEMA_VERSION = "finance_value_discovery_error_v0"
MAX_PROVIDER_OUTPUT_BYTES = 1_000_000


def invoke_finance_value_discovery_extension(
    payload: Mapping[str, Any],
    *,
    runtime_root: str | Path | None = None,
) -> dict[str, Any]:
    """Dispatch the compatibility command through the verified extension binding."""

    binding = resolve_capability_binding(
        state_file=default_extension_state_file(runtime_root),
        capability_id=FINANCE_VALUE_DISCOVERY_CAPABILITY_ID,
        protocol=FINANCE_VALUE_DISCOVERY_PROVIDER_PROTOCOL,
        permission=FINANCE_VALUE_DISCOVERY_PERMISSION,
    )
    try:
        completed = subprocess.run(
            [str(value) for value in binding["argv"]],
            input=json.dumps(dict(payload), ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=int(binding["timeout_seconds"]),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("finance value-discovery provider execution failed") from exc
    if len(completed.stdout.encode("utf-8")) > MAX_PROVIDER_OUTPUT_BYTES:
        raise ValueError("finance value-discovery provider response is too large")
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "finance value-discovery provider returned invalid JSON"
        ) from exc
    if not isinstance(response, Mapping):
        raise ValueError(
            "finance value-discovery provider returned a non-object response"
        )
    schema = response.get("schema_version")
    if schema not in {
        FINANCE_VALUE_DISCOVERY_PACKET_SCHEMA_VERSION,
        FINANCE_VALUE_DISCOVERY_ERROR_SCHEMA_VERSION,
    }:
        raise ValueError("finance value-discovery provider returned an invalid schema")
    if completed.returncode == 0 and (
        response.get("ok") is not True
        or schema != FINANCE_VALUE_DISCOVERY_PACKET_SCHEMA_VERSION
    ):
        raise ValueError(
            "finance value-discovery provider returned an invalid success packet"
        )
    if (
        completed.returncode != 0
        and schema != FINANCE_VALUE_DISCOVERY_ERROR_SCHEMA_VERSION
    ):
        raise ValueError(
            "finance value-discovery provider failed without an error packet"
        )
    return dict(response)


def render_finance_value_discovery_compatibility_markdown(
    payload: Mapping[str, Any],
) -> str:
    projection = payload.get("projection")
    projection = projection if isinstance(projection, Mapping) else {}
    lines = [
        "# LoopX Finance Value Discovery",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- next_action: `{projection.get('next_action')}`",
        f"- continuous_watch_allowed: `{projection.get('continuous_watch_allowed')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines).rstrip() + "\n"
