#!/usr/bin/env python3
"""Contract smoke for evidence-backed issue-fix supplemental metrics."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value) + "\n" for value in values),
        encoding="utf-8",
    )


def main() -> int:
    repo = "public-fixture/widgets"
    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-supplement-") as tmp:
        root = Path(tmp)
        runtime = root / "runtime"
        registry = root / "registry.json"
        _write_json(
            registry,
            {
                "schema_version": "loopx_registry_v0",
                "common_runtime_root": str(runtime),
                "goals": [{"id": "fixture-goal", "repo": str(root)}],
            },
        )
        _write_jsonl(
            runtime / "goals" / "fixture-goal" / "runs" / "index.jsonl",
            [
                {
                    "generated_at": "2026-07-02T00:00:00Z",
                    "classification": "operator_gate_approved",
                    "operator_gate": {
                        "recorded_at": "2026-07-02T00:00:00Z",
                        "gate": "publish_fix_pr",
                        "decision": "approve",
                    },
                },
                {
                    "generated_at": "2026-07-11T00:00:00Z",
                    "classification": "state_refreshed",
                    "human_reward": {
                        "recorded_at": "2026-07-11T00:01:00Z",
                        "decision": "correct_route",
                        "reward": "negative",
                        "lesson": {
                            "schema_version": "human_reward_lesson_v0",
                            "kind": "route",
                            "summary": "Keep delivery on the selected issue.",
                        },
                    },
                },
                {
                    "generated_at": "2026-07-12T00:00:00Z",
                    "classification": "state_refreshed",
                    "human_reward": {
                        "recorded_at": "2026-07-12T00:01:00Z",
                        "decision": "continue",
                        "reward": "positive",
                    },
                },
            ],
        )
        domain = root / ".loopx" / "domain-state" / "fixture-goal" / "issue_fix"
        _write_jsonl(
            domain / "feasibility.jsonl",
            [
                {
                    "observation": {"repo": repo, "issue_ref": "issues_42"},
                    "decision": {"route": "fix_pr"},
                },
                {
                    "observation": {"repo": repo, "issue_ref": "issues_43"},
                    "decision": {"route": "fix_pr"},
                },
                {
                    "observation": {"repo": repo, "issue_ref": "issues_44"},
                    "decision": {"route": "triage_only"},
                },
            ],
        )
        _write_jsonl(
            domain / "pr-lifecycle.jsonl",
            [
                {
                    "generated_at": "2026-07-05T00:00:00Z",
                    "observation": {
                        "repo": repo,
                        "pr_ref": "pull_77",
                        "state": "MERGED",
                    },
                    "transition": {"decision": "no_followup"},
                },
                {
                    "generated_at": "2026-07-06T00:00:00Z",
                    "observation": {
                        "repo": repo,
                        "pr_ref": "pull_78",
                        "state": "CLOSED",
                    },
                    "transition": {"decision": "no_followup"},
                },
                {
                    "generated_at": "2026-07-07T00:00:00Z",
                    "observation": {
                        "repo": repo,
                        "pr_ref": "pull_79",
                        "state": "OPEN",
                    },
                    "transition": {"decision": "monitor_continuation"},
                    "first_push_ci": {
                        "schema_version": "issue_fix_first_push_ci_evidence_v0",
                        "pr_ref": "pull_79",
                        "status": "PASSING",
                        "observed_at": "2026-07-07T00:00:00Z",
                    },
                },
            ],
        )
        events = root / "events.json"
        _write_json(
            events,
            {
                "schema_version": "issue_fix_metrics_event_batch_v0",
                "events": [
                    {
                        "event_id": "human-1",
                        "event_type": "human_intervention",
                        "occurred_at": "2026-07-03T00:00:00Z",
                    },
                    {
                        "event_id": "human-2",
                        "event_type": "human_intervention",
                        "occurred_at": "2026-07-04T00:00:00Z",
                    },
                    {
                        "event_id": "ci-77",
                        "event_type": "first_push_ci",
                        "occurred_at": "2026-07-05T00:00:00Z",
                        "pr_ref": "pull_77",
                        "status": "PASSING",
                    },
                    {
                        "event_id": "ci-78",
                        "event_type": "first_push_ci",
                        "occurred_at": "2026-07-06T00:00:00Z",
                        "pr_ref": "pull_78",
                        "status": "FAILING",
                    },
                    {
                        "event_id": "gap-found",
                        "event_type": "capability_gap",
                        "occurred_at": "2026-07-07T00:00:00Z",
                        "gap_id": "projection-gap",
                        "status": "found",
                    },
                    {
                        "event_id": "gap-fixed",
                        "event_type": "capability_gap",
                        "occurred_at": "2026-07-08T00:00:00Z",
                        "gap_id": "projection-gap",
                        "status": "fixed",
                    },
                    {
                        "event_id": "gap-verified",
                        "event_type": "capability_gap",
                        "occurred_at": "2026-07-09T00:00:00Z",
                        "gap_id": "projection-gap",
                        "status": "real_callsite_verified",
                    },
                    {
                        "event_id": "comment-1",
                        "event_type": "useful_public_comment",
                        "occurred_at": "2026-07-10T00:00:00Z",
                    },
                    {
                        "event_id": "outside-period",
                        "event_type": "human_intervention",
                        "occurred_at": "2026-06-01T00:00:00Z",
                    },
                ],
            },
        )
        memory = root / "memory.json"
        _write_json(
            memory,
            {
                "schema_version": "issue_fix_repository_memory_read_result_v0",
                "results": [
                    {
                        "verification_status": "confirmed",
                        "decision_influence": ["patch"],
                        "patch_influence_allowed": True,
                    },
                    {
                        "verification_status": "unverified",
                        "patch_influence_allowed": False,
                    },
                ],
            },
        )
        command = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
            "--format",
            "json",
            "issue-fix",
            "metrics-supplement",
            "--goal-id",
            "fixture-goal",
            "--project",
            str(root),
            "--repo",
            repo,
            "--period-start",
            "2026-07-01T00:00:00Z",
            "--period-end",
            "2026-08-01T00:00:00Z",
            "--event-json",
            str(events),
            "--repository-memory-json",
            str(memory),
            "--generated-at",
            "2026-08-01T00:01:00Z",
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
        counts = packet["supplement"]["counts"]
        assert counts["issues_screened"] == 3, packet
        assert counts["triage_outcomes"] == 1, packet
        assert counts["automatic_terminal_closeouts"] == 2, packet
        assert counts["human_interventions"] == 2, packet
        assert counts["first_push_ci_passed"] == 2, packet
        assert counts["first_push_ci_total"] == 3, packet
        assert packet["supplement"]["coverage"]["first_push_ci"] == {
            "eligible_prs": 3,
            "observed_prs": 3,
            "complete": True,
        }, packet
        assert counts["loopx_capability_gaps_found"] == 1, packet
        assert counts["loopx_capability_gaps_fixed"] == 1, packet
        assert counts["loopx_capability_gaps_real_callsite_verified"] == 1, packet
        assert counts["memory_retrievals"] == 2, packet
        assert counts["memory_verified_decision_influence"] == 1, packet
        assert counts["memory_verified_patch_influence"] == 1, packet
        assert counts["memory_stale_results"] == 0, packet
        assert counts["useful_public_comments"] == 1, packet
        assert "duplicate_external_writes" not in packet["missing_fields"], packet
        serialized = json.dumps(packet, sort_keys=True)
        assert str(root) not in serialized, serialized
        for field in (
            "raw_event_payload_captured",
            "raw_memory_captured",
            "credentials_captured",
            "local_paths_captured",
        ):
            assert packet[field] is False, packet

        event_arg_index = command.index("--event-json")
        incomplete_command = command[:event_arg_index] + command[event_arg_index + 2 :]
        incomplete_result = subprocess.run(
            incomplete_command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        incomplete = json.loads(incomplete_result.stdout)
        assert incomplete["supplement"]["coverage"]["first_push_ci"] == {
            "eligible_prs": 3,
            "observed_prs": 1,
            "complete": False,
        }, incomplete
        assert "first_push_ci_total" in incomplete["missing_fields"], incomplete
        assert "first_push_ci_passed" in incomplete["missing_fields"], incomplete
        assert "human_interventions" in incomplete["missing_fields"], incomplete
        assert incomplete["supplement"]["coverage"]["human_intervention"] == {
            "source": "loopx_compact_run_index",
            "observed_events": 2,
            "complete": False,
        }, incomplete

        history_command = incomplete_command + [
            "--human-intervention-coverage-start",
            "2026-07-01T00:00:00Z",
        ]
        history_result = subprocess.run(
            history_command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        history = json.loads(history_result.stdout)
        assert history["supplement"]["counts"]["human_interventions"] == 2, history
        assert history["supplement"]["coverage"]["human_intervention"] == {
            "source": "loopx_compact_run_index",
            "observed_events": 2,
            "complete": True,
            "complete_from": "2026-07-01T00:00:00Z",
        }, history
        assert history["source_summary"]["run_history_rows"] == 3, history

    print("issue-fix metrics supplement smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
