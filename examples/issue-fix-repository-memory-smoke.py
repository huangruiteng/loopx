#!/usr/bin/env python3
"""Smoke-test provider-neutral repository-memory composition and fail-open use."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.feasibility import (  # noqa: E402
    build_issue_fix_feasibility_packet,
)
from loopx.capabilities.issue_fix.repository_context import (  # noqa: E402
    build_issue_fix_repository_context_packet,
)
from loopx.capabilities.issue_fix.repository_memory_provider import (  # noqa: E402
    retrieve_issue_fix_repository_memory,
    sync_issue_fix_repository_memory,
)
from loopx.capabilities.context_providers.base import (  # noqa: E402
    ContextProviderItem,
    ContextProviderRetrieval,
    ContextProviderSync,
)
from loopx.capabilities.context_providers.openviking import (  # noqa: E402
    OpenVikingContextProvider,
)

REVISION = "9cf42405a8bb0a8a17a66d4f953515f5a2c82620"
PREVIOUS_REVISION = "3aa42405a8bb0a8a17a66d4f953515f5a2c82111"
ISSUE_URL = "https://github.com/volcengine/OpenViking/issues/3124"


class ContractProvider:
    provider_id = "contract_provider"

    def __init__(self, *, resource_ref: str, content: str) -> None:
        self.resource_ref = resource_ref
        self.content = content

    def retrieve(self, **kwargs: Any) -> ContextProviderRetrieval:
        return ContextProviderRetrieval(
            provider="contract_provider",
            namespace=str(kwargs["namespace"]),
            status="completed",
            query_summary=str(kwargs["query_summary"]),
            observed_at=str(kwargs["observed_at"]),
            search_performed=True,
            read_performed=True,
            requested_limit=int(kwargs["max_results"]),
            items=(
                ContextProviderItem(
                    resource_ref=self.resource_ref,
                    summary="Provider returned the bounded current source candidate.",
                    content=self.content,
                    score=0.91,
                ),
            ),
        )

    def sync(self, **kwargs: Any) -> Any:  # pragma: no cover - retrieval contract only.
        raise AssertionError(kwargs)


class LifecycleProvider(ContractProvider):
    def __init__(
        self,
        *,
        resource_ref: str,
        content: str,
        sync_status: str = "completed",
    ) -> None:
        super().__init__(resource_ref=resource_ref, content=content)
        self.sync_status = sync_status
        self.retrieve_count = 0
        self.sync_count = 0

    def retrieve(self, **kwargs: Any) -> ContextProviderRetrieval:
        self.retrieve_count += 1
        return super().retrieve(**kwargs)

    def sync(self, **kwargs: Any) -> ContextProviderSync:
        self.sync_count += 1
        resources = list(kwargs["resources"])
        return ContextProviderSync(
            provider="contract_provider",
            namespace=str(kwargs["namespace"]),
            status=self.sync_status,
            observed_at=str(kwargs["observed_at"]),
            requested_count=len(resources),
            completed_count=len(resources) if self.sync_status == "completed" else 0,
            write_count=len(resources) if kwargs["execute"] else 0,
            result_refs=tuple(target for _source, target in resources),
            pending_count=(
                len(resources) if self.sync_status == "committed_pending" else 0
            ),
        )


class OpenVikingContractRunner:
    def __init__(self, *, scope_ref: str) -> None:
        self.scope_ref = scope_ref
        self.calls: list[list[str]] = []

    def __call__(
        self, command: list[str], **_kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        if command[1:] == ["--version"]:
            stdout = "openviking 0.4.9.dev11\n"
        elif command[1:3] == ["status", "-o"]:
            stdout = json.dumps({"status": "healthy"})
        elif command[1] == "search":
            stdout = json.dumps(
                {
                    "result": {
                        "resources": [
                            {
                                "uri": f"{self.scope_ref}/src/worker.py",
                                "abstract": "Bounded public worker contract evidence.",
                                "score": 0.93,
                            }
                        ]
                    }
                }
            )
        elif command[1] == "read":
            stdout = json.dumps(
                {"result": {"content": "private-to-call transient provider body"}}
            )
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(command, 0, stdout=stdout)


class UncertainWriteRunner:
    def __init__(
        self,
        *,
        target: str,
        source_content: str,
        post_write_state: str = "pending",
    ) -> None:
        self.target = target
        self.source_content = source_content
        self.post_write_state = post_write_state
        self.calls: list[list[str]] = []
        self.write_attempted = False

    def __call__(
        self, command: list[str], **_kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        args = command[1:]
        if args == ["--version"]:
            return subprocess.CompletedProcess(
                command, 0, stdout="openviking 0.4.9.dev40\n"
            )
        if args[:2] == ["status", "-o"]:
            return subprocess.CompletedProcess(
                command, 0, stdout=json.dumps({"status": "healthy"})
            )
        if args[0] == "add-resource":
            self.write_attempted = True
            return subprocess.CompletedProcess(command, 1, stdout="Connection Error")
        if args[0] == "read":
            if self.write_attempted and self.post_write_state == "verified":
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps({"result": self.source_content}),
                )
            return subprocess.CompletedProcess(command, 1, stdout="not found")
        if args[0] == "tree":
            rows = (
                [{"uri": self.target}]
                if self.write_attempted and self.post_write_state == "pending"
                else []
            )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"result": {"resources": rows}}),
            )
        if args[0] == "ls":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"result": {"resources": []}}),
            )
        if args[0] == "mkdir":
            return subprocess.CompletedProcess(
                command, 0, stdout=json.dumps({"ok": True})
            )
        raise AssertionError(command)


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
                "decision_influence": ["change_scope", "patch"],
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
    assert hook["verified_decision_influence_count"] == 1, hook
    assert hook["patch_influence_allowed_count"] == 1, hook
    assert hook["writeback_performed"] is False, hook
    assert hook["automatic_capture_performed"] is False, hook
    memory_sources = [
        row for row in context["sources"] if row["source_kind"] == "memory_retrieval"
    ]
    assert len(memory_sources) == 1, memory_sources
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

    ov_scope = f"viking://resources/public-repo/{REVISION}"
    ov_runner = OpenVikingContractRunner(scope_ref=ov_scope)
    ov_provider = OpenVikingContextProvider(
        executable="ov-contract",
        runner=ov_runner,
    )
    ov_retrieval = ov_provider.retrieve(
        namespace="public-repository",
        scope_ref=ov_scope,
        query="worker contract",
        query_summary="Current worker contract evidence.",
        max_results=2,
        timeout_seconds=5,
        observed_at="2026-07-11T03:30:00+08:00",
    )
    assert ov_retrieval.status == "completed", ov_retrieval
    assert ov_retrieval.search_performed is True
    assert ov_retrieval.read_performed is True
    assert len(ov_retrieval.items) == 1
    assert any(call[1] == "search" for call in ov_runner.calls)
    assert any(call[1] == "read" for call in ov_runner.calls)
    ov_public = ov_retrieval.public_packet()
    assert "private-to-call transient provider body" not in json.dumps(ov_public)
    assert ov_scope not in json.dumps(ov_public)
    assert_boundary(ov_public)

    with tempfile.TemporaryDirectory(prefix="loopx-memory-provider-") as tmpdir:
        checkout = Path(tmpdir)
        source = checkout / "src" / "worker.py"
        source.parent.mkdir(parents=True)
        source.write_text(
            "def current_contract():\n    return 'verified'\n", encoding="utf-8"
        )
        scope_ref = f"viking://resources/public-repo/{REVISION}"
        sync_plan = ov_provider.sync(
            namespace="public-repository",
            resources=[
                (
                    str(source),
                    f"viking://resources/public-repo/{REVISION}/src/worker.py",
                )
            ],
            timeout_seconds=5,
            observed_at="2026-07-11T03:30:00+08:00",
            execute=False,
        ).public_packet()
        assert sync_plan["status"] == "planned", sync_plan
        assert sync_plan["ok"] is True, sync_plan
        assert sync_plan["external_writes_performed"] is False, sync_plan
        assert_boundary(sync_plan)

        target = f"viking://resources/public-repo/{REVISION}/src/worker.py"
        uncertain_runner = UncertainWriteRunner(
            target=target,
            source_content=source.read_text(encoding="utf-8"),
        )
        uncertain_provider = OpenVikingContextProvider(
            executable="ov-contract",
            runner=uncertain_runner,
        )
        uncertain = uncertain_provider.sync(
            namespace="public-repository",
            resources=[(str(source), target)],
            timeout_seconds=5,
            observed_at="2026-07-11T03:30:00+08:00",
            execute=True,
        ).public_packet()
        assert uncertain["status"] == "committed_pending", uncertain
        assert uncertain["ok"] is True, uncertain
        assert uncertain["completed_count"] == 0, uncertain
        assert uncertain["pending_count"] == 1, uncertain
        assert uncertain["write_count"] == 1, uncertain
        assert uncertain["reconciliation_performed"] is True, uncertain
        assert uncertain["retry_disposition"] == "wait_and_reconcile", uncertain
        assert uncertain["external_writes_performed"] is True, uncertain
        assert_boundary(uncertain)

        verified_runner = UncertainWriteRunner(
            target=target,
            source_content=source.read_text(encoding="utf-8"),
            post_write_state="verified",
        )
        verified = (
            OpenVikingContextProvider(
                executable="ov-contract",
                runner=verified_runner,
            )
            .sync(
                namespace="public-repository",
                resources=[(str(source), target)],
                timeout_seconds=5,
                observed_at="2026-07-11T03:30:00+08:00",
                execute=True,
            )
            .public_packet()
        )
        assert verified["status"] == "completed", verified
        assert verified["completed_count"] == 1, verified
        assert verified["pending_count"] == 0, verified
        assert verified["write_count"] == 1, verified
        assert verified["reconciliation_performed"] is True, verified
        assert verified["retry_disposition"] == "no_retry", verified

        absent_runner = UncertainWriteRunner(
            target=target,
            source_content=source.read_text(encoding="utf-8"),
            post_write_state="absent",
        )
        absent = (
            OpenVikingContextProvider(
                executable="ov-contract",
                runner=absent_runner,
            )
            .sync(
                namespace="public-repository",
                resources=[(str(source), target)],
                timeout_seconds=5,
                observed_at="2026-07-11T03:30:00+08:00",
                execute=True,
            )
            .public_packet()
        )
        assert absent["status"] == "partial", absent
        assert absent["completed_count"] == 0, absent
        assert absent["pending_count"] == 0, absent
        assert absent["write_count"] == 0, absent
        assert absent["reconciliation_performed"] is True, absent
        assert absent["retry_disposition"] == "safe_to_retry", absent
        assert absent["reason_code"] == "provider_sync_write_failed_absent", absent

        generic_pending = ContextProviderSync(
            provider="fake-provider",
            namespace="public-repository",
            status="committed_pending",
            observed_at="2026-07-11T03:30:00+08:00",
            requested_count=1,
            completed_count=0,
            write_count=1,
            pending_count=1,
            reconciliation_performed=True,
            retry_disposition="wait_and_reconcile",
        ).public_packet()
        assert generic_pending["ok"] is True, generic_pending
        assert generic_pending["retry_disposition"] == "wait_and_reconcile"
        assert_boundary(generic_pending)
        provider_result = retrieve_issue_fix_repository_memory(
            config={
                "schema_version": "issue_fix_repository_memory_provider_config_v0",
                "enabled": True,
                "provider": "contract_provider",
                "namespace": "public-repository",
                "visibility": "public",
                "scope_ref": scope_ref,
                "repository_revision": REVISION,
                "max_results": 3,
                "timeout_seconds": 5,
            },
            repo_path=checkout,
            repository_revision=REVISION,
            query="current worker contract validation",
            query_summary="Current worker contract evidence.",
            supports=["change_scope", "validation"],
            observed_at="2026-07-11T03:30:00+08:00",
            provider=ContractProvider(
                resource_ref=f"{scope_ref}/src/worker.py",
                content=source.read_text(encoding="utf-8"),
            ),
        )
        provider_memory = provider_result["memory_input"]
        assert provider_memory["results"][0]["verification_status"] == "confirmed"
        assert (
            provider_memory["results"][0]["verification_reference"] == "src/worker.py"
        )
        assert provider_memory["latency_ms"] == 0
        assert provider_memory["requested_limit"] == 3
        assert provider_memory["configured_resource_count"] == 0
        assert provider_memory["stale_or_unmapped_count"] == 0
        assert provider_memory["verification_mode"] == "canonical_text_or_parser_chunk"
        assert provider_result["provider_projection"]["checkout_verification"] == {
            "revision": REVISION,
            "confirmed_count": 1,
            "stale_or_unmapped_count": 0,
            "verified_decision_influence_count": 0,
            "patch_influence_allowed_count": 0,
            "configured_resource_count": 0,
            "verification_mode": "canonical_text_or_parser_chunk",
        }
        assert_boundary(provider_result)

        lifecycle_root = "viking://resources/public-repository/example-repo"
        lifecycle_scope = f"{lifecycle_root}/{REVISION[:12]}/repository-context"
        lifecycle_provider = LifecycleProvider(
            resource_ref=f"{lifecycle_scope}/src/worker.py",
            content=source.read_text(encoding="utf-8"),
        )
        lifecycle_config = {
            "schema_version": "issue_fix_repository_memory_provider_config_v0",
            "enabled": True,
            "provider": "contract_provider",
            "namespace": "public-repository",
            "visibility": "public",
            "revision_policy": "checkout_head",
            "repository_scope_root": lifecycle_root,
            "active_repository_revision": PREVIOUS_REVISION,
            "resource_references": ["src/worker.py"],
            "max_results": 3,
            "timeout_seconds": 5,
            "sync_timeout_seconds": 5,
        }
        stale_retrieval = retrieve_issue_fix_repository_memory(
            config=lifecycle_config,
            repo_path=checkout,
            repository_revision=REVISION,
            query="current worker contract validation",
            query_summary="Current worker contract evidence.",
            supports=["change_scope", "validation"],
            observed_at="2026-07-11T03:30:00+08:00",
            provider=lifecycle_provider,
        )
        assert stale_retrieval["memory_input"]["status"] == "unavailable"
        assert (
            stale_retrieval["memory_input"]["reason_code"]
            == "current_revision_not_activated"
        )
        lifecycle_plan = stale_retrieval["provider_projection"][
            "repository_context_lifecycle"
        ]
        assert lifecycle_plan["revision_changed"] is True, lifecycle_plan
        assert lifecycle_plan["sync_required"] is True, lifecycle_plan
        assert lifecycle_plan["retrieval_allowed"] is False, lifecycle_plan
        assert lifecycle_provider.retrieve_count == 0
        assert lifecycle_root not in json.dumps(stale_retrieval)
        assert_boundary(stale_retrieval)

        lifecycle_sync = sync_issue_fix_repository_memory(
            config=lifecycle_config,
            repo_path=checkout,
            repository_revision=REVISION,
            references=["src/worker.py"],
            observed_at="2026-07-11T03:31:00+08:00",
            execute=True,
            provider=lifecycle_provider,
        )
        activation = lifecycle_sync["repository_context_activation"]
        assert activation["status"] == "activated", activation
        assert activation["active_repository_revision"] == REVISION, activation
        assert activation["previous_repository_revision"] == PREVIOUS_REVISION
        assert activation["retrieval_allowed"] is True, activation
        assert lifecycle_provider.sync_count == 1
        assert lifecycle_root not in json.dumps(lifecycle_sync)
        assert_boundary(lifecycle_sync)

        pending_provider = LifecycleProvider(
            resource_ref=f"{lifecycle_scope}/src/worker.py",
            content=source.read_text(encoding="utf-8"),
            sync_status="committed_pending",
        )
        pending_sync = sync_issue_fix_repository_memory(
            config=lifecycle_config,
            repo_path=checkout,
            repository_revision=REVISION,
            references=["src/worker.py"],
            observed_at="2026-07-11T03:31:30+08:00",
            execute=True,
            provider=pending_provider,
        )
        pending_activation = pending_sync["repository_context_activation"]
        assert pending_activation["status"] == "activation_pending"
        assert pending_activation["active_repository_revision"] is None
        assert pending_activation["retrieval_allowed"] is False
        assert_boundary(pending_sync)

        activated_config = {
            **lifecycle_config,
            "active_repository_revision": REVISION,
        }
        activated_retrieval = retrieve_issue_fix_repository_memory(
            config=activated_config,
            repo_path=checkout,
            repository_revision=REVISION,
            query="current worker contract validation",
            query_summary="Current worker contract evidence.",
            supports=["change_scope", "validation"],
            observed_at="2026-07-11T03:32:00+08:00",
            provider=lifecycle_provider,
        )
        active_plan = activated_retrieval["provider_projection"][
            "repository_context_lifecycle"
        ]
        assert active_plan["sync_required"] is False, active_plan
        assert active_plan["retrieval_allowed"] is True, active_plan
        assert lifecycle_provider.retrieve_count == 1
        assert (
            activated_retrieval["memory_input"]["results"][0]["verification_status"]
            == "confirmed"
        )
        assert_boundary(activated_retrieval)

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

    invalid_influence = json.loads(json.dumps(memory_input))
    invalid_influence["results"][1]["decision_influence"] = ["patch"]
    try:
        build_issue_fix_repository_context_packet(
            repo="owner/repo",
            issue_ref="issue_1",
            context_input=context_input,
            memory_retrieval_input=invalid_influence,
        )
    except ValueError as exc:
        assert "must be confirmed before recording decision influence" in str(exc), exc
    else:
        raise AssertionError("unverified memory must not claim decision influence")

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

        provider_config_path = tmp / "provider-config.json"
        provider_config_path.write_text(
            json.dumps(
                {
                    "schema_version": "issue_fix_repository_memory_provider_config_v0",
                    "enabled": False,
                    "provider": "openviking",
                    "namespace": "public-repository",
                    "visibility": "public",
                    "scope_ref": f"viking://resources/public-repo/{REVISION}",
                    "repository_revision": REVISION,
                    "max_results": 3,
                    "timeout_seconds": 5,
                }
            ),
            encoding="utf-8",
        )
        configured_command = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "issue-fix",
            "workflow-plan",
            "--url",
            ISSUE_URL,
            "--repo-path",
            str(tmp),
            "--repository-context-json",
            str(context_path),
            "--validation-label",
            "focused VLM status regression",
        ]
        configured_result = subprocess.run(
            configured_command,
            cwd=ROOT,
            env={
                **os.environ,
                "LOOPX_ISSUE_FIX_REPOSITORY_MEMORY_PROVIDER_CONFIG": str(
                    provider_config_path
                ),
            },
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        configured_packet = json.loads(configured_result.stdout)
        configured_hook = configured_packet["repository_context"]["memory_projection"][
            "retrieval_hook"
        ]
        assert configured_hook["status"] == "disabled", configured_hook
        assert configured_hook["provider"] == "openviking", configured_hook
        assert_boundary(configured_packet)

    print("issue-fix-repository-memory-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
