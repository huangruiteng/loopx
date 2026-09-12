from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.capabilities.agent_turn_recall import runtime as recall_runtime
from loopx.capabilities.agent_turn_recall.runtime import (
    run_configured_agent_turn_recall,
)
from loopx.capabilities.reward_memory import outcome_lifecycle
from loopx.capabilities.reward_memory.outcome_lifecycle import (
    reconcile_pending_turn_outcome_ingests,
    run_configured_turn_outcome_ingest,
    run_configured_turn_outcome_ingest_fail_open,
    turn_outcome_ingest_sidecar_path,
)
from loopx.capabilities.context_providers.base import ContextProviderSync
from loopx.control_plane.turn_driver.executor import reward_memory_reflection_digest
from tests.capabilities.test_agent_turn_recall import normalized_config, quota_decision
from tests.capabilities.test_reward_memory_ingestion import FakeProvider


class OutcomeProvider(FakeProvider):
    provider_id = "openviking"


class AmbiguousOnceProvider(OutcomeProvider):
    def sync(self, **kwargs):
        completed = super().sync(**kwargs)
        if self.sync_calls != 1:
            return completed
        return ContextProviderSync(
            provider=self.provider_id,
            namespace=completed.namespace,
            status="committed_pending",
            observed_at=completed.observed_at,
            requested_count=1,
            completed_count=0,
            write_count=completed.write_count,
            result_refs=completed.result_refs,
            pending_count=1,
            reason_code="provider_commit_ambiguous",
            retry_disposition="retry_same_event",
        )


def _config(tmp_path: Path, *, automatic_ingest: bool = True):
    config = normalized_config(tmp_path)
    config["automation"]["automatic_ingest"] = automatic_ingest
    entry = config["corpora"]["agent_turn_preferences"]
    policy = entry["standing_policy"]
    policy["allowed_source_kinds"] = ["research_review"]
    policy["allowed_actor_roles"] = ["validated_goal_agent"]
    entry["corpus"]["maintenance"]["writeback_triggers"] = ["research_review"]
    return config


def _reflection(*, status: str = "eligible") -> str:
    if status == "no_evidence":
        return json.dumps(
            {
                "schema_version": "turn_reward_memory_reflection_v0",
                "status": "no_evidence",
            }
        )
    return json.dumps(
        {
            "schema_version": "turn_reward_memory_reflection_v0",
            "status": "eligible",
            "surface_id": "agent_workflow.turn_admission",
            "outcome_kind": "research",
            "content_summary": (
                "Require an exact timestamped provider read before comparing flows."
            ),
            "reasoning_summary": (
                "Independent validation showed stale snapshots reverse the conclusion."
            ),
            "confidence": "high",
            "evidence_refs": ["artifact:flow-probe", "receipt:validation"],
        }
    )


def _status(*, automatic_ingest: bool = True):
    return {
        "ok": True,
        "status": "available",
        "available": True,
        "automatic_recall": True,
        "automatic_ingest": automatic_ingest,
    }


def _settlement_evidence(reflection_json: str | None = None):
    reflection_json = reflection_json or _reflection()
    reflection = json.loads(reflection_json)
    return {
        "schema_version": "turn_post_settlement_evidence_v0",
        "task_validation": {
            "ok": True,
            "status": "passed",
            "validator_kind": "fixture-independent-validator",
            "reward_memory_reflection_validation": {
                "schema_version": "reward_memory_reflection_validation_v0",
                "status": "validated",
                "reflection_digest": reward_memory_reflection_digest(reflection_json),
                "evidence_refs": reflection["evidence_refs"],
            },
        },
        "writeback": {"ok": True, "appended": True},
        "quota_spend": {"ok": True, "appended": True},
    }


