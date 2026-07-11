#!/usr/bin/env python3
"""Contract smoke for bounded public issue-fix repository snapshots."""

from __future__ import annotations

import json
import os
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


def _fake_gh(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
changed = os.environ.get("FAKE_GH_VARIANT") == "changed"
if args[:2] == ["api", "graphql"]:
    query = next((item.split("=", 1)[1] for item in args if item.startswith("query=")), "")
    if "issues(states:OPEN)" in query:
        print(json.dumps({"data": {"repository": {
            "issues": {"totalCount": 13 if changed else 12},
            "pullRequests": {"totalCount": 5},
        }}}))
    else:
        nodes = [
            {"__typename": "Issue", "createdAt": "2026-07-02T00:00:00Z", "closedAt": None},
            {"__typename": "Issue", "createdAt": "2026-07-03T00:00:00Z", "closedAt": "2026-07-20T00:00:00Z"},
            {"__typename": "Issue", "createdAt": "2026-07-04T00:00:00Z", "closedAt": "2026-07-21T00:00:00Z"},
            {"__typename": "Issue", "createdAt": "2026-07-05T00:00:00Z", "closedAt": "2026-07-22T00:00:00Z"},
            {"__typename": "Issue", "createdAt": "2026-07-06T00:00:00Z", "closedAt": None},
            {"__typename": "PullRequest", "createdAt": "2026-07-07T00:00:00Z", "closedAt": "2026-07-25T00:00:00Z", "mergedAt": "2026-07-25T00:00:00Z"},
            {"__typename": "PullRequest", "createdAt": "2026-07-08T00:00:00Z", "closedAt": "2026-07-26T00:00:00Z", "mergedAt": "2026-07-26T00:00:00Z"},
            {"__typename": "PullRequest", "createdAt": "2026-07-09T00:00:00Z", "closedAt": "2026-07-27T00:00:00Z", "mergedAt": None},
            {"__typename": "PullRequest", "createdAt": "2026-07-10T00:00:00Z", "closedAt": None, "mergedAt": None},
        ]
        if changed:
            nodes.append({"__typename": "Issue", "createdAt": "2026-07-11T00:00:00Z", "closedAt": None})
        print(json.dumps([{"data": {"search": {"nodes": nodes}}}]))
elif args[:2] == ["issue", "view"]:
    number = int(args[2])
    closed = number == 42
    print(json.dumps({
        "number": number,
        "state": "CLOSED" if closed else "OPEN",
        "url": f"https://github.com/public-fixture/widgets/issues/{number}",
        "closedAt": "2026-07-25T00:00:00Z" if closed else None,
        "updatedAt": "2026-07-25T00:00:00Z",
    }))
elif args[:2] == ["pr", "view"]:
    number = int(args[2])
    merged = number == 77
    print(json.dumps({
        "number": number,
        "state": "MERGED" if merged else "OPEN",
        "url": f"https://github.com/public-fixture/widgets/pull/{number}",
        "createdAt": f"2026-07-{number - 70:02d}T00:00:00Z",
        "updatedAt": "2026-07-25T00:00:00Z",
        "reviewDecision": "APPROVED" if merged else "REVIEW_REQUIRED",
        "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
    }))
else:
    raise SystemExit(2)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-snapshot-") as tmp:
        root = Path(tmp)
        fake_bin = root / "bin"
        fake_bin.mkdir()
        _fake_gh(fake_bin / "gh")
        baseline = root / "baseline.json"
        _write_json(
            baseline,
            {
                "schema_version": "issue_fix_repository_reporting_snapshot_v0",
                "repo": "public-fixture/widgets",
                "captured_at": "2026-07-01T00:00:00Z",
                "open_issues": 10,
                "open_pull_requests": 4,
            },
        )
        domain = root / ".loopx" / "domain-state" / "fixture-goal" / "issue_fix"
        _write_jsonl(
            domain / "feasibility.jsonl",
            [
                {
                    "observation": {
                        "repo": "public-fixture/widgets",
                        "issue_ref": "issues_42",
                    }
                },
                {
                    "observation": {
                        "repo": "public-fixture/widgets",
                        "issue_ref": "issues_43",
                    }
                },
            ],
        )
        _write_jsonl(
            domain / "pr-lifecycle.jsonl",
            [
                {
                    "observation": {
                        "repo": "public-fixture/widgets",
                        "pr_ref": "pull_77",
                    }
                },
                {
                    "observation": {
                        "repo": "public-fixture/widgets",
                        "pr_ref": "pull_78",
                    }
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
            "repository-snapshot",
            "--goal-id",
            "fixture-goal",
            "--project",
            str(root),
            "--repo",
            "public-fixture/widgets",
            "--repository-baseline-json",
            str(baseline),
            "--fetch-public-github",
            "--retain-material-snapshot",
            "--generated-at",
            "2026-08-01T00:00:00Z",
        ]
        env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}
        first = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        packet = json.loads(first.stdout)
        snapshot = packet["snapshot"]
        assert snapshot["open_issues"] == 12, packet
        assert snapshot["open_pull_requests"] == 5, packet
        assert snapshot["flow_since_baseline"]["issues_closed"] == 3, packet
        assert len(snapshot["issue_states"]) == 2, packet
        assert len(snapshot["pull_request_states"]) == 2, packet
        assert packet["retention"]["write_performed"] is True, packet
        assert packet["raw_provider_payload_captured"] is False, packet
        assert packet["credentials_captured"] is False, packet
        assert packet["local_paths_captured"] is False, packet

        second = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        second_packet = json.loads(second.stdout)
        assert second_packet["retention"]["write_performed"] is False, second_packet

        changed = subprocess.run(
            command,
            cwd=ROOT,
            env={**env, "FAKE_GH_VARIANT": "changed"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        changed_packet = json.loads(changed.stdout)
        assert changed_packet["snapshot"]["open_issues"] == 13, changed_packet
        assert changed_packet["retention"]["write_performed"] is True, changed_packet
        ledger = domain / "repository-snapshots.jsonl"
        rows = [json.loads(line) for line in ledger.read_text().splitlines()]
        assert len(rows) == 1, rows
        assert rows[0]["snapshot"]["open_issues"] == 13, rows
        serialized = json.dumps(changed_packet, sort_keys=True)
        assert str(root) not in serialized, serialized

    print("issue-fix repository snapshot smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
