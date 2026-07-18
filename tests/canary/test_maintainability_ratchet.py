from __future__ import annotations

from pathlib import Path

from loopx.canary.maintainability_ratchet import (
    build_control_plane_maintainability_report,
    collect_oversized_decision_functions,
    evaluate_maintainability_findings,
    render_control_plane_maintainability_report,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_current_repository_debt_is_reviewed_without_line_count_pins() -> None:
    report = build_control_plane_maintainability_report(REPOSITORY_ROOT)

    assert report["ok"] is True, render_control_plane_maintainability_report(report)
    assert report["policy"]["freezes_exact_line_counts"] is False
    assert report["unreviewed_count"] == 0
    assert report["stale_exception_count"] == 0
    assert set(report["category_counts"]) == {
        "compatibility_facade",
        "dependency_debt",
        "oversized_decision_function",
    }
    assert report["reviewed_exception_count"] == report["finding_count"]


def test_reviewed_exception_lifecycle_rejects_new_debt_and_stale_entries() -> None:
    finding = {
        "id": "dependency_debt:loopx.sample->loopx.presentation",
        "category": "dependency_debt",
        "path": "loopx/sample.py",
    }
    exception = {
        finding["id"]: {
            "reason": "A public compatibility window still exists.",
            "retirement_plan": "Delete the edge after the compatibility window closes.",
        }
    }

    unreviewed = evaluate_maintainability_findings(
        [finding],
        reviewed_exceptions={},
    )
    assert unreviewed["ok"] is False
    assert unreviewed["unreviewed_findings"] == [
        {**finding, "review_state": "unreviewed"}
    ]

    reviewed = evaluate_maintainability_findings(
        [finding],
        reviewed_exceptions=exception,
    )
    assert reviewed["ok"] is True
    assert reviewed["reviewed_exception_count"] == 1

    stale = evaluate_maintainability_findings(
        [],
        reviewed_exceptions=exception,
    )
    assert stale["ok"] is False
    assert stale["stale_exceptions"][0]["id"] == finding["id"]


def test_decision_ratchet_measures_function_ast_not_file_length(tmp_path: Path) -> None:
    control_plane = tmp_path / "loopx" / "control_plane"
    control_plane.mkdir(parents=True)
    (tmp_path / "loopx" / "quota.py").write_text("", encoding="utf-8")
    (tmp_path / "loopx" / "status.py").write_text("", encoding="utf-8")
    (control_plane / "large_file.py").write_text(
        "\n".join(["# padding"] * 500 + ["def small():", "    return 1", ""]),
        encoding="utf-8",
    )
    (control_plane / "decisions.py").write_text(
        "def oversized(value):\n"
        "    total = 0\n"
        "    if value > 0:\n"
        "        total += 1\n"
        "    if value > 1:\n"
        "        total += 1\n"
        "    if value > 2:\n"
        "        total += 1\n"
        "    if value > 3:\n"
        "        total += 1\n"
        "    return total\n",
        encoding="utf-8",
    )

    findings = collect_oversized_decision_functions(
        tmp_path,
        statement_limit=100,
        decision_point_limit=3,
    )

    assert [finding["symbol"] for finding in findings] == ["oversized"]
    assert findings[0]["metrics"]["decision_points"] == 4
    assert all(finding["path"] != "loopx/control_plane/large_file.py" for finding in findings)
