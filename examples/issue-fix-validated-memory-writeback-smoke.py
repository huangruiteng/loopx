#!/usr/bin/env python3
"""Smoke-test explicit, idempotent validated-outcome repository-memory writes."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.context_providers.base import ContextProviderSync  # noqa: E402
from loopx.capabilities.issue_fix.feasibility import (  # noqa: E402
    build_issue_fix_feasibility_packet,
)
from loopx.capabilities.issue_fix.outcome_projection import (  # noqa: E402
    build_issue_fix_outcome_projection,
)
from loopx.capabilities.issue_fix.repository_memory_provider import (  # noqa: E402
    write_issue_fix_validated_outcome_memory,
)


REVISION = "9cf42405a8bb0a8a17a66d4f953515f5a2c82620"
OBSERVED_AT = "2026-07-11T08:40:00+08:00"


class WritebackContractProvider:
    provider_id = "contract_provider"

    def __init__(self) -> None:
        self.contents: dict[str, str] = {}

    def retrieve(self, **kwargs: Any) -> Any:  # pragma: no cover
        raise AssertionError(kwargs)

    def sync(self, **kwargs: Any) -> ContextProviderSync:
        assert kwargs["execute"] is True, kwargs
        source, target = list(kwargs["resources"])[0]
        content = Path(source).read_text(encoding="utf-8")
        existing = self.contents.get(target)
        if existing is not None:
            assert existing == content, (existing, content)
        else:
            self.contents[target] = content
        return ContextProviderSync(
            provider=self.provider_id,
            namespace=str(kwargs["namespace"]),
            status="completed",
            observed_at=str(kwargs["observed_at"]),
            requested_count=1,
            completed_count=1,
            write_count=0 if existing is not None else 1,
            result_refs=(target,),
        )


def repository_context() -> dict[str, object]:
    return {
        "schema_version": "issue_fix_repository_context_input_v0",
        "repository_revision": REVISION,
        "sources": [
            {
                "source_id": "current-source",
                "source_kind": "source_code",
                "reference": "src/worker.py",
                "trust": "authoritative",
                "freshness": "current",
                "supports": ["change_scope", "reproduction"],
                "summary": "Current checkout bounds the affected worker path.",
            },
            {
                "source_id": "focused-test",
                "source_kind": "test_surface",
                "reference": "tests/test_worker.py",
                "trust": "verified",
                "freshness": "current",
                "supports": ["validation"],
                "summary": "Focused worker regression surface.",
            },
        ],
    }


def outcome_packet() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    feasibility = build_issue_fix_feasibility_packet(
        url="https://github.com/owner/repo/issues/7",
        reproduction_status="confirmed",
        reproduction_label="focused worker reproduction",
        scope_class="bounded",
        validation_label="focused worker regression",
        repository_context_input=repository_context(),
    )
    delivery = {
        "schema_version": "issue_fix_delivery_evidence_input_v0",
        "outcome_status": "completed",
        "validation_status": "passed",
        "validation_label": "passed focused public contract test",
        "changed_files": ["src/worker.py", "tests/test_worker.py"],
        "commit_ref": REVISION,
        "outputs": [
            {"kind": "pull_request", "url": "https://github.com/owner/repo/pull/8"}
        ],
        "risks": ["broader integration validation was not run"],
        "recorded_at": OBSERVED_AT,
    }
    outcome = build_issue_fix_outcome_projection(
        goal_id="public-issue-fix-goal",
        feasibility_packet=feasibility,
        delivery_evidence_input=delivery,
        agent_id="public-issue-fix-agent",
        generated_at=OBSERVED_AT,
    )
    return feasibility, delivery, outcome


def provider_config(provider: str = "contract_provider") -> dict[str, Any]:
    return {
        "schema_version": "issue_fix_repository_memory_provider_config_v0",
        "enabled": True,
        "provider": provider,
        "namespace": "public-repository",
        "visibility": "public",
        "scope_ref": f"viking://resources/public-repo/{REVISION}",
        "repository_revision": REVISION,
        "sync_timeout_seconds": 5,
        "writeback_enabled": True,
        "writeback_scope_ref": f"viking://resources/public-repo/{REVISION}",
        "workspace_scope": "owner-repo",
        "peer_scope": "issue-fix-agent",
    }


def assert_public_boundary(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    for forbidden in ("must never be written", "/Users/", "/private/tmp/"):
        assert forbidden not in text, (forbidden, text)


def main() -> int:
    feasibility, delivery, outcome = outcome_packet()
    provider = WritebackContractProvider()
    first = write_issue_fix_validated_outcome_memory(
        config=provider_config(),
        outcome_packet=outcome,
        repository_revision=REVISION,
        observed_at=OBSERVED_AT,
        execute=True,
        provider=provider,
    )
    retry = write_issue_fix_validated_outcome_memory(
        config=provider_config(),
        outcome_packet=outcome,
        repository_revision=REVISION,
        observed_at=OBSERVED_AT,
        execute=True,
        provider=provider,
    )
    assert first["status"] == "completed" and first["write_count"] == 1, first
    assert retry["status"] == "completed" and retry["write_count"] == 0, retry
    assert first["idempotency_key"] == retry["idempotency_key"]
    assert first["supersession_key_recorded"] is True
    stored_fact = next(iter(provider.contents.values()))
    for expected in (
        "issue_fix_validated_outcome_memory_v0",
        '"validation_status": "passed"',
        '"freshness": "revision_pinned"',
        '"supersession_key": "sha256:',
    ):
        assert expected in stored_fact, expected
    assert_public_boundary(first)
    assert_public_boundary(retry)

    disabled = write_issue_fix_validated_outcome_memory(
        config={**provider_config(), "writeback_enabled": False},
        outcome_packet=outcome,
        repository_revision=REVISION,
        observed_at=OBSERVED_AT,
        execute=True,
        provider=provider,
    )
    assert disabled["status"] == "disabled" and not disabled["external_writes_performed"]
    try:
        write_issue_fix_validated_outcome_memory(
            config=provider_config(),
            outcome_packet={**outcome, "raw_transcript": "must never be written"},
            repository_revision=REVISION,
            observed_at=OBSERVED_AT,
            execute=True,
            provider=provider,
        )
    except ValueError as exc:
        assert "unsafe field: raw_transcript" in str(exc), exc
    else:
        raise AssertionError("raw transcript writeback must be rejected")
    failed_outcome = json.loads(json.dumps(outcome))
    failed_outcome["issue_fix_outcomes"][0]["validation"]["status"] = "failed"
    try:
        write_issue_fix_validated_outcome_memory(
            config=provider_config(),
            outcome_packet=failed_outcome,
            repository_revision=REVISION,
            observed_at=OBSERVED_AT,
            execute=True,
            provider=provider,
        )
    except ValueError as exc:
        assert "requires passed validation" in str(exc), exc
    else:
        raise AssertionError("failed validation must block memory writeback")

    with tempfile.TemporaryDirectory(prefix="loopx-writeback-smoke-") as tmpdir:
        tmp = Path(tmpdir)
        fake_ov = tmp / "ov-contract"
        fake_ov.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "args = sys.argv[1:]\n"
            "if args == ['--version']: print('openviking 0.4.9.dev11')\n"
            "elif args and args[0] == 'status': print(json.dumps({'status':'healthy'}))\n"
            "elif args and args[0] == 'tree': print(json.dumps({'resources':[]}))\n"
            "elif args and args[0] in {'read','ls'}: sys.exit(1)\n"
            "elif args and args[0] in {'mkdir','add-resource'}: print(json.dumps({'result':'ok'}))\n"
            "else: sys.exit(2)\n",
            encoding="utf-8",
        )
        fake_ov.chmod(0o755)
        feasibility_path = tmp / "feasibility.json"
        delivery_path = tmp / "delivery.json"
        config_path = tmp / "provider.json"
        feasibility_path.write_text(json.dumps(feasibility), encoding="utf-8")
        delivery_path.write_text(json.dumps(delivery), encoding="utf-8")
        config_path.write_text(
            json.dumps(
                {
                    **provider_config("openviking"),
                    "provider_binary": str(fake_ov),
                }
            ),
            encoding="utf-8",
        )
        command = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "issue-fix",
            "outcome",
            "--goal-id",
            "public-issue-fix-goal",
            "--repo",
            "owner/repo",
            "--issue-ref",
            str(feasibility["observation"]["issue_ref"]),
            "--feasibility-json",
            str(feasibility_path),
            "--delivery-evidence-json",
            str(delivery_path),
            "--repository-memory-provider-json",
            str(config_path),
            "--write-repository-memory",
            "--generated-at",
            OBSERVED_AT,
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        packet = json.loads(result.stdout)
        assert packet["repository_memory_writeback"]["status"] == "completed"
        assert packet["repository_memory_writeback"]["write_count"] == 1
        assert packet["external_writes_performed"] is True
        assert packet["source_contract"]["repository_memory_writeback"] == (
            "issue_fix_validated_outcome_memory_writeback_v0"
        )
        assert packet["source_contract"]["writes_external_provider"] is True
        assert_public_boundary(packet)

    print("issue-fix-validated-memory-writeback-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
