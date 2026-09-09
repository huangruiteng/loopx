from __future__ import annotations

from pathlib import Path

import loopx.pr_review as pr_review_module

HEAD_1 = "a" * 40
HEAD_2 = "b" * 40


def _rows() -> list[dict[str, object]]:
    return [
        {
            "number": 1,
            "title": "one",
            "state": "OPEN",
            "headRefOid": HEAD_1,
            "updatedAt": "2026-08-12T00:00:00Z",
        },
        {
            "number": 2,
            "title": "two",
            "state": "OPEN",
            "headRefOid": HEAD_2,
            "updatedAt": "2026-08-12T00:00:00Z",
        },
    ]


def _fake_run_gh_json(args: list[str], *, cwd: Path | None = None):
    if args[0] == "pr" and args[1] == "list":
        return _rows()
    if args[0] == "pr" and args[1] == "view":
        number = args[2]
        checks = (
            [{"name": "build", "status": "IN_PROGRESS", "conclusion": ""}]
            if number == "2"
            else [
                {
                    "name": "pytest",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                },
                {
                    "name": "lint",
                    "status": "COMPLETED",
                    "conclusion": "FAILURE",
                },
            ]
        )
        return {
            "createdAt": "2026-08-11T00:00:00Z",
            "commits": [
                {
                    "authoredDate": "2026-08-12T00:00:00Z",
                    "committedDate": "2026-08-12T00:00:00Z",
                }
            ],
            "reviews": [],
            "statusCheckRollup": checks,
        }
    return {}


