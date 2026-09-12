from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from loopx.capabilities.reward_memory import codex_app_outcome
from loopx.capabilities.reward_memory.codex_app_outcome import (
    codex_app_outcome_candidate_sidecar_path,
    run_staged_codex_app_turn_outcome_ingest,
    stage_codex_app_turn_outcome_candidate,
)


def _reflection() -> str:
    return json.dumps(
        {
            "schema_version": "turn_reward_memory_reflection_v0",
            "status": "eligible",
            "surface_id": "agent_workflow.turn_admission",
            "outcome_kind": "engineering",
            "content_summary": "Run the exact admission test before changing routing.",
            "reasoning_summary": "The independently checked route avoided stale state.",
            "confidence": "high",
            "evidence_refs": ["artifact:app-route", "receipt:app-validation"],
        }
    )


def _validator(path: Path, *, attest: bool) -> list[str]:
    body = (
        "import json,sys; r=json.load(sys.stdin); "
        + (
            "print(json.dumps({'schema_version':"
            "'reward_memory_reflection_validation_v0','status':'validated',"
            "'reflection_digest':r['reflection_digest'],"
            "'evidence_refs':r['reflection']['evidence_refs']}))"
            if attest
            else "print('validation passed without reflection attestation')"
        )
    )
    path.write_text(body + "\n", encoding="utf-8")
    return [sys.executable, str(path)]


def test_app_refresh_stages_private_candidate_and_spend_finalizes_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv = _validator(tmp_path / "validate.py", attest=True)
    monkeypatch.setattr(
        codex_app_outcome,
        "_validation_declaration",
        lambda **_kwargs: {
            "validation_command": None,
            "validation_command_argv": argv,
            "validation_label": "app reflection validator",
            "validation_timeout_seconds": 5,
        },
    )
    monkeypatch.setattr(
        codex_app_outcome,
        "_goal_repo",
        lambda *_args, **_kwargs: tmp_path,
    )

    staged = stage_codex_app_turn_outcome_candidate(
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        goal_id="goal",
        agent_id="pilot",
        todo_id="todo_app",
        turn_instance_id="turn-app",
        effect_id="effect:app",
        state_file=tmp_path / "ACTIVE_GOAL_STATE.md",
        validation_workspace=tmp_path,
        reflection_json=_reflection(),
        observed_at="2026-09-13T03:00:00+00:00",
    )

    assert staged["status"] == "validation_bound"
    assert staged["validation_bound"] is True
    assert staged["raw_content_projected"] is False
    assert staged["external_writes_performed"] is False
    path = codex_app_outcome_candidate_sidecar_path(
        tmp_path,
        goal_id="goal",
        agent_id="pilot",
        candidate_id=staged["candidate_id"],
    )
    assert path.stat().st_mode & 0o777 == 0o600

    observed: dict[str, Any] = {}

    def ingest(**kwargs: Any) -> dict[str, Any]:
        observed.update(kwargs)
        return {
            "ok": True,
            "status": "activated",
            "external_writes_performed": True,
        }

    monkeypatch.setattr(
        codex_app_outcome,
        "run_configured_turn_outcome_ingest",
        ingest,
    )
    finalized = run_staged_codex_app_turn_outcome_ingest(
        registry_path=tmp_path / "registry.json",
        goal_id="goal",
        agent_id="pilot",
        todo_id="todo_app",
        turn_instance_id="turn-app",
        effect_id="effect:app",
        candidate_id=staged["candidate_id"],
        writeback_appended=True,
        spend_appended=True,
    )

    assert finalized["status"] == "activated"
    assert finalized["host_wiring"] == (
        "codex_app_refresh_spend_post_settlement"
    )
    assert observed["turn_key"] == "effect:app"
    evidence = observed["settlement_evidence"]
    assert evidence["task_validation"]["ok"] is True
    assert evidence["writeback"] == {"ok": True, "appended": True}
    assert evidence["quota_spend"] == {"ok": True, "appended": True}


def test_app_refresh_without_exact_validator_attestation_stays_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv = _validator(tmp_path / "validate.py", attest=False)
    monkeypatch.setattr(
        codex_app_outcome,
        "_validation_declaration",
        lambda **_kwargs: {
            "validation_command": None,
            "validation_command_argv": argv,
            "validation_label": "ordinary validator",
            "validation_timeout_seconds": 5,
        },
    )
    monkeypatch.setattr(
        codex_app_outcome,
        "_goal_repo",
        lambda *_args, **_kwargs: tmp_path,
    )

    staged = stage_codex_app_turn_outcome_candidate(
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        goal_id="goal",
        agent_id="pilot",
        todo_id="todo_app",
        turn_instance_id="turn-app",
        effect_id="effect:app",
        state_file=tmp_path / "ACTIVE_GOAL_STATE.md",
        validation_workspace=tmp_path,
        reflection_json=_reflection(),
        observed_at="2026-09-13T03:00:00+00:00",
    )

    assert staged["status"] == "awaiting_evidence_validation"
    assert staged["validation_bound"] is False
    assert staged["provider_sync_count"] == 0
    assert staged["external_writes_performed"] is False
