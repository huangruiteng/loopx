#!/usr/bin/env python3
"""Smoke-test that live auto-research E2E claims require lane-authored evidence."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "loopx-auto-research-knn"
AGENT_ID = "codex-side-bypass"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def run_cli(
    args: list[str],
    *,
    registry: Path,
    runtime_root: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime_root),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def base_demo_args() -> list[str]:
    return [
        "auto-research",
        "demo-e2e",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--reasoning-effort",
        "high",
    ]


def live_evidence_payload(*, claim_authority: dict[str, str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "auto_research_live_codex_lane_e2e_evidence_v0",
        "source": "live_codex_lane_output",
        "goal_id": GOAL_ID,
        "agent_id": AGENT_ID,
        "visible_lanes": {
            "launched": True,
            "accepted": True,
            "lane_count": 3,
        },
        "lane_evidence": {
            "lane_authored": True,
            "evidence_source": "live_codex_lane_output",
            "append_status": "appended_to_loopx_state",
            "evidence_event_count": 3,
            "result_status": "supported",
            "protected_scope_clean": True,
            "dev_metric": 4.0,
            "holdout_metric": 4.5,
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
            "local_workspace_path_redacted": True,
        },
    }
    if claim_authority:
        payload["claim_authority"] = claim_authority
    return payload


def assert_public_board_claim_boundary(payload: dict[str, Any]) -> None:
    boundary = payload["board"]["claim_boundary"]
    assert boundary["schema_version"] == "auto_research_public_claim_boundary_v0", payload
    assert boundary["metric_source_kind"] == "loopx_rollout_event_log", payload
    assert boundary["claim_source"] == "live_codex_e2e", payload
    assert boundary["live_claim_scope"] == "dev_only", payload
    assert boundary["holdout_result_scope"] == "rollout_context_only", payload
    assert boundary["holdout_claim_allowed"] is False, payload
    assert boundary["promotion_result_scope"] == "candidate_only_not_auto_promoted", payload
    assert boundary["promotion_claim_allowed"] is False, payload
    assert boundary["first_screen_claim_allowed"] is False, payload
    assert "automatic_promotion" in boundary["blocked_claims"], payload


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )

        no_live = run_cli(
            [*base_demo_args(), "--execute"],
            registry=registry,
            runtime_root=runtime_root,
        )
        no_live_payload = json.loads(no_live.stdout)
        assert no_live_payload["ok"] is True, no_live_payload
        assert no_live_payload["live_codex_e2e"]["executed"] is False, no_live_payload
        assert no_live_payload["live_codex_e2e"]["claim_allowed"] is False, no_live_payload
        assert no_live_payload["live_codex_e2e"]["evidence_source"] == (
            "not_collected_from_codex_lane_output"
        ), no_live_payload
        assert_public_board_claim_boundary(no_live_payload)

        evidence = temp / "live-evidence.public.json"
        evidence.write_text(json.dumps(live_evidence_payload(), sort_keys=True), encoding="utf-8")

        dry_run_with_evidence = run_cli(
            [*base_demo_args(), "--live-evidence", str(evidence)],
            registry=registry,
            runtime_root=runtime_root,
            check=False,
        )
        assert dry_run_with_evidence.returncode == 1, dry_run_with_evidence.stdout
        dry_error = json.loads(dry_run_with_evidence.stdout)
        assert dry_error["ok"] is False, dry_error
        assert "--live-evidence requires --execute" in dry_error["error"], dry_error
        assert_public_safe(dry_error)

        bad_evidence = temp / "bad-live-evidence.public.json"
        bad_payload = live_evidence_payload()
        bad_payload["source"] = "generated_quickstart_pack_protected_eval_replay"
        bad_evidence.write_text(json.dumps(bad_payload, sort_keys=True), encoding="utf-8")
        rejected = run_cli(
            [*base_demo_args(), "--execute", "--live-evidence", str(bad_evidence)],
            registry=registry,
            runtime_root=runtime_root,
            check=False,
        )
        assert rejected.returncode == 1, rejected.stdout
        rejected_payload = json.loads(rejected.stdout)
        assert rejected_payload["ok"] is False, rejected_payload
        assert "source must be live_codex_lane_output" in rejected_payload["error"], rejected_payload
        assert_public_safe(rejected_payload)

        claimed = run_cli(
            [*base_demo_args(), "--execute", "--live-evidence", str(evidence)],
            registry=registry,
            runtime_root=runtime_root,
        )
        claimed_payload = json.loads(claimed.stdout)
        live = claimed_payload["live_codex_e2e"]
        protected_eval = claimed_payload["protected_eval_result"]
        research_loop = claimed_payload["research_loop"]
        assert claimed_payload["ok"] is True, claimed_payload
        assert protected_eval["dev_metric"] == 4.0, claimed_payload
        assert protected_eval["holdout_metric"] == 4.5, claimed_payload
        assert research_loop["dev_metric"] == 4.0, claimed_payload
        assert research_loop["holdout_metric"] == 4.5, claimed_payload
        assert live["executed"] is True, claimed_payload
        assert live["claim_allowed"] is True, claimed_payload
        assert live["claim_scope"] == "dev_only", claimed_payload
        assert live["dev_claim_allowed"] is True, claimed_payload
        assert live["holdout_claim_allowed"] is False, claimed_payload
        assert live["promotion_claim_allowed"] is False, claimed_payload
        assert live["holdout_claim_authority"] is None, claimed_payload
        assert live["promotion_claim_authority"] is None, claimed_payload
        assert live["evidence_source"] == "live_codex_lane_output", claimed_payload
        assert live["evidence_event_count"] == 3, claimed_payload
        assert live["result_status"] == "supported", claimed_payload
        assert live["dev_metric"] == 4.0, claimed_payload
        assert live["holdout_metric"] is None, claimed_payload
        assert live["holdout_metric_present"] is True, claimed_payload
        assert live["holdout_metric_redacted"] is True, claimed_payload
        assert live["holdout_claim_blocked_reason"] == (
            "requires_separate_heldout_live_evidence_or_owner_approval"
        ), claimed_payload
        assert live["promotion_claim_blocked_reason"] == (
            "requires_separate_heldout_live_evidence_or_owner_approval"
        ), claimed_payload
        assert live["public_boundary"]["raw_logs_recorded"] is False, claimed_payload
        assert live["public_boundary"]["private_artifacts_recorded"] is False, claimed_payload
        assert live["public_boundary"]["absolute_paths_recorded"] is False, claimed_payload
        assert live["public_boundary"]["credentials_recorded"] is False, claimed_payload
        assert live["public_boundary"]["local_workspace_path_redacted"] is True, claimed_payload
        assert_public_board_claim_boundary(claimed_payload)
        assert_public_safe(claimed_payload)

        authorized_evidence = temp / "authorized-live-evidence.public.json"
        authorized_evidence.write_text(
            json.dumps(
                live_evidence_payload(
                    claim_authority={
                        "holdout_claim": "separate_heldout_live_evidence",
                        "promotion_claim": "owner_approval",
                        "source_ref": "owner-approved-live-claim-fixture",
                    }
                ),
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        authorized = run_cli(
            [*base_demo_args(), "--execute", "--live-evidence", str(authorized_evidence)],
            registry=registry,
            runtime_root=runtime_root,
        )
        authorized_payload = json.loads(authorized.stdout)
        authorized_live = authorized_payload["live_codex_e2e"]
        assert authorized_live["claim_scope"] == "promotion_claim_authorized", authorized_payload
        assert authorized_live["holdout_claim_allowed"] is True, authorized_payload
        assert authorized_live["promotion_claim_allowed"] is True, authorized_payload
        assert authorized_live["holdout_claim_authority"] == "separate_heldout_live_evidence", authorized_payload
        assert authorized_live["promotion_claim_authority"] == "owner_approval", authorized_payload
        assert authorized_live["holdout_metric"] == 4.5, authorized_payload
        assert authorized_live["holdout_metric_redacted"] is False, authorized_payload
        assert authorized_live["holdout_claim_blocked_reason"] is None, authorized_payload
        assert authorized_live["promotion_claim_blocked_reason"] is None, authorized_payload
        assert_public_safe(authorized_payload)

    print("auto-research-live-codex-claim-boundary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