def test_validated_turn_reflection_writes_reads_back_and_replays(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    provider = OutcomeProvider()
    monkeypatch.setattr(
        outcome_lifecycle,
        "resolve_reward_memory_experiment",
        lambda **_kwargs: (_status(), config),
    )
    monkeypatch.setattr(outcome_lifecycle, "_goal_repo", lambda *_args: tmp_path)
    monkeypatch.setattr(
        recall_runtime,
        "resolve_reward_memory_experiment",
        lambda **_kwargs: (_status(), config),
    )
    monkeypatch.setattr(recall_runtime, "_goal_repo", lambda *_args: tmp_path)
    request = {
        "registry_path": tmp_path / "registry.json",
        "goal_id": "goal",
        "agent_id": "pilot",
        "turn_key": "sha256:validated-turn",
        "host_result": {
            "result_kind": "validated_progress",
            "reward_memory_reflection_json": _reflection(),
        },
        "settlement_evidence": _settlement_evidence(),
        "observed_at": "2026-08-02T10:00:00+00:00",
        "provider": provider,
    }

    first = run_configured_turn_outcome_ingest(**request)
    second = run_configured_turn_outcome_ingest(**request)

    assert first["status"] == "activated", first
    assert first["automatic_ingest"] is True
    assert first["provider_sync_count"] == 1
    assert first["exact_readback_verified"] is True
    assert first["external_writes_performed"] is True
    assert second["status"] == "activated"
    assert second["source_event_id"] == first["source_event_id"]
    assert second["deduplicated"] is True
    assert second["external_writes_performed"] is False
    assert second["sidecar_receipt_reused"] is True
    assert provider.sync_calls == 1
    assert provider.retrieve_calls == 1

    next_turn = run_configured_agent_turn_recall(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="pilot",
        quota_decision=quota_decision(),
        turn_instance_id="turn-after-validated-outcome",
        observed_at="2026-08-02T11:00:00+00:00",
        execute=True,
        provider=provider,
    )
    guidance = next_turn["context"]["guidance"]
    assert next_turn["status"] == "applied"
    assert guidance[0]["content_summary"] == (
        "Require an exact timestamped provider read before comparing flows."
    )
    assert str(guidance[0]["candidate_ref"]).startswith("candidate:")
    assert next_turn["outcome_ingest_reconciliation"]["status"] == "empty"


def test_no_evidence_and_explicit_disable_make_zero_provider_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OutcomeProvider()
    enabled = _config(tmp_path)
    monkeypatch.setattr(
        outcome_lifecycle,
        "resolve_reward_memory_experiment",
        lambda **_kwargs: (_status(), enabled),
    )
    monkeypatch.setattr(outcome_lifecycle, "_goal_repo", lambda *_args: tmp_path)
    no_evidence = run_configured_turn_outcome_ingest(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="pilot",
        turn_key="sha256:no-evidence",
        host_result={"reward_memory_reflection_json": _reflection(status="no_evidence")},
        provider=provider,
    )

    disabled = _config(tmp_path, automatic_ingest=False)
    monkeypatch.setattr(
        outcome_lifecycle,
        "resolve_reward_memory_experiment",
        lambda **_kwargs: (_status(automatic_ingest=False), disabled),
    )
    explicitly_disabled = run_configured_turn_outcome_ingest(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="pilot",
        turn_key="sha256:disabled",
        host_result={"reward_memory_reflection_json": _reflection()},
        settlement_evidence=_settlement_evidence(),
        provider=provider,
    )

    assert no_evidence["status"] == "no_eligible_evidence"
    assert explicitly_disabled["status"] == "explicitly_disabled"
    assert provider.sync_calls == 0
    assert provider.retrieve_calls == 0


def test_sibling_agent_scope_is_rejected_before_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    provider = OutcomeProvider()
    monkeypatch.setattr(
        outcome_lifecycle,
        "resolve_reward_memory_experiment",
        lambda **_kwargs: (_status(), config),
    )
    monkeypatch.setattr(outcome_lifecycle, "_goal_repo", lambda *_args: tmp_path)

    receipt = run_configured_turn_outcome_ingest_fail_open(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="sibling",
        turn_key="sha256:sibling",
        host_result={"reward_memory_reflection_json": _reflection()},
        provider=provider,
    )

    assert receipt["status"] == "runtime_unavailable"
    assert receipt["reason_code"] == "automatic_ingest_runtime_failed"
    assert provider.sync_calls == 0
    assert provider.retrieve_calls == 0


def test_ambiguous_write_reconciles_same_event_on_next_turn_without_duplication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    provider = AmbiguousOnceProvider()
    monkeypatch.setattr(
        outcome_lifecycle,
        "resolve_reward_memory_experiment",
        lambda **_kwargs: (_status(), config),
    )
    monkeypatch.setattr(outcome_lifecycle, "_goal_repo", lambda *_args: tmp_path)
    request = {
        "registry_path": tmp_path / "registry.json",
        "goal_id": "goal",
        "agent_id": "pilot",
        "turn_key": "sha256:ambiguous-turn",
        "host_result": {"reward_memory_reflection_json": _reflection()},
        "settlement_evidence": _settlement_evidence(),
        "observed_at": "2026-08-02T10:00:00+00:00",
        "provider": provider,
    }

    first = run_configured_turn_outcome_ingest(**request)

    assert first["status"] == "committed_pending"
    assert first["reconciliation_state"] == "pending"
    assert provider.sync_calls == 1
    assert provider.retrieve_calls == 0
    assert len(provider.resources) == 1

    config["automation"]["automatic_ingest"] = False
    disabled = reconcile_pending_turn_outcome_ingests(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="pilot",
        provider=provider,
    )
    assert disabled["status"] == "explicitly_disabled"
    assert provider.sync_calls == 1

    config["automation"]["automatic_ingest"] = True
    reconciled = reconcile_pending_turn_outcome_ingests(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="pilot",
        provider=provider,
    )

    assert reconciled["attempted_count"] == 1
    assert reconciled["completed_count"] == 1
    assert reconciled["receipts"][0]["exact_readback_verified"] is True
    assert reconciled["receipts"][0]["deduplicated"] is True
    assert provider.sync_calls == 2
    assert provider.retrieve_calls == 1
    assert len(provider.resources) == 1

    replayed = run_configured_turn_outcome_ingest(**request)
    assert replayed["sidecar_receipt_reused"] is True
    assert provider.sync_calls == 2

    path = turn_outcome_ingest_sidecar_path(
        tmp_path,
        goal_id="goal",
        agent_id="pilot",
        source_event_id=first["source_event_id"],
    )
    assert path.stat().st_mode & 0o777 == 0o600


def test_pending_outcome_direct_retry_reuses_stored_settlement_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    provider = AmbiguousOnceProvider()
    monkeypatch.setattr(
        outcome_lifecycle,
        "resolve_reward_memory_experiment",
        lambda **_kwargs: (_status(), config),
    )
    monkeypatch.setattr(outcome_lifecycle, "_goal_repo", lambda *_args: tmp_path)
    common = {
        "registry_path": tmp_path / "registry.json",
        "goal_id": "goal",
        "agent_id": "pilot",
        "turn_key": "sha256:direct-retry",
        "host_result": {"reward_memory_reflection_json": _reflection()},
        "provider": provider,
    }

    first = run_configured_turn_outcome_ingest(
        **common,
        settlement_evidence=_settlement_evidence(),
    )
    retried = run_configured_turn_outcome_ingest(**common)

    assert first["reconciliation_state"] == "pending"
    assert retried["exact_readback_verified"] is True
    assert retried["deduplicated"] is True
    assert provider.sync_calls == 2
    assert provider.retrieve_calls == 1
    assert len(provider.resources) == 1


def test_host_reflection_without_independent_evidence_binding_is_not_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    provider = OutcomeProvider()
    monkeypatch.setattr(
        outcome_lifecycle,
        "resolve_reward_memory_experiment",
        lambda **_kwargs: (_status(), config),
    )
    monkeypatch.setattr(outcome_lifecycle, "_goal_repo", lambda *_args: tmp_path)

    receipt = run_configured_turn_outcome_ingest(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="pilot",
        turn_key="sha256:self-attested",
        host_result={"reward_memory_reflection_json": _reflection()},
        provider=provider,
    )

    assert receipt["status"] == "evidence_validation_required"
    assert receipt["candidate_state"] == "awaiting_evidence_validation"
    assert provider.sync_calls == 0
    assert provider.retrieve_calls == 0


def test_reflection_validation_without_durable_settlement_is_not_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    provider = OutcomeProvider()
    monkeypatch.setattr(
        outcome_lifecycle,
        "resolve_reward_memory_experiment",
        lambda **_kwargs: (_status(), config),
    )
    monkeypatch.setattr(outcome_lifecycle, "_goal_repo", lambda *_args: tmp_path)
    evidence = _settlement_evidence()
    evidence["quota_spend"] = {"ok": True, "appended": False}

    receipt = run_configured_turn_outcome_ingest(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="pilot",
        turn_key="sha256:unsettled",
        host_result={"reward_memory_reflection_json": _reflection()},
        settlement_evidence=evidence,
        provider=provider,
    )

    assert receipt["status"] == "evidence_validation_required"
    assert receipt["candidate_state"] == "awaiting_evidence_validation"
    assert provider.sync_calls == 0
    assert provider.retrieve_calls == 0
