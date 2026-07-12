from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence


CONFIG_SCHEMA = "semantic_preference_hook_config_v0"
REQUEST_SCHEMA = "semantic_preference_provider_request_v0"
RESPONSE_SCHEMA = "semantic_preference_provider_response_v0"
RECALL_SCHEMA = "semantic_preference_recall_v0"
RECEIPT_SCHEMA = "semantic_preference_application_receipt_v0"
SURFACE_RE = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,199}$")
MAX_PROVIDER_OUTPUT_BYTES = 256_000
MAX_ITEM_BYTES = 8_000
MAX_RECEIPT_REFS = 20


def _surface(value: object) -> str:
    result = str(value or "").strip()
    if not SURFACE_RE.fullmatch(result):
        raise ValueError(
            "surface must be a module-qualified token such as pr_review.reply"
        )
    return result


def _config(config: str | Path, project: str | Path) -> dict[str, Any]:
    root = Path(project).expanduser().resolve()
    path = Path(config).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("project directory does not exist")
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = None
    if relative is not None:
        tracked = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--error-unmatch",
                "--",
                str(relative),
            ],
            capture_output=True,
            check=False,
        )
        ignored = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--quiet", "--", str(relative)],
            capture_output=True,
            check=False,
        )
        if tracked.returncode == 0 or ignored.returncode != 0:
            raise ValueError("config inside the project must be ignored and untracked")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("config must be a readable JSON object") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != CONFIG_SCHEMA:
        raise ValueError(f"config schema_version must be {CONFIG_SCHEMA}")
    if not isinstance(payload.get("enabled", False), bool):
        raise ValueError("config enabled must be a boolean")
    return payload


def _context(values: Sequence[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values or []:
        key, separator, item = value.partition("=")
        if not separator or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", key):
            raise ValueError("context must use lower-snake key=value syntax")
        if len(item) > 500:
            raise ValueError(f"context value for {key} exceeds 500 characters")
        result[key] = item
    return result


def _unavailable(surface: str, policy: str, kind: str) -> dict[str, Any]:
    if policy == "fail_closed":
        raise ValueError(f"semantic preference provider unavailable: {kind}")
    return {
        "ok": True,
        "schema_version": RECALL_SCHEMA,
        "status": "provider_unavailable",
        "surface": surface,
        "items": [],
        "failure_kind": kind,
    }


def recall(
    config: str | Path,
    *,
    project: str | Path,
    surface: str,
    context: Sequence[str] | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    payload = _config(config, project)
    surface_id = _surface(surface)
    if not payload.get("enabled", False):
        return {
            "ok": True,
            "schema_version": RECALL_SCHEMA,
            "status": "disabled",
            "surface": surface_id,
            "items": [],
        }
    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, Mapping) or not isinstance(
        surfaces.get(surface_id), Mapping
    ):
        raise ValueError(f"surface is not configured: {surface_id}")
    surface_config = surfaces[surface_id]
    query = str(surface_config.get("query") or "").strip()
    policy = str(surface_config.get("failure_policy") or "fail_open")
    try:
        limit = int(surface_config.get("limit", 5))
    except (TypeError, ValueError) as exc:
        raise ValueError("surface limit must be an integer") from exc
    if not 1 <= len(query) <= 500 or not 1 <= limit <= 20:
        raise ValueError("surface query or limit is outside the bounded contract")
    if policy not in {"fail_open", "fail_closed"}:
        raise ValueError("failure_policy must be fail_open or fail_closed")
    provider = payload.get("provider")
    argv = provider.get("argv") if isinstance(provider, Mapping) else None
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(v, str) and v for v in argv)
    ):
        raise ValueError("enabled provider requires a non-empty string argv list")
    try:
        timeout = int(provider.get("timeout_seconds", 30))
    except (TypeError, ValueError) as exc:
        raise ValueError("provider timeout_seconds must be an integer") from exc
    if not 1 <= timeout <= 120:
        raise ValueError("provider timeout_seconds must be between 1 and 120")
    request = {
        "schema_version": REQUEST_SCHEMA,
        "surface": surface_id,
        "query": query,
        "limit": limit,
        "context": _context(context),
    }
    if not execute:
        return {
            "ok": True,
            "schema_version": RECALL_SCHEMA,
            "status": "preview_ready",
            "surface": surface_id,
            "request": request,
        }
    try:
        completed = subprocess.run(
            argv,
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _unavailable(surface_id, policy, "execution_failed")
    if completed.returncode != 0:
        return _unavailable(surface_id, policy, "nonzero_exit")
    if len(completed.stdout.encode("utf-8")) > MAX_PROVIDER_OUTPUT_BYTES:
        return _unavailable(surface_id, policy, "response_too_large")
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return _unavailable(surface_id, policy, "invalid_json")
    items = response.get("items") if isinstance(response, Mapping) else None
    if (
        not isinstance(response, Mapping)
        or response.get("schema_version") != RESPONSE_SCHEMA
        or not isinstance(items, list)
        or not all(isinstance(item, Mapping) for item in items)
    ):
        return _unavailable(surface_id, policy, "invalid_response")
    bounded = [dict(item) for item in items[:limit]]
    if any(
        len(json.dumps(item, ensure_ascii=False).encode("utf-8")) > MAX_ITEM_BYTES
        for item in bounded
    ):
        return _unavailable(surface_id, policy, "item_too_large")
    return {
        "ok": True,
        "schema_version": RECALL_SCHEMA,
        "status": "completed",
        "surface": surface_id,
        "items": bounded,
        "truncated": len(items) > len(bounded),
    }


def _token(value: object, label: str) -> str:
    result = str(value or "").strip()
    if not TOKEN_RE.fullmatch(result):
        raise ValueError(f"{label} must be a compact public-safe token")
    return result


def application_receipt(
    *,
    surface: str,
    application_id: str,
    outcome: str,
    preference_refs: Sequence[str] | None = None,
    artifact_ref: str | None = None,
) -> dict[str, Any]:
    if outcome not in {"applied", "ignored", "failed"}:
        raise ValueError("outcome must be applied, ignored, or failed")
    refs = [str(ref) for ref in preference_refs or [] if str(ref).strip()]
    if len(refs) > MAX_RECEIPT_REFS:
        raise ValueError(f"preference_refs supports at most {MAX_RECEIPT_REFS} items")
    return {
        "schema_version": RECEIPT_SCHEMA,
        "surface": _surface(surface),
        "application_id": _token(application_id, "application_id"),
        "outcome": outcome,
        "preference_ref_digests": sorted(
            {hashlib.sha256(str(ref).encode()).hexdigest()[:16] for ref in refs}
        ),
        "artifact_ref": _token(artifact_ref, "artifact_ref") if artifact_ref else None,
    }