def test_pr_list_keeps_nested_details_in_bounded_per_pr_reads(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake(args: list[str], *, cwd: Path | None = None):
        calls.append(args)
        return _fake_run_gh_json(args, cwd=cwd)

    monkeypatch.setattr(pr_review_module, "_run_gh_json", fake)
    scan = pr_review_module.scan_github_pull_requests(
        repo="huangruiteng/loopx",
        limit=10,
        state_filter="open",
    )

    list_call = next(args for args in calls if args[0] == "pr" and args[1] == "list")
    json_fields = list_call[list_call.index("--json") + 1].split(",")
    assert "statusCheckRollup" not in json_fields
    assert "createdAt" in json_fields
    assert {"commits", "reviews"}.isdisjoint(json_fields)

    rows = scan["pull_requests"]
    assert len(rows) == 2
    assert rows[0]["statusCheckRollup"] == [
        {"name": "pytest", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "lint", "status": "COMPLETED", "conclusion": "FAILURE"},
    ]
    assert rows[1]["statusCheckRollup"] == [
        {"name": "build", "status": "IN_PROGRESS", "conclusion": ""},
    ]
    detail_calls = [args for args in calls if args[:2] == ["pr", "view"]]
    assert [args[2] for args in detail_calls] == ["1", "2"]
    assert all(
        args[args.index("--json") + 1] == "createdAt,commits,reviews,statusCheckRollup"
        for args in detail_calls
    )
    assert rows[0]["commits"][0]["committedDate"] == "2026-08-12T00:00:00Z"
    assert rows[0]["reviews"] == []


def test_pr_list_failed_check_lookup_leaves_rollup_absent(monkeypatch) -> None:
    def fake(args: list[str], *, cwd: Path | None = None):
        if args[0] == "pr" and args[1] == "list":
            return _rows()
        raise RuntimeError("detail unavailable")

    monkeypatch.setattr(pr_review_module, "_run_gh_json", fake)
    scan = pr_review_module.scan_github_pull_requests(
        repo="huangruiteng/loopx",
        limit=10,
        state_filter="open",
    )
    rows = scan["pull_requests"]
    assert all("statusCheckRollup" not in row for row in rows)
    assert scan["complete"] is False
    assert scan["states"][0]["detail_read_failures"] == 2
    assert scan["states"][0]["source_read_valid"] is False


def test_security_policy_keeps_public_entry_classification_after_move() -> None:
    assert pr_review_module._file_area(".github/SECURITY.md") == (
        "public_entry_or_policy"
    )


def test_agent_instruction_files_are_behavior_bearing_surfaces() -> None:
    assert pr_review_module._file_area("skills/loopx-project/SKILL.md") == (
        "agent_instruction_surface"
    )
    assert pr_review_module._file_area(".github/copilot.instructions.md") == (
        "agent_instruction_surface"
    )
    assert pr_review_module._file_area("AGENTS.md") == "agent_instruction_surface"


def test_agent_instruction_surface_gets_behavior_risk_and_review_depth() -> None:
    files = [
        {
            "path": "skills/loopx-project/SKILL.md",
            "area": "agent_instruction_surface",
            "additions": 20,
            "deletions": 2,
        }
    ]

    hint = pr_review_module._metadata_risk_hint({}, files, {"total": 1})
    analysis = pr_review_module._main_regression_analysis({}, files)

    assert hint["level"] == "medium"
    assert pr_review_module._review_depth(files) == "agent_behavior_review"
    assert analysis["risk_level"] == "medium"
    assert any(
        "Automatically loaded agent instructions" in item
        for item in analysis["potential_regressions"]
    )
    assert any(
        "pre-change, disabled, and enabled instruction surfaces" in item
        for item in analysis["verification_focus"]
    )


def _queue_pr(
    number: int,
    *,
    author: str,
    ready_at: str,
    updated_at: str,
    review_decision: str = "REVIEW_REQUIRED",
    reviews: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    head = f"{number:040x}"
    return {
        "number": number,
        "title": f"PR {number}",
        "url": f"https://github.com/owner/repo/pull/{number}",
        "state": "OPEN",
        "author": {"login": author},
        "createdAt": ready_at,
        "updatedAt": updated_at,
        "headRefOid": head,
        "isDraft": False,
        "reviewDecision": review_decision,
        "mergeStateStatus": "CLEAN",
        "files": [{"path": "src/runtime.py", "additions": 1, "deletions": 0}],
        "commits": [
            {
                "authoredDate": ready_at,
                "committedDate": ready_at,
                "messageHeadline": "change runtime",
            }
        ],
        "reviews": reviews or [],
    }


def _full_review_body(
    head: str,
    *,
    verdict: str = "APPROVE",
    author_fallback: bool = False,
) -> str:
    fallback = ""
    if author_fallback:
        fallback = (
            "Approval conclusion (author-owned PR; GitHub blocks formal self-approval)"
            if verdict == "APPROVE"
            else "Request changes conclusion (author-owned PR; GitHub blocks formal self-review)"
        ) + "\n\n"
    return (
        f"{fallback}## 动机\n完整动机。\n\n"
        "## 改动思路\n完整思路。\n\n"
        "## 具体改动\n完整改动。\n\n"
        "## 对主干的风险\n完整风险。\n\n"
        "## 我的整体评价\n整体通过。\n\n"
        f"**English verdict:** {verdict} at exact head {head}."
    )


def test_queue_prioritizes_authenticated_developer_owned_heads(monkeypatch) -> None:
    monkeypatch.setattr(pr_review_module, "_now_iso", lambda: "2026-08-18T12:00:00Z")
    rows = [
        _queue_pr(
            11,
            author="community",
            ready_at="2026-08-18T07:00:00Z",
            updated_at="2026-08-18T11:59:00Z",
        ),
        _queue_pr(
            12,
            author="maintainer",
            ready_at="2026-08-17T06:00:00Z",
            updated_at="2026-08-18T11:58:00Z",
        ),
        _queue_pr(
            13,
            author="maintainer",
            ready_at="2026-08-18T10:00:00Z",
            updated_at="2026-08-18T11:57:00Z",
        ),
    ]

    packet = pr_review_module.build_pr_review_packet(
        pull_requests=rows,
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )

    assert [item["number"] for item in packet["pull_requests"]] == [12, 13, 11]
    assert [item["scheduling_lane"] for item in packet["pull_requests"]] == [
        "authenticated_developer_owned",
        "authenticated_developer_owned",
        "composite_remaining",
    ]
    assert [item["scheduling_tier"] for item in packet["pull_requests"]] == [
        0,
        0,
        2,
    ]
    assert packet["pull_requests"][0]["review_ready_at"] == "2026-08-17T06:00:00Z"
    policy = packet["scheduling_policy"]
    assert policy["schema_version"] == "pull_request_review_scheduling_policy_v0"
    assert policy["authenticated_developer_login"] == "maintainer"
    assert policy["owner_first_active"] is True
    assert [item["id"] for item in policy["ordered_tiers"][:3]] == [
        "authenticated_developer_owned",
        "community_feedback_and_aged_backlog",
        "composite_remaining",
    ]
    assert "one-off author filters" in policy["manual_override_rule"]

    overdue = pr_review_module.build_pr_review_packet(
        pull_requests=[
            rows[0],
            _queue_pr(
                14,
                author="maintainer",
                ready_at="2026-08-16T10:00:00Z",
                updated_at="2026-08-18T11:56:00Z",
            ),
        ],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )
    assert overdue["pull_requests"][0]["number"] == 14
    assert (
        overdue["pull_requests"][0]["scheduling_lane"]
        == "authenticated_developer_owned"
    )


def test_community_feedback_and_aged_backlog_precede_remaining_queue(
    monkeypatch,
) -> None:
    monkeypatch.setattr(pr_review_module, "_now_iso", lambda: "2026-08-18T12:00:00Z")
    feedback = _queue_pr(
        21,
        author="community",
        ready_at="2026-08-18T10:00:00Z",
        updated_at="2026-08-18T11:00:00Z",
        review_decision="CHANGES_REQUESTED",
        reviews=[
            {
                "author": {"login": "maintainer"},
                "body": "Please repair the exact-head behavior.",
                "commit": {"oid": "f" * 40},
                "state": "CHANGES_REQUESTED",
                "submittedAt": "2026-08-18T09:00:00Z",
            }
        ],
    )
    aged = _queue_pr(
        22,
        author="community",
        ready_at="2026-08-17T06:00:00Z",
        updated_at="2026-08-18T11:01:00Z",
    )
    ordinary = _queue_pr(
        23,
        author="community",
        ready_at="2026-08-18T07:00:00Z",
        updated_at="2026-08-18T11:02:00Z",
    )

    packet = pr_review_module.build_pr_review_packet(
        pull_requests=[ordinary, feedback, aged],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )

    assert [item["number"] for item in packet["pull_requests"]] == [22, 21, 23]
    assert [item["scheduling_lane"] for item in packet["pull_requests"]] == [
        "community_aged_backlog",
        "community_feedback",
        "composite_remaining",
    ]
    assert [item["scheduling_tier"] for item in packet["pull_requests"]] == [
        1,
        1,
        2,
    ]


def test_request_changes_after_current_head_is_not_community_feedback(
    monkeypatch,
) -> None:
    monkeypatch.setattr(pr_review_module, "_now_iso", lambda: "2026-08-18T12:00:00Z")
    row = _queue_pr(
        24,
        author="community",
        ready_at="2026-08-18T09:00:00Z",
        updated_at="2026-08-18T11:00:00Z",
        review_decision="CHANGES_REQUESTED",
        reviews=[
            {
                "author": {"login": "maintainer"},
                "body": "Please repair the current exact head.",
                "commit": {"oid": str(24).zfill(40)},
                "state": "CHANGES_REQUESTED",
                "submittedAt": "2026-08-18T10:00:00Z",
            }
        ],
    )

    item = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]

    assert item["community_feedback_ready"] is False
    assert item["scheduling_lane"] == "composite_remaining"


def test_review_conclusion_requires_format_exact_head_and_formal_state(
    monkeypatch,
) -> None:
    monkeypatch.setattr(pr_review_module, "_now_iso", lambda: "2026-08-18T12:00:00Z")
    row = _queue_pr(
        21,
        author="community",
        ready_at="2026-08-18T07:00:00Z",
        updated_at="2026-08-18T11:00:00Z",
    )
    head = str(row["headRefOid"])
    row["reviews"] = [
        {
            "author": {"login": "maintainer"},
            "body": _full_review_body(head),
            "commit": {"oid": head},
            "state": "COMMENTED",
            "submittedAt": "2026-08-18T10:00:00Z",
        }
    ]

    invalid = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]
    assert invalid["review_conclusion"]["status"] == "invalid"
    assert (
        invalid["review_conclusion"]["schema_version"]
        == "pull_request_review_conclusion_v0"
    )
    assert (
        "formal_review_state_required"
        in invalid["review_conclusion"]["invalid_reasons"]
    )
    assert invalid["review_action_kind"] == "review_pull_request_exact_head"

    row["reviews"][0]["state"] = "APPROVED"
    valid = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]
    assert valid["review_conclusion"]["status"] == "valid"
    assert valid["review_action_kind"] == "qualify_pull_request_merge_readiness"

    row["reviews"][0]["author"] = {"login": "peer-reviewer"}
    peer_valid = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]
    assert peer_valid["review_conclusion"]["status"] == "valid"
    assert peer_valid["review_conclusion"]["reviewer"] == "peer-reviewer"


