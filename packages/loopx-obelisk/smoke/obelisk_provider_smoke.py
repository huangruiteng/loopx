#!/usr/bin/env python3
"""Offline contract smoke for the loopx-obelisk provider."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "src"))

from loopx_obelisk.contract import doctor, retrieve  # noqa: E402


SESSION_ID = "codex:thread-a"
REQUEST = {
    "schema_version": "decision_context_advisory_retrieve_request_v0",
    "operation": "retrieve",
    "namespace": "peer-session",
    "scope_ref": f"host-session:{SESSION_ID}",
    "query": "current implementation decision",
    "query_summary": "peer task decision",
    "max_results": 2,
    "timeout_seconds": 20,
    "observed_at": "2026-09-05T00:00:00+00:00",
}


def _validate_schema(instance: object, filename: str) -> None:
    schema = json.loads((PACKAGE_ROOT / "schemas" / filename).read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(instance)


def main() -> None:
    _validate_schema(REQUEST, "request.schema.json")
    calls: list[tuple[list[str], float]] = []
    query_paths: list[Path] = []

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, float(kwargs["timeout"])))
        if argv[1:] == ["--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="obelisk 0.1.0\n")
        assert argv[1] == "--query", argv
        query_path = Path(argv[2])
        query_paths.append(query_path)
        script = query_path.read_text(encoding="utf-8")
        assert f'"sessionId": "{SESSION_ID}"' in script, script
        assert '"source": "codex"' in script, script
        assert '"includeMeta": false' in script, script
        assert '"includeInactive": false' in script, script
        assert "!hit?.session?.is_invoking" in script, script
        assert "hit?.session?.source === expectedSource" in script, script
        assert "hit.message.text.slice(0, 16000)" in script, script
        assert "context: hit" not in script, script
        payload = [
            {
                "message": {
                    "uuid": "current-message",
                    "text": "Current task must not be independent evidence.",
                    "content_type": "text",
                    "role": "assistant",
                },
                "session": {
                    "id": SESSION_ID,
                    "source": "codex",
                    "is_invoking": True,
                },
                "rank": -1.0,
            },
            {
                "message": {
                    "uuid": "thinking-message",
                    "text": "Hidden chain-of-thought must not cross the boundary.",
                    "content_type": "thinking",
                    "role": "assistant",
                },
                "session": {"id": SESSION_ID, "source": "codex"},
                "rank": -0.9,
            },
            {
                "message": {
                    "uuid": "other-message",
                    "text": "A different task must not cross the scope boundary.",
                    "content_type": "text",
                    "role": "user",
                },
                "session": {"id": "codex:thread-b", "source": "codex"},
                "rank": -0.8,
            },
            {
                "message": {
                    "uuid": "message-1",
                    "text": "The source task retained the extension boundary.",
                    "content_type": "text",
                    "role": "assistant",
                },
                "session": {"id": SESSION_ID, "source": "codex"},
                "rank": -0.75,
            }
        ]
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(payload))

    doctor(obelisk_bin="obelisk", runner=runner, timeout_seconds=3)
    response = retrieve(
        REQUEST,
        obelisk_bin="obelisk",
        timeout_cap_seconds=5,
        runner=runner,
    )

    assert calls[0] == (["obelisk", "--version"], 3)
    assert calls[1][0][0:2] == ["obelisk", "--query"]
    assert calls[1][1] == 5
    assert all("--build" not in call[0] and "--attune" not in call[0] for call in calls)
    assert all(not path.exists() for path in query_paths)
    assert response == {
        "ok": True,
        "schema_version": "decision_context_advisory_retrieve_response_v0",
        "status": "completed",
        "reason_code": None,
        "items": [
            {
                "resource_ref": f"obelisk:{SESSION_ID}:message-1",
                "summary": "Historical Codex task assistant",
                "content": "The source task retained the extension boundary.",
                "score": -0.75,
            }
        ],
    }
    _validate_schema(response, "response.schema.json")

    fractional = dict(REQUEST, timeout_seconds=1.5)
    _validate_schema(fractional, "request.schema.json")
    fractional_response = retrieve(
        fractional,
        obelisk_bin="obelisk",
        timeout_cap_seconds=5,
        runner=runner,
    )
    assert math.isclose(calls[-1][1], 1.5)
    _validate_schema(fractional_response, "response.schema.json")

    invalid = dict(REQUEST, scope_ref="codex://threads/thread-a")
    before = len(calls)
    try:
        retrieve(invalid, runner=runner)
    except ValueError as exc:
        assert "host-session:codex" in str(exc)
    else:
        raise AssertionError("raw Codex deep link was accepted by the provider")
    assert len(calls) == before

    for field, value, expected_error in (
        ("max_results", 1.5, "max_results must be an integer"),
        ("timeout_seconds", 0, "timeout_seconds must be between"),
    ):
        malformed = dict(REQUEST, **{field: value})
        try:
            retrieve(malformed, runner=runner)
        except ValueError as exc:
            assert expected_error in str(exc), exc
        else:
            raise AssertionError(f"invalid {field} was accepted")
    assert len(calls) == before
    print("obelisk-provider-smoke: ok")


if __name__ == "__main__":
    main()
