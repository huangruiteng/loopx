#!/usr/bin/env python3
"""Contract smoke for provider-neutral issue-fix monthly metrics projection."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    repo = "public-fixture/widgets"
    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-metrics-") as tmp:
        root = Path(tmp)
        baseline = root / "baseline.json"
        current = root / "current.json"
        supplement = root / "supplement.json"
        feasibility = root / "feasibility.jsonl"
        lifecycle = root / "pr-lifecycle.jsonl"

        _write_json(
            baseline,
            {
                "schema_version": "issue_fix_repository_reporting_snapshot_v0",
                "repo": repo,
                "captured_at": "2026-07-01T00:00:00Z",
                "open_issues": 10,
                "open_pull_requests": 4,
            },
        )
        _write_json(
            current,
            {
                "schema_version": "issue_fix_repository_reporting_snapshot_v0",
                "repo": repo,
                "captured_at": "2026-08-01T00:00:00Z",
                "open_issues": 12,
                "open_pull_requests": 5,
                "flow_since_baseline": {
                    "issues_opened": 5,
                    "issues_closed": 3,
                    "pull_requests_opened": 4,
                    "pull_requests_closed": 3,
                    "pull_requests_merged": 2,
                },
                "issue_states": [
                    {"issue_ref": "issues_42", "state": "CLOSED"},
                    {"issue_ref": "issues_43", "state": "OPEN"},
                ],
                "pull_request_states": [
                    {
                        "pr_ref": "pull_77",
                        "state": "MERGED",
                        "ci": "PASSING",
                        "review": "APPROVED",
                    },
                    {
                        "pr_ref": "pull_78",
                        "state": "OPEN",
                        "ci": "PASSING",
                        "review": "REVIEW_REQUIRED",
                    },
                ],
            },
        )
        _write_json(
            supplement,
            {
                "schema_version": "issue_fix_metrics_supplement_v0",
                "counts": {
                    "human_interventions": 1,
                    "first_push_ci_passed": 1,
                    "first_push_ci_total": 2,
                    "loopx_capability_gaps_found": 2,
                    "memory_retrievals": 3,
                },
            },
        )
        _write_jsonl(
            feasibility,
            [
                {
                    "generated_at": "2026-07-02T00:00:00Z",
                    "observation": {"repo": repo, "issue_ref": "issues_42"},
                    "decision": {"route": "fix_pr"},
                    "delivery_evidence": {"validation_status": "passed"},
                },
                {
                    "generated_at": "2026-07-03T00:00:00Z",
                    "observation": {"repo": repo, "issue_ref": "issues_43"},
                    "decision": {"route": "fix_pr"},
                    "delivery_evidence": {"validation_status": "passed"},
                },
            ],
        )
        _write_jsonl(
            lifecycle,
            [
                {
                    "generated_at": "2026-07-04T00:00:00Z",
                    "observation": {
                        "repo": repo,
                        "pr_ref": "pull_77",
                        "issue_ref": "issues_42",
                        "permalink": (
                            "https://github.com/public-fixture/widgets/pull/77"
                        ),
                        "state": "MERGED",
                        "checks": {"aggregate": "PASSING"},
                        "review_decision": "APPROVED",
                    },
                    "reviewer_notification_receipts": ["sha256:" + "a" * 64],
                },
                {
                    "generated_at": "2026-07-05T00:00:00Z",
                    "observation": {
                        "repo": repo,
                        "pr_ref": "pull_78",
                        "issue_ref": "issues_43",
                        "permalink": (
                            "https://github.com/public-fixture/widgets/pull/78"
                        ),
                        "state": "OPEN",
                        "checks": {"aggregate": "PASSING"},
                        "review_decision": "REVIEW_REQUIRED",
                    },
                },
            ],
        )

        command = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "issue-fix",
            "metrics",
            "--goal-id",
            "fixture-goal",
            "--project",
            str(root),
            "--repo",
            repo,
            "--repository-baseline-json",
            str(baseline),
            "--repository-current-json",
            str(current),
            "--supplement-json",
            str(supplement),
            "--feasibility-ledger",
            str(feasibility),
            "--pr-lifecycle-ledger",
            str(lifecycle),
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
        assert packet["ok"] is True, packet
        assert packet["baseline"]["agent_output"]["pull_requests"] == 0, packet
        output = packet["current"]["agent_output"]
        assert output["pull_requests"] == 2, packet
        assert output["merged_pull_requests"] == 1, packet
        assert output["linked_issues_closed"] == 1, packet
        assert output["pull_requests_refreshed_from_snapshot"] == 2, packet
        assert output["stale_lifecycle_rows_corrected_by_snapshot"] == 0, packet
        assert packet["delta"]["repository"]["open_issues"] == 2, packet
        assert (
            packet["ratios"]["pilot_share_of_repository_prs_opened"]["value"] == 0.5
        ), packet
        assert len(packet["output_inventory"]["pull_requests"]) == 2, packet
        serialized = json.dumps(packet, sort_keys=True)
        assert str(root) not in serialized, serialized
        assert packet["external_writes_performed"] is False, packet

        missing_current = json.loads(current.read_text(encoding="utf-8"))
        missing_current.pop("issue_states")
        missing_current.pop("pull_request_states")
        _write_json(current, missing_current)
        without_supplement = [
            value
            for value in command
            if value not in {"--supplement-json", str(supplement)}
        ]
        missing = subprocess.run(
            without_supplement,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        missing_packet = json.loads(missing.stdout)
        assert missing_packet["current"]["agent_output"]["linked_issues_closed"] is None
        missing_codes = {item["code"] for item in missing_packet["missing_data"]}
        assert "linked_issue_states_not_captured" in missing_codes, missing_packet
        assert "human_interventions_not_captured" in missing_codes, missing_packet

        bad_current = json.loads(current.read_text(encoding="utf-8"))
        bad_current["open_issues"] = 99
        _write_json(current, bad_current)
        bad = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert bad.returncode == 1, bad.stdout
        assert "does not reconcile" in json.loads(bad.stdout)["error"], bad.stdout

    print("issue-fix metrics projection smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