def test_latest_review_and_author_owned_fallback_are_enforced(monkeypatch) -> None:
    monkeypatch.setattr(pr_review_module, "_now_iso", lambda: "2026-08-18T12:00:00Z")
    row = _queue_pr(
        31,
        author="maintainer",
        ready_at="2026-08-18T07:00:00Z",
        updated_at="2026-08-18T11:00:00Z",
    )
    head = str(row["headRefOid"])
    row["reviews"] = [
        {
            "author": {"login": "maintainer"},
            "body": _full_review_body(head, author_fallback=True),
            "commit": {"oid": head},
            "state": "COMMENTED",
            "submittedAt": "2026-08-18T09:00:00Z",
        },
        {
            "author": {"login": "maintainer"},
            "body": "REQUEST_CHANGES: fix this",
            "commit": {"oid": head},
            "state": "CHANGES_REQUESTED",
            "submittedAt": "2026-08-18T10:00:00Z",
        },
    ]

    latest_invalid = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]
    assert latest_invalid["review_conclusion"]["status"] == "invalid"

    row["reviews"] = row["reviews"][:1]
    valid_fallback = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]
    assert valid_fallback["review_conclusion"]["status"] == "valid"
    assert valid_fallback["review_action_kind"] is None

    row["reviews"] = [
        {
            "author": {"login": "maintainer"},
            "body": _full_review_body(
                head,
                verdict="REQUEST_CHANGES",
                author_fallback=True,
            ),
            "commit": {"oid": head},
            "state": "COMMENTED",
            "submittedAt": "2026-08-18T10:30:00Z",
        }
    ]
    blocking_fallback = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]
    assert blocking_fallback["review_conclusion"]["status"] == "valid"
    assert blocking_fallback["review_conclusion"]["state"] == "COMMENTED"
    assert blocking_fallback["review_action_kind"] is None

    row["reviews"][0]["body"] = _full_review_body(
        head,
        verdict="REQUEST_CHANGES",
        author_fallback=False,
    )
    untitled_blocking_fallback = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]
    assert untitled_blocking_fallback["review_conclusion"]["status"] == "invalid"
    assert (
        "author_owned_review_missing_titled_commented_fallback"
        in untitled_blocking_fallback["review_conclusion"]["invalid_reasons"]
    )

    row["reviews"] = [
        {
            "author": {"login": "peer-reviewer"},
            "body": _full_review_body(head, verdict="REQUEST_CHANGES"),
            "commit": {"oid": head},
            "state": "APPROVED",
            "submittedAt": "2026-08-18T10:45:00Z",
        }
    ]
    mismatched_peer_verdict = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]
    assert mismatched_peer_verdict["review_conclusion"]["status"] == "invalid"
    assert (
        "review_state_verdict_mismatch"
        in mismatched_peer_verdict["review_conclusion"]["invalid_reasons"]
    )

    row["reviews"] = [
        {
            "author": {"login": "maintainer"},
            "body": _full_review_body(head, author_fallback=True),
            "commit": {"oid": head},
            "state": "COMMENTED",
            "submittedAt": "2026-08-18T09:00:00Z",
        }
    ]
    row["reviews"].append(
        {
            "author": {"login": "maintainer"},
            "body": "Supplemental check note only.",
            "commit": {"oid": head},
            "state": "COMMENTED",
            "submittedAt": "2026-08-18T11:00:00Z",
        }
    )
    ordinary_comment = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]
    assert ordinary_comment["review_conclusion"]["status"] == "valid"
    assert ordinary_comment["review_action_kind"] is None


