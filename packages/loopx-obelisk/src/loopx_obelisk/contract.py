from __future__ import annotations

import json
import math
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


REQUEST_SCHEMA = "decision_context_advisory_retrieve_request_v0"
RESPONSE_SCHEMA = "decision_context_advisory_retrieve_response_v0"
MAX_RESULTS = 8
MAX_QUERY_CHARS = 1_000
MAX_CONTENT_CHARS = 16_000
MAX_SCOPE_CHARS = 2_048
_REQUEST_FIELDS = {
    "schema_version",
    "operation",
    "namespace",
    "scope_ref",
    "query",
    "query_summary",
    "max_results",
    "timeout_seconds",
    "observed_at",
}
_CODEX_SESSION_SCOPE_RE = re.compile(r"^host-session:codex:([^\s:/?#]+)$")

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _text(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field} must be a bounded non-empty string")
    return value.strip()


def validate_request(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("provider request must be an object")
    unexpected = sorted(set(value) - _REQUEST_FIELDS)
    if unexpected:
        raise ValueError(
            "provider request contains unsupported fields: " + ", ".join(unexpected)
        )
    if value.get("schema_version") != REQUEST_SCHEMA:
        raise ValueError(f"provider request must use {REQUEST_SCHEMA}")
    if value.get("operation") != "retrieve":
        raise ValueError("provider operation must be retrieve")
    raw_limit = value.get("max_results")
    raw_timeout = value.get("timeout_seconds")
    if isinstance(raw_limit, bool) or not isinstance(raw_limit, int):
        raise ValueError("max_results must be an integer")
    if isinstance(raw_timeout, bool) or not isinstance(raw_timeout, (int, float)):
        raise ValueError("timeout_seconds must be numeric")
    limit = raw_limit
    timeout_seconds = float(raw_timeout)
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"max_results must be between 1 and {MAX_RESULTS}")
    if not math.isfinite(timeout_seconds) or not 1 <= timeout_seconds <= 120:
        raise ValueError("timeout_seconds must be between 1 and 120")
    return {
        "schema_version": REQUEST_SCHEMA,
        "operation": "retrieve",
        "namespace": _text(value.get("namespace"), field="namespace", maximum=120),
        "scope_ref": _text(
            value.get("scope_ref"), field="scope_ref", maximum=MAX_SCOPE_CHARS
        ),
        "query": _text(value.get("query"), field="query", maximum=MAX_QUERY_CHARS),
        "query_summary": _text(
            value.get("query_summary"), field="query_summary", maximum=220
        ),
        "max_results": limit,
        "timeout_seconds": timeout_seconds,
        "observed_at": _text(
            value.get("observed_at"), field="observed_at", maximum=80
        ),
    }


def _query_script(request: Mapping[str, Any]) -> str:
    scope_ref = str(request["scope_ref"])
    locator = _CODEX_SESSION_SCOPE_RE.fullmatch(scope_ref)
    options: dict[str, Any] = {
        "limit": min(int(request["max_results"]) * 4, 32),
        "source": "codex",
        "includeMeta": False,
        "includeInactive": False,
    }
    expected_source: str | None = None
    if locator is not None:
        # Obelisk namespaces Codex ids in its public query API. LoopX keeps
        # that provider detail outside the Core deep-link parser.
        options["sessionId"] = f"codex:{locator.group(1)}"
        expected_source = "codex"
    else:
        raise ValueError(
            "scope_ref must use host-session:codex:<thread-id>"
        )
    return "\n".join(
        [
            f"const hits = search({json.dumps(request['query'])}, {json.dumps(options)});",
            f"const expectedSource = {json.dumps(expected_source)};",
            f"const limit = {int(request['max_results'])};",
            "return hits.filter((hit) =>",
            "  !hit?.session?.is_invoking &&",
            "  (!expectedSource || hit?.session?.source === expectedSource)",
            ").slice(0, limit).map((hit) => ({",
            "  message: {",
            "    uuid: hit?.message?.uuid,",
            (
                "    text: typeof hit?.message?.text === 'string' "
                f"? hit.message.text.slice(0, {MAX_CONTENT_CHARS}) : '',"
            ),
            "    content_type: hit?.message?.content_type,",
            "    role: hit?.message?.role,",
            "  },",
            "  session: {",
            "    id: hit?.session?.id,",
            "    source: hit?.session?.source,",
            "    is_invoking: hit?.session?.is_invoking,",
            "  },",
            "  rank: hit?.rank,",
            "}));",
            "",
        ]
    )


