#!/usr/bin/env python3
"""Smoke-test provider-neutral repository-memory composition and fail-open use."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.feasibility import (  # noqa: E402
    build_issue_fix_feasibility_packet,
)
from loopx.capabilities.issue_fix.repository_context import (  # noqa: E402
    build_issue_fix_repository_context_packet,
)

REVISION = "9cf42405a8bb0a8a17a66d4f953515f5a2c82620"
ISSUE_URL = "https://github.com/volcengine/OpenViking/issues/3124"


def repository_context() -> dict[str, object]:
    return {
        "schema_version": "issue_fix_repository_context_input_v0",
        "repository_revision": REVISION,
        "sources": [
            {
                "source_id": "current-source",
                "source_kind": "source_code",
                "reference": "openviking/server/api/v1/vlm.py",
                "trust": "authoritative",
                "freshness": "current",
                "supports": ["change_scope", "reproduction"],
                "summary": "Current checkout bounds the affected VLM status path.",
            },
            {
                "source_id": "focused-test",
                "source_kind": "test_surface",
                "reference": "tests/unit/server/test_vlm_status.py",
                "trust": "verified",
                "freshness": "current",
                "supports": ["validation"],
                "summary": "Focused status regression surface.",
            },
        ],
    }


def completed_memory() -> dict[str, object]:
    return {
        "schema_version": "issue_fix_repository_memory_read_result_v0",
        "provider": "fake_memory",
        "namespace": "public_repository_memory",
        "visibility": "public",
        "status": "completed",
        "query_summary": "Prior public VLM status fixes and validation lessons.",
        "observed_at": "2026-07-11T02:40:00+08:00",
        "search_performed": True,
        "read_performed": True,
        "writeback_performed": False,
        "automatic_capture_performed": False,
        "results": [
            {
                "memory_ref": "provider-private-record-1",
                "summary": "A prior fix kept provider failures distinct from status.",
                "supports": ["change_scope", "reproduction"],
                "verification_status": "confirmed",
                "verification_reference": "openviking/server/api/v1/vlm.py",
                "verification_revision": REVISION,
            },
            {
                "memory_ref": "provider-private-record-2",
                "summary": "A historical validation hint still needs checkout proof.",
                "supports": ["validation"],
                "verification_status": "unverified",
            },
        ],
    }


def unavailable_openviking() -> dict[str, object]:
    return {
        "schema_version": "issue_fix_repository_memory_read_result_v0",
        "provider": "openviking_codex_memory",
        "namespace": "openviking_public_repository",
        "visibility": "public",
        "status": "unavailable",
        "query_summary": "Public OpenViking repository history for issue 3124.",
        "observed_at": "2026-07-11T02:40:00+08:00",
        "search_performed": False,
        "read_performed": False,
        "reason_code": "connector_unavailable",
        "writeback_performed": False,
        "automatic_capture_performed": False,
        "results": [],
    }


def assert_boundary(payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    for forbidden in (
        "provider-private-record-1",
        "provider-private-record-2",
        "raw memory body",
        "credential-value",
        "/Users/",
        "/private/tmp/",
    ):
        assert forbidden not in text, (forbidden, text)


def main() -> int:
    context_input = repository_context()
    memory_input = completed_memory()
    context = build_issue_fix_repository_context_packet(
        repo="volcengine/OpenViking",
        issue_ref="issue_3124",
        context_input=context_input,
        memory_retrieval_input=memory_input,
    )
    assert context["ok"] is True, context
    assert context["context_status"] == "grounded", context
    assert context["external_reads_performed"] is True, context
    hook = context["memory_projection"]["retrieval_hook"]
    assert hook["status"] == "used", hook
    assert hook["result_count"] == 2, hook
    assert hook["confirmed_count"] == 1, hook
    assert hook["unverified_count"] == 1, hook
    assert hook["patch_influence_allowed_count"] == 1, hook
    assert hook["writeback_performed"] is False, hook
    assert hook["automatic_capture_performed"] is False, hook
    memory_sources = [
        row for row in context["sources"] if row["source_kind"] == "memory_retrieval"
    ]
    assert len(memory_sources) == 2, memory_sources
    assert all(row["trust"] == "advisory" for row in memory_sources), memory_sources
    assert all(row["reference"].startswith("memory:") for row in memory_sources)
    assert_boundary(context)

    feasibility = build_issue_fix_feasibility_packet(
        url=ISSUE_URL,
        reproduction_status="planned",
        reproduction_label="focused VLM status reproduction",
        scope_class="bounded",
        validation_label="focused VLM status regression",
        repository_context_input=context_input,
        repository_memory_input=memory_input,
    )
    assert feasibility["decision"]["route"] == "fix_pr", feasibility
    assert feasibility["repository_context_effect"]["route_overridden"] is False
    assert_boundary(feasibility)

    unavailable = build_issue_fix_repository_context_packet(
        repo="volcengine/OpenViking",
        issue_ref="issue_3124",
        context_input=context_input,
        memory_retrieval_input=unavailable_openviking(),
    )
    unavailable_hook = unavailable["memory_projection"]["retrieval_hook"]
    assert unavailable["ok"] is True, unavailable
    assert unavailable["context_status"] == "grounded", unavailable
    assert unavailable_hook["status"] == "unavailable", unavailable_hook
    assert unavailable_hook["reason_code"] == "connector_unavailable"
    assert unavailable_hook["fail_open"] is True
    assert unavailable_hook["source_refs"] == []
    assert_boundary(unavailable)

    invalid_capture = dict(memory_input)
    invalid_capture["automatic_capture_performed"] = True
    try:
        build_issue_fix_repository_context_packet(
            repo="owner/repo",
            issue_ref="issue_1",
            context_input=context_input,
            memory_retrieval_input=invalid_capture,
        )
    except ValueError as exc:
        assert "automatic capture" in str(exc), exc
    else:
        raise AssertionError("automatic memory capture must be rejected")

    with tempfile.TemporaryDirectory(prefix="loopx-memory-hook-") as tmpdir:
        tmp = Path(tmpdir)
        context_path = tmp / "context.json"
        memory_path = tmp / "memory.json"
        context_path.write_text(json.dumps(context_input), encoding="utf-8")
        memory_path.write_text(json.dumps(memory_input), encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "issue-fix",
            "workflow-plan",
            "--url",
            ISSUE_URL,
            "--repository-context-json",
            str(context_path),
            "--repository-memory-json",
            str(memory_path),
            "--validation-label",
            "focused VLM status regression",
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        cli_packet = json.loads(result.stdout)
        cli_hook = cli_packet["repository_context"]["memory_projection"][
            "retrieval_hook"
        ]
        assert cli_hook["status"] == "used", cli_hook
        assert cli_hook["confirmed_count"] == 1, cli_hook
        assert_boundary(cli_packet)

    print("issue-fix-repository-memory-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
