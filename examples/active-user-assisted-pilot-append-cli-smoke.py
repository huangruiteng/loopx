#!/usr/bin/env python3
"""Smoke-test appending compact active_user_assisted_pilot_v0 events."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import collect_status  # noqa: E402


GOAL_ID = "active-user-assisted-pilot-append-fixture"
PILOT_SCHEMA = "active_user_assisted_pilot_v0"
ACTIVE_INJECTION_SCHEMA = "active_user_simulator_injection_v0"
RUN_SCHEMA = "operator_simulator_run_v0"


NO_ORACLE_AUDIT_KEYS = [
    "hidden_tests_seen",
    "expected_solution_seen",
    "answer_key_seen",
    "private_material_seen",
    "raw_forbidden_logs_seen",
    "direct_patch_supplied",
    "tool_executed_for_worker",
    "benchmark_scoring_or_resource_changed",
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def active_user_pilot_event() -> dict[str, Any]:
    return {
        "schema_version": PILOT_SCHEMA,
        "pilot_id": "train-fasttext-active-user-assisted-pilot-v0",
        "benchmark_id": "terminal-bench@2.0",
        "task_id": "train-fasttext",
        "trigger": {
            "kind": "previous_compact_negative_result",
            "failed_autonomous_modes": [
                {"mode": "hardened_codex_baseline", "official_task_score": 0.0},
                {"mode": "codex_loopx", "official_task_score": 0.0},
            ],
            "both_autonomous_modes_failed": True,
            "assisted_score_kind": "not_run",
        },
        "active_injection_contract": {
            "schema_version": ACTIVE_INJECTION_SCHEMA,
            "simulator_setting": "deterministic_scripted_user",
            "proactive_intervention_allowed": True,
            "directive_feedback_allowed": True,
            "artificial_mildness_required": False,
        },
        "frequency_budget": {
            "max_interventions": 3,
            "max_proactive_interventions": 2,
            "min_worker_events_between_proactive": 2,
            "max_chars_per_intervention": 800,
        },
        "visibility_policy": {
            "policy_id": "compact_failure_and_worker_visible_state_only",
            "allowed": [
                "public_task_statement",
                "compact_failure_summary",
                "worker_visible_validation_output",
                "public_safe_loopx_state_summary",
            ],
            "forbidden": [
                "hidden_tests",
                "expected_solutions",
                "benchmark_answer_keys",
                "private_project_material",
                "raw_runner_logs",
                "local_host_paths",
            ],
        },
        "operator_simulator_run": {
            "schema_version": RUN_SCHEMA,
            "simulator_identity": {
                "setting": "deterministic_scripted_user",
                "model_family": "scripted",
                "seed": "active-user-assisted-pilot-v0",
            },
            "interventions": [
                {
                    "turn": 1,
                    "proactive": True,
                    "type": "strategy_redirection",
                    "chars": 312,
                    "worker_events_since_previous_proactive": 3,
                    "no_oracle_audit": {key: False for key in NO_ORACLE_AUDIT_KEYS},
                    "raw_simulator_message": "This field must not survive compaction.",
                },
                {
                    "turn": 2,
                    "proactive": True,
                    "type": "validation_triage",
                    "chars": 241,
                    "worker_events_since_previous_proactive": 2,
                    "no_oracle_audit": {key: False for key in NO_ORACLE_AUDIT_KEYS},
                },
            ],
            "official_task_score_reference": {
                "kind": "not_run",
                "value": None,
                "reason": "deterministic assisted pilot does not execute Terminal-Bench",
            },
            "simulator_induced_error_count": 0,
            "frequency_budget_audit": {
                "proactive_interventions": 2,
                "max_proactive_interventions": 2,
                "min_worker_events_between_proactive_satisfied": True,
            },
            "side_effect_audit": {
                "model_api": False,
                "benchmark_run": False,
                "docker": False,
                "cloud_sandbox": False,
                "paid_compute": False,
                "private_artifact_read": False,
                "leaderboard_upload": False,
            },
            "next_run_decision": {
                "decision": "eligible_for_private_no_upload_assisted_treatment",
                "minimum_next_evidence": "real no-upload assisted treatment with separate official score",
                "requires_real_runner_approval": True,
                "keep_official_scores_separate": True,
            },
            "raw" + "_runner_log_path": "/" + "U" + "sers/example/private/raw.log",
        },
        "claim_boundary": {
            "official_score_claim_allowed": False,
            "assisted_collaboration_claim_allowed": True,
            "leaderboard_claim_allowed": False,
        },
        "local" + "_artifact_path": "/" + "t" + "mp/private/active-user-pilot.json",
    }


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    pilot_path = root / "active_user_pilot.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-10T00:00:00+00:00\n"
        "---\n\n"
        "# Active User Assisted Pilot Append Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Append compact active_user_assisted_pilot_v0 through the CLI.\n\n"
        "## Next Action\n\n"
        "- Inspect the appended active-user assisted pilot projection.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-10T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "benchmark-active-user-pilot",
                    "status": "active-read-only",
                    "repo": str(project),
                    "state_file": state_file,
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                    "quota": {"compute": 1.0, "window_hours": 24},
                    "authority_sources": [],
                }
            ],
        },
    )
    write_json(pilot_path, active_user_pilot_event())
    return registry_path, runtime, pilot_path


def run_cli(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def assert_no_private_surface(summary: dict[str, Any]) -> None:
    text = json.dumps(summary, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "tmp/",
        "OPENAI" + "_API_KEY",
        "auth" + ".json",
        "sessions/",
        "raw_simulator_message",
        "raw" + "_runner_log_path",
        "local" + "_artifact_path",
        "hidden_tests",
        "expected_solutions",
        "benchmark_answer_keys",
    ]
    leaked = [needle for needle in forbidden if needle in text]
    assert not leaked, leaked


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="active-user-pilot-append-") as tmp:
        registry_path, runtime, pilot_path = write_fixture(Path(tmp))
        index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"

        args = [
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "history",
            "append-active-user-assisted-pilot",
            "--goal-id",
            GOAL_ID,
            "--active-user-pilot-json",
            str(pilot_path),
            "--delivery-batch-scale",
            "implementation",
            "--delivery-outcome",
            "primary_goal_outcome",
            "--no-global-sync",
        ]

        dry_run = run_cli(args)
        assert dry_run["ok"], dry_run
        assert dry_run["dry_run"] is True, dry_run
        assert dry_run["appended"] is False, dry_run
        assert not index_path.exists(), index_path
        assert_no_private_surface(dry_run["active_user_assisted_pilot"])

        appended = run_cli([*args, "--execute"])
        assert appended["ok"], appended
        assert appended["dry_run"] is False, appended
        assert appended["appended"] is True, appended
        assert index_path.exists(), index_path
        assert_no_private_surface(appended["active_user_assisted_pilot"])

        index_records = [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(index_records) == 1, index_records
        record = index_records[0]
        assert record["classification"] == PILOT_SCHEMA, record
        assert record["active_user_assisted_pilot"]["schema_version"] == PILOT_SCHEMA, record
        assert_no_private_surface(record["active_user_assisted_pilot"])

        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(runtime),
            scan_roots=[],
            limit=10,
        )
        assert status["ok"], status
        latest_runs = status["run_history"]["goals"][0]["latest_runs"]
        pilot_run = next(run for run in latest_runs if run.get("classification") == PILOT_SCHEMA)
        summary = pilot_run["active_user_assisted_pilot_summary"]
        assert summary["schema_version"] == PILOT_SCHEMA, summary
        assert summary["pilot_id"] == "train-fasttext-active-user-assisted-pilot-v0", summary
        assert summary["benchmark_id"] == "terminal-bench@2.0", summary
        assert summary["task_id"] == "train-fasttext", summary

        trigger = summary["trigger"]
        assert trigger["both_autonomous_modes_failed"] is True, trigger
        assert trigger["failed_autonomous_mode_count"] == 2, trigger
        assert trigger["failed_autonomous_modes"] == ["hardened_codex_baseline", "codex_loopx"], trigger
        assert trigger["assisted_score_kind"] == "not_run", trigger

        operator = summary["operator_simulator_run"]
        assert operator["schema_version"] == RUN_SCHEMA, operator
        assert operator["setting"] == "deterministic_scripted_user", operator
        assert operator["model_family"] == "scripted", operator
        assert operator["intervention_count"] == 2, operator
        assert operator["proactive_intervention_count"] == 2, operator
        assert operator["no_oracle_audit_passed"] is True, operator
        assert operator["official_task_score_kind"] == "not_run", operator
        assert operator["simulator_induced_error_count"] == 0, operator
        assert operator["frequency_budget_satisfied"] is True, operator
        assert operator["side_effect_audit_passed"] is True, operator

        boundary = summary["claim_boundary"]
        assert boundary["official_score_claim_allowed"] is False, boundary
        assert boundary["assisted_collaboration_claim_allowed"] is True, boundary
        assert boundary["leaderboard_claim_allowed"] is False, boundary

        decision = summary["next_run_decision"]
        assert decision["decision"] == "eligible_for_private_no_upload_assisted_treatment", decision
        assert decision["requires_real_runner_approval"] is True, decision
        assert decision["keep_official_scores_separate"] is True, decision
        assert_no_private_surface(summary)

        print(
            "active-user-assisted-pilot-append-cli-smoke ok "
            f"task={summary['task_id']} "
            f"failed_modes={trigger['failed_autonomous_mode_count']} "
            f"proactive={operator['proactive_intervention_count']} "
            f"official={operator['official_task_score_kind']}"
        )


if __name__ == "__main__":
    main()
