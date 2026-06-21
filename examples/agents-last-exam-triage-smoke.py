#!/usr/bin/env python3
"""Smoke-test the Agents' Last Exam benchmark triage note."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import build_agents_last_exam_result_benchmark_report  # noqa: E402
from loopx.status import (  # noqa: E402
    benchmark_experiment_report_readiness_note,
    compact_benchmark_experiment_report,
)

TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "agents-last-exam-triage-v0.md"
README = TOPIC_DIR / "README.md"
ROADMAP = TOPIC_DIR / "roadmap.md"

SCHEMA = "agents_last_exam_triage_v0"
BENCHMARK_ID = "agents-last-exam"
ARXIV_ID = "2606.05405"
XHS_NOTE_ID = "6a29525a0000000022023914"
GOAL_ID = "agents-last-exam-result-append-cli-fixture"

REQUIRED_DOC_SNIPPETS = [
    "Agents' Last Exam Triage V0",
    "http://xhslink.com/o/1tiETi329bL",
    XHS_NOTE_ID,
    "https://arxiv.org/abs/2606.05405",
    "https://github.com/rdi-berkeley/agents-last-exam",
    "Terminal-Bench",
    "fix-code-vulnerability",
    "python3 examples/agents-last-exam-triage-smoke.py",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "sk-" + "example",
    "SHOULD_NOT_APPEAR",
    "private-output-marker",
]


def triage_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "source_links": {
            "xiaohongshu_note_id": XHS_NOTE_ID,
            "arxiv_id": ARXIV_ID,
            "github_repo": "rdi-berkeley/agents-last-exam",
        },
        "positioning": {
            "long_horizon": True,
            "economically_valuable_workflows": True,
            "real_os_sandboxes": True,
            "gui_and_cli_surface": True,
            "verifiable_outcomes": True,
        },
        "planning_decision": {
            "add_to_backlog": True,
            "priority": "P1/P2_follow_on",
            "do_not_displace_terminal_bench_first_pair": True,
            "requires_adapter_dossier_before_execution": True,
            "first_current_pair": "terminal-bench@2.0/fix-code-vulnerability",
        },
        "stop_conditions": [
            "do_not_run_cloud_sandbox_or_paid_compute_from_heartbeat",
            "do_not_copy_hidden_references_or_raw_trajectories",
            "do_not_treat_social_summary_as_authoritative_without_primary_sources",
            "do_not_replace_current_terminal_bench_pair_before_result_or_blocker",
        ],
    }


def assert_public_safe(value: Any) -> None:
    text = json.dumps(value, sort_keys=True, ensure_ascii=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 10000, len(text)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    leaked = [snippet for snippet in FORBIDDEN_TEXT if snippet in text]
    assert not leaked, leaked
    assert "agents-last-exam-triage-v0.md" in readme, readme
    assert "Agents' Last Exam" in roadmap, roadmap


def assert_triage_payload(payload: dict[str, Any]) -> None:
    assert payload["schema_version"] == SCHEMA, payload
    assert payload["benchmark_id"] == BENCHMARK_ID, payload
    assert payload["source_links"]["arxiv_id"] == ARXIV_ID, payload
    assert payload["source_links"]["xiaohongshu_note_id"] == XHS_NOTE_ID, payload
    assert payload["positioning"]["long_horizon"] is True, payload
    decision = payload["planning_decision"]
    assert decision["add_to_backlog"] is True, decision
    assert decision["do_not_displace_terminal_bench_first_pair"] is True, decision
    assert decision["requires_adapter_dossier_before_execution"] is True, decision
    assert decision["first_current_pair"] == "terminal-bench@2.0/fix-code-vulnerability", decision
    assert "do_not_run_cloud_sandbox_or_paid_compute_from_heartbeat" in payload["stop_conditions"], payload
    assert_public_safe(payload)


def write_synthetic_ale_run(root: Path) -> Path:
    run_dir = root / "synthetic_ale_run"
    (run_dir / "origin_log" / "codex").mkdir(parents=True)
    (run_dir / "output").mkdir()
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "codex__openai-gpt-5-4__demo__hello__v0__20260611_000000",
                "agent_id": "codex_loopx",
                "model": "openai/gpt-5.4",
                "task_path": "demo/hello",
                "variant_index": 0,
                "status": "completed",
                "duration_s": 321.5,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "eval_result.json").write_text(
        json.dumps(
            {
                "eval_status": "passed",
                "score": 1.0,
                "eval_duration_s": 12.25,
                "error": None,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    events = [
        {
            "ts": "2026-06-11T00:00:00Z",
            "type": "unit_started",
            "data": {
                "private_path": "/" + "Users/bytedance/private",
                "task_prompt": "SHOULD_NOT_APPEAR",
            },
        },
        {"ts": "2026-06-11T00:01:00Z", "type": "agent_finished", "data": {}},
        {"ts": "2026-06-11T00:01:10Z", "type": "eval_finished", "data": {"score": 1.0}},
    ]
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in events) + "\n",
        encoding="utf-8",
    )
    (run_dir / "trajectory.json").write_text(
        json.dumps({"raw": "SHOULD_NOT_APPEAR"}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "output" / "answer.txt").write_text(
        "private-output-marker\n",
        encoding="utf-8",
    )
    return run_dir


def write_cli_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    run_dir = write_synthetic_ale_run(root)

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-11T00:00:00+00:00\n"
        "---\n\n"
        "# Agents Last Exam Result Append CLI Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Append compact ALE result report through the CLI.\n\n"
        "## Next Action\n\n"
        "- Inspect the appended compact ALE result projection.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-11T00:00:00+00:00",
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
    return registry_path, runtime, run_dir


def assert_ale_result_ingest_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-ale-ingest-") as tmp:
        run_dir = write_synthetic_ale_run(Path(tmp))
        report = build_agents_last_exam_result_benchmark_report(
            run_dir,
            report_id="agents-last-exam-synthetic-ingest-smoke",
        )

    assert report["schema_version"] == "benchmark_experiment_report_v0", report
    identity = report["experiment_identity"]
    assert identity["benchmark_id"] == BENCHMARK_ID, identity
    assert identity["task_slice"] == "demo__hello", identity
    official = report["official_score"]
    assert official["kind"] == "ale_eval_result", official
    assert official["native_score"] == 1.0, official
    assert official["submit_eligible"] is False, official
    assert official["leaderboard_evidence"] is False, official
    artifacts = report["reproducibility_artifacts"]
    assert artifacts["run_json_present"] is True, artifacts
    assert artifacts["eval_result_json_present"] is True, artifacts
    assert artifacts["events_jsonl_present"] is True, artifacts
    assert artifacts["raw_surface_content_recorded"] is False, artifacts
    assert artifacts["local_paths_recorded"] is False, artifacts
    assert artifacts["event_type_counts"]["unit_started"] == 1, artifacts
    assert "single_arm_no_delta" in report["negative_results"]["negative_evidence_layers"], report

    compact = compact_benchmark_experiment_report(report)
    assert compact is not None, report
    assert compact["experiment_identity"]["benchmark_id"] == BENCHMARK_ID, compact
    assert compact["official_score"]["kind"] == "ale_eval_result", compact
    note = benchmark_experiment_report_readiness_note(compact)
    assert note is not None, compact
    assert note["next_run_authorization"] == "fixture_only", note
    assert note["leaderboard_evidence"] is False, note
    assert_public_safe(report)
    assert_public_safe(compact)
    assert_public_safe(note)


def assert_ale_result_append_cli() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-ale-append-cli-") as tmp:
        registry_path, runtime, run_dir = write_cli_fixture(Path(tmp))
        index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
        args = [
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "history",
            "append-agents-last-exam-result-report",
            "--goal-id",
            GOAL_ID,
            "--agents-last-exam-run-dir",
            str(run_dir),
            "--report-id",
            "agents-last-exam-cli-append-smoke",
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
        assert dry_run["classification"] == "agents_last_exam_result_report_v0", dry_run
        assert dry_run["benchmark_report_source"]["raw_surfaces_excluded"] is True, dry_run
        assert_public_safe(dry_run["benchmark_experiment_report"])
        assert_public_safe(dry_run["benchmark_report_source"])

        appended = run_cli([*args, "--execute"])
        assert appended["ok"], appended
        assert appended["dry_run"] is False, appended
        assert appended["appended"] is True, appended
        assert index_path.exists(), index_path
        assert appended["classification"] == "agents_last_exam_result_report_v0", appended
        assert appended["benchmark_report_source"]["raw_surface_content_recorded"] is False, appended
        assert_public_safe(appended["benchmark_experiment_report"])
        assert_public_safe(appended["benchmark_report_source"])

        records = [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 1, records
        record = records[0]
        assert record["classification"] == "agents_last_exam_result_report_v0", record
        report = record["benchmark_experiment_report"]
        assert report["schema_version"] == "benchmark_experiment_report_v0", report
        assert report["experiment_identity"]["report_id"] == "agents-last-exam-cli-append-smoke", report
        assert report["experiment_identity"]["benchmark_id"] == BENCHMARK_ID, report
        assert report["official_score"]["submit_eligible"] is False, report
        assert report["official_score"]["leaderboard_evidence"] is False, report
        assert "single_arm_no_delta" in report["negative_results"]["negative_evidence_layers"], report
        assert_public_safe(report)


def main() -> None:
    assert_doc_contract()
    payload = triage_payload()
    assert_triage_payload(payload)
    assert_ale_result_ingest_contract()
    assert_ale_result_append_cli()
    print(
        "agents-last-exam-triage-smoke ok "
        f"benchmark={payload['benchmark_id']} "
        f"arxiv={payload['source_links']['arxiv_id']} "
        f"xhs={payload['source_links']['xiaohongshu_note_id']}"
    )


if __name__ == "__main__":
    main()
