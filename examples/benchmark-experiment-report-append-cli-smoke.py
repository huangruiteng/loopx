#!/usr/bin/env python3
"""Smoke-test appending compact benchmark_experiment_report_v0 events."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.cli import review_packet_handoff_only_payload  # noqa: E402
from goal_harness.review_packet import build_review_packet  # noqa: E402
from goal_harness.status import collect_status  # noqa: E402


GOAL_ID = "benchmark-report-append-cli-fixture"
REPORT_MODULE_PATH = REPO_ROOT / "examples" / "benchmark-experiment-report-template-smoke.py"


def load_report_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("benchmark_experiment_report_template_smoke", REPORT_MODULE_PATH)
    assert spec is not None and spec.loader is not None, REPORT_MODULE_PATH
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def benchmark_report_event() -> dict[str, Any]:
    module = load_report_module()
    note = module.decision_note_payload(module.comparison_summary_payload())
    readiness_note = module.decision_note_payload(module.readiness_summary_payload())
    failure_note = module.decision_note_payload(module.failure_summary_payload())
    report = module.report_payload(note, readiness_note, failure_note)
    report["raw_log_path"] = "/" + "Users/example/private/raw.log"
    report["local_artifact_path"] = "/" + "tmp/private/artifact.json"
    report["negative_results"]["failed_hypotheses"][0]["private_trace_path"] = "/" + "Users/example/private/session.jsonl"
    return report


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".goal-harness" / "registry.json"
    report_path = root / "benchmark_report.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-07T00:00:00+00:00\n"
        "---\n\n"
        "# Benchmark Report Append CLI Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Append compact benchmark_experiment_report_v0 through the CLI.\n\n"
        "## Next Action\n\n"
        "- Inspect the appended benchmark report projection.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-07T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "benchmark-report-projection",
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
    write_json(report_path, benchmark_report_event())
    return registry_path, runtime, report_path


def run_cli(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "goal_harness.cli", *args],
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
        "auth.json",
        "sessions/",
        "raw_log_path",
        "local_artifact_path",
        "private_trace_path",
        "lark" + "office",
        "fei" + "shu.cn",
    ]
    leaked = [needle for needle in forbidden if needle in text]
    assert not leaked, leaked


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-report-append-") as tmp:
        registry_path, runtime, report_path = write_fixture(Path(tmp))
        index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"

        args = [
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "history",
            "append-benchmark-report",
            "--goal-id",
            GOAL_ID,
            "--benchmark-report-json",
            str(report_path),
            "--delivery-batch-scale",
            "implementation",
            "--delivery-outcome",
            "primary_goal_outcome",
        ]

        dry_run = run_cli(args)
        assert dry_run["ok"], dry_run
        assert dry_run["dry_run"] is True, dry_run
        assert dry_run["appended"] is False, dry_run
        assert not index_path.exists(), index_path
        assert_no_private_surface(dry_run["benchmark_experiment_report"])

        appended = run_cli([*args, "--execute"])
        assert appended["ok"], appended
        assert appended["dry_run"] is False, appended
        assert appended["appended"] is True, appended
        assert index_path.exists(), index_path
        assert_no_private_surface(appended["benchmark_experiment_report"])

        index_records = [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(index_records) == 1, index_records
        record = index_records[0]
        assert record["classification"] == "benchmark_experiment_report_v0", record
        assert record["benchmark_experiment_report"]["schema_version"] == "benchmark_experiment_report_v0", record
        assert_no_private_surface(record["benchmark_experiment_report"])

        status = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(runtime),
            scan_roots=[],
            limit=10,
        )
        assert status["ok"], status
        latest_runs = status["run_history"]["goals"][0]["latest_runs"]
        report_run = next(run for run in latest_runs if run.get("classification") == "benchmark_experiment_report_v0")
        report_summary = report_run["benchmark_experiment_report_summary"]
        assert report_summary["schema_version"] == "benchmark_experiment_report_v0", report_summary
        identity = report_summary["experiment_identity"]
        assert identity["report_id"] == "mini-control-plane-repair-report-v0", report_summary
        official = report_summary["official_score"]
        assert official["delta"] == 0.0, official
        assert official["submit_eligible"] is False, official
        assert official["leaderboard_evidence"] is False, official
        negative = report_summary["negative_results"]
        assert negative["null_official_delta"] is True, negative
        assert set(negative["negative_evidence_layers"]) == {"readiness_only", "failure_analysis"}, negative
        next_decision = report_summary["next_decision"]
        assert next_decision["decision"] == "continue", next_decision
        assert next_decision["source_decision_note_schema"] == "benchmark_comparison_decision_note_v0", next_decision
        boundary = report_summary["claim_boundary"]
        assert "official leaderboard uplift" in boundary["must_not_claim"], boundary
        assert_no_private_surface(report_summary)

        readiness_note = report_run["benchmark_experiment_report_readiness_note"]
        assert readiness_note["schema_version"] == "benchmark_experiment_report_readiness_note_v0", readiness_note
        assert readiness_note["source_schema_version"] == "benchmark_experiment_report_v0", readiness_note
        assert readiness_note["readiness"] == "negative_or_control_plane_only", readiness_note
        assert readiness_note["next_run_authorization"] == "fixture_only", readiness_note
        assert readiness_note["report_decision"] == "continue", readiness_note
        assert readiness_note["report_id"] == "mini-control-plane-repair-report-v0", readiness_note
        assert readiness_note["task_slice"] == "mini_control_plane_repair_v0", readiness_note
        assert readiness_note["submit_eligible"] is False, readiness_note
        assert readiness_note["leaderboard_evidence"] is False, readiness_note
        assert readiness_note["simulator_enabled"] is False, readiness_note
        assert readiness_note["null_official_delta"] is True, readiness_note
        assert set(readiness_note["negative_evidence_layers"]) == {"readiness_only", "failure_analysis"}, readiness_note
        assert "official leaderboard uplift" in readiness_note["must_not_claim"], readiness_note
        assert_no_private_surface(readiness_note)

        replay_decision = report_run["benchmark_experiment_report_replay_decision"]
        assert replay_decision["schema_version"] == "benchmark_experiment_report_replay_decision_v0", replay_decision
        assert replay_decision["source_schema_version"] == "benchmark_experiment_report_readiness_note_v0", replay_decision
        assert replay_decision["readiness"] == "negative_or_control_plane_only", replay_decision
        assert replay_decision["authorization"] == "fixture_only", replay_decision
        assert replay_decision["replay_decision"] == "continue_fixture_replay", replay_decision
        assert replay_decision["next_run_mode"] == "fixture_replay", replay_decision
        assert replay_decision["surface"] == "status_review_packet_only", replay_decision
        assert replay_decision["report_id"] == "mini-control-plane-repair-report-v0", replay_decision
        assert replay_decision["task_slice"] == "mini_control_plane_repair_v0", replay_decision
        assert set(replay_decision["negative_evidence_layers"]) == {"readiness_only", "failure_analysis"}, replay_decision
        assert "official leaderboard uplift" in replay_decision["must_not_claim"], replay_decision
        assert_no_private_surface(replay_decision)

        packet = build_review_packet(status, goal_id=GOAL_ID)
        handoff = packet["project_agent_handoff"]
        assert "report=mini-control-plane-repair-report-v0" in handoff, handoff
        assert "report_decision=continue" in handoff, handoff
        assert "readiness=negative_or_control_plane_only" in handoff, handoff
        assert "next_run=fixture_only" in handoff, handoff
        assert "replay=continue_fixture_replay" in handoff, handoff
        assert "mode=fixture_replay" in handoff, handoff
        assert "chain_map=benchmark-report-chain-map-v0.md" in handoff, handoff
        assert "negative_layers=readiness_only,failure_analysis" in handoff, handoff
        assert_no_private_surface({"handoff": handoff})

        handoff_only = review_packet_handoff_only_payload(packet)
        chain_handoff = handoff_only["benchmark_report_chain_handoff"]
        assert chain_handoff["schema_version"] == "benchmark_report_chain_handoff_v0", chain_handoff
        assert chain_handoff["surface"] == "status_review_packet_only", chain_handoff
        assert chain_handoff["chain_map"] == "benchmark-report-chain-map-v0.md", chain_handoff
        assert chain_handoff["report_id"] == "mini-control-plane-repair-report-v0", chain_handoff
        assert chain_handoff["task_slice"] == "mini_control_plane_repair_v0", chain_handoff
        assert chain_handoff["report_decision"] == "continue", chain_handoff
        assert chain_handoff["readiness"] == "negative_or_control_plane_only", chain_handoff
        assert chain_handoff["authorization"] == "fixture_only", chain_handoff
        assert chain_handoff["replay_decision"] == "continue_fixture_replay", chain_handoff
        assert chain_handoff["next_run_mode"] == "fixture_replay", chain_handoff
        assert set(chain_handoff["negative_evidence_layers"]) == {"readiness_only", "failure_analysis"}, chain_handoff
        assert "official leaderboard uplift" in chain_handoff["must_not_claim"], chain_handoff
        assert chain_handoff["source_run"]["classification"] == "benchmark_experiment_report_v0", chain_handoff
        assert_no_private_surface(chain_handoff)

        cli_handoff_only = run_cli(
            [
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "review-packet",
                "--goal-id",
                GOAL_ID,
                "--handoff-only",
                "--format",
                "json",
            ]
        )
        cli_chain_handoff = cli_handoff_only["benchmark_report_chain_handoff"]
        assert cli_chain_handoff == chain_handoff, cli_handoff_only
        assert "benchmark_report_chain_handoff" in cli_handoff_only, cli_handoff_only
        assert "handoff_followthrough_summary" not in cli_handoff_only, cli_handoff_only
        assert_no_private_surface(cli_handoff_only)

    print("benchmark-experiment-report-append-cli-smoke ok")


if __name__ == "__main__":
    main()