def _run_obelisk_query(
    request: Mapping[str, Any],
    *,
    obelisk_bin: str,
    runner: CommandRunner,
) -> list[Mapping[str, Any]]:
    query_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".mjs",
            prefix="loopx-obelisk-",
            delete=False,
        ) as handle:
            handle.write(_query_script(request))
            query_path = Path(handle.name)
        completed = runner(
            [obelisk_bin, "--query", str(query_path)],
            capture_output=True,
            check=False,
            text=True,
            timeout=float(request["timeout_seconds"]),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Obelisk query execution failed") from exc
    finally:
        if query_path is not None:
            query_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        raise RuntimeError("Obelisk query returned a non-zero exit")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Obelisk query returned invalid JSON") from exc
    if not isinstance(payload, list) or not all(
        isinstance(item, Mapping) for item in payload
    ):
        raise RuntimeError("Obelisk query result must be a list of objects")
    return payload


def _resource_ref(hit: Mapping[str, Any]) -> str | None:
    message = hit.get("message")
    session = hit.get("session")
    if not isinstance(message, Mapping) or not isinstance(session, Mapping):
        return None
    session_id = str(session.get("id") or "").strip()
    message_id = str(message.get("uuid") or "").strip()
    source = str(session.get("source") or message.get("source") or "unknown").strip()
    if not session_id or not message_id or any(
        len(value) > 180 or any(character.isspace() for character in value)
        for value in (source, session_id, message_id)
    ):
        return None
    return f"obelisk:{session_id}:{message_id}"


def _summary(hit: Mapping[str, Any]) -> str:
    message = hit.get("message")
    role = (
        str(message.get("role") or "message")
        if isinstance(message, Mapping)
        else "message"
    )
    if role not in {"user", "assistant", "system", "developer"}:
        role = "message"
    return f"Historical Codex task {role}"


def _score(hit: Mapping[str, Any]) -> float | None:
    value = hit.get("rank")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    score = float(value)
    return score if math.isfinite(score) else None


def retrieve(
    value: object,
    *,
    obelisk_bin: str = "obelisk",
    timeout_cap_seconds: float = 10,
    runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    request = validate_request(value)
    if timeout_cap_seconds <= 0:
        raise ValueError("timeout_cap_seconds must be positive")
    request["timeout_seconds"] = min(
        float(request["timeout_seconds"]),
        float(timeout_cap_seconds),
    )
    hits = _run_obelisk_query(request, obelisk_bin=obelisk_bin, runner=runner)
    locator = _CODEX_SESSION_SCOPE_RE.fullmatch(str(request["scope_ref"]))
    if locator is None:
        raise ValueError("scope_ref must use host-session:codex:<thread-id>")
    expected_session_id = f"codex:{locator.group(1)}"
    items: list[dict[str, Any]] = []
    for hit in hits:
        message = hit.get("message")
        session = hit.get("session")
        if (
            not isinstance(message, Mapping)
            or not isinstance(session, Mapping)
            or session.get("id") != expected_session_id
            or session.get("source") != "codex"
            or session.get("is_invoking") is True
            or message.get("content_type") != "text"
            or message.get("role") not in {"user", "assistant"}
        ):
            continue
        resource_ref = _resource_ref(hit)
        content = str(message.get("text") or "").strip()
        if not resource_ref or not content:
            continue
        items.append(
            {
                "resource_ref": resource_ref,
                "summary": _summary(hit),
                "content": content[:MAX_CONTENT_CHARS],
                "score": _score(hit),
            }
        )
        if len(items) >= int(request["max_results"]):
            break
    return {
        "ok": True,
        "schema_version": RESPONSE_SCHEMA,
        "status": "completed",
        "reason_code": None,
        "items": items,
    }


def doctor(
    *,
    obelisk_bin: str = "obelisk",
    runner: CommandRunner = subprocess.run,
    timeout_seconds: float = 10,
) -> None:
    try:
        completed = runner(
            [obelisk_bin, "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Obelisk CLI is unavailable") from exc
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError("Obelisk CLI version probe failed")