def test_community_author_self_review_does_not_satisfy_maintainer_queue(
    monkeypatch,
) -> None:
    monkeypatch.setattr(pr_review_module, "_now_iso", lambda: "2026-08-18T12:00:00Z")
    row = _queue_pr(
        3660,
        author="community-author",
        ready_at="2026-08-18T07:00:00Z",
        updated_at="2026-08-18T11:00:00Z",
    )
    head = str(row["headRefOid"])
    row["reviews"] = [
        {
            "author": {"login": "community-author"},
            "body": _full_review_body(head, author_fallback=True),
            "commit": {"oid": head},
            "state": "COMMENTED",
            "submittedAt": "2026-08-18T11:00:00Z",
        }
    ]

    self_review_only = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]

    assert self_review_only["review_conclusion"]["status"] == "invalid"
    assert (
        "formal_review_state_required"
        in self_review_only["review_conclusion"]["invalid_reasons"]
    )
    assert self_review_only["review_action_kind"] == "review_pull_request_exact_head"

    row["reviews"].append(
        {
            "author": {"login": "maintainer"},
            "body": _full_review_body(head),
            "commit": {"oid": head},
            "state": "APPROVED",
            "submittedAt": "2026-08-18T10:00:00Z",
        }
    )
    independently_reviewed = pr_review_module.build_pr_review_packet(
        pull_requests=[row],
        repository="owner/repo",
        limit=10,
        source="fixture",
        state_filter="open",
        reviewer_login="maintainer",
    )["pull_requests"][0]

    assert independently_reviewed["review_conclusion"]["status"] == "valid"
    assert independently_reviewed["review_conclusion"]["reviewer"] == "maintainer"
    assert independently_reviewed["review_action_kind"] == (
        "qualify_pull_request_merge_readiness"
    )
