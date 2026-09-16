from __future__ import annotations

from pathlib import Path

from loopx.canary.maintainability_ratchet import (
    MODULE_METRIC_BASELINE_SCHEMA_VERSION,
    build_control_plane_maintainability_report,
    collect_dependency_debt,
    collect_module_metric_findings,
    collect_oversized_decision_functions,
    evaluate_maintainability_findings,
    module_metrics,
    render_control_plane_maintainability_report,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_current_repository_debt_is_reviewed_without_line_count_pins() -> None:
    report = build_control_plane_maintainability_report(REPOSITORY_ROOT)

    assert report["ok"] is True, render_control_plane_maintainability_report(report)
    assert report["policy"]["freezes_exact_line_counts"] is False
    assert (
        "does not retain a coarse all-file hotspot limit"
        in report["policy"]["repository_scope_decision"]
    )
    assert report["unreviewed_count"] == 0
    assert report["stale_exception_count"] == 0
    assert set(report["category_counts"]) == {"compatibility_facade"}
    assert report["category_counts"].get("oversized_decision_function", 0) == 0
    assert report["reviewed_exception_count"] == report["finding_count"]
    # One scan of the immutable checkout owns both debt and metric assertions.
    # Mutated temporary repositories below must still be evaluated afresh.
    assert report["policy"]["module_line_limit"] == 1500
    assert report["policy"]["module_any_limit"] == 300
    assert report["policy"]["module_dict_any_limit"] == 300
    assert report["category_counts"].get("module_metric_budget", 0) == 0


def test_module_metric_ratchet_detects_new_oversized_module(tmp_path: Path) -> None:
    module_path = tmp_path / "loopx" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text(
        "\n".join(["# padding"] * 1501),
        encoding="utf-8",
    )
    tracked_paths = {module_path}

    findings = collect_module_metric_findings(
        tmp_path,
        tracked_paths=tracked_paths,
    )

    assert len(findings) == 1
    assert findings[0]["category"] == "module_metric_budget"
    assert findings[0]["path"] == "loopx/sample.py"
    assert findings[0]["metrics"]["lines"] == 1501
    assert findings[0]["regressions"] == {"lines": 1501}


def test_module_metric_ratchet_rejects_growth_above_checked_in_baseline(
    tmp_path: Path,
) -> None:
    module_path = tmp_path / "loopx" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text(
        "from typing import Any\n"
        "value: dict[str, Any] = {}\n"
        "extra = 'padding'\n",
        encoding="utf-8",
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        (
            '{"schema_version": "'
            + MODULE_METRIC_BASELINE_SCHEMA_VERSION
            + '", "default_limits": {"lines": 1500, "any_count": 300, '
            '"dict_any_count": 300}, "module_metric_ceilings": {'
            '"loopx/sample.py": {"lines": 2, "any_count": 1, "dict_any_count": 1}}}'
        ),
        encoding="utf-8",
    )

    findings = collect_module_metric_findings(
        tmp_path,
        tracked_paths={module_path},
        baseline_path=baseline_path,
    )

    assert len(findings) == 1
    assert findings[0]["regressions"] == {"lines": 3}
    assert module_metrics(module_path)["any_count"] == 1


def test_module_metric_debt_names_the_reviewed_ledger_to_refresh(
    tmp_path: Path,
) -> None:
    """Module metric growth is settled in the checked-in ledger, not by exception."""

    module_path = tmp_path / "loopx" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("\n".join(["# padding"] * 1501), encoding="utf-8")

    payload = evaluate_maintainability_findings(
        collect_module_metric_findings(tmp_path, tracked_paths={module_path}),
        reviewed_exceptions={},
    )
    rendered = render_control_plane_maintainability_report(
        {
            **payload,
            "policy": {
                "module_metric_baseline_path": "loopx/canary/module_metric_baseline.json"
            },
        }
    )

    assert payload["ok"] is False
    assert "module metric debt" in rendered
    assert "loopx/canary/module_metric_baseline.json" in rendered


def test_review_without_module_metric_debt_keeps_the_report_unchanged() -> None:
    finding = {
        "id": "compatibility_facade:loopx.sample",
        "category": "compatibility_facade",
        "path": "loopx/sample.py",
    }

    rendered = render_control_plane_maintainability_report(
        evaluate_maintainability_findings(
            [finding],
            reviewed_exceptions={
                finding["id"]: {
                    "reason": "A public compatibility window still exists.",
                    "retirement_plan": "Delete the edge after the window closes.",
                }
            },
        )
    )

    assert "module metric debt" not in rendered


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


def test_reviewed_metric_debt_rejects_growth_and_accepts_improvement() -> None:
    finding = {
        "id": "oversized_decision_function:loopx.sample:large",
        "category": "oversized_decision_function",
        "path": "loopx/sample.py",
        "metrics": {"statements": 100, "decision_points": 70},
    }
    exception = {
        finding["id"]: {
            "reason": "Existing debt predates the ratchet.",
            "retirement_plan": "Extract bounded policy helpers.",
            "metric_ceilings": {"statements": 100, "decision_points": 70},
        }
    }

    improved = evaluate_maintainability_findings(
        [{**finding, "metrics": {"statements": 90, "decision_points": 60}}],
        reviewed_exceptions=exception,
    )
    assert improved["ok"] is True
    assert improved["magnitude_regression_count"] == 0

    worsened = evaluate_maintainability_findings(
        [{**finding, "metrics": {"statements": 101, "decision_points": 70}}],
        reviewed_exceptions=exception,
    )
    assert worsened["ok"] is False
    assert worsened["magnitude_regressions"][0]["metric_regressions"] == [
        {"metric": "statements", "actual": 101, "ceiling": 100}
    ]

    missing_ceiling = evaluate_maintainability_findings(
        [finding],
        reviewed_exceptions={
            finding["id"]: {
                "reason": "Existing debt predates the ratchet.",
                "retirement_plan": "Extract bounded policy helpers.",
            }
        },
    )
    assert missing_ceiling["ok"] is False
    assert missing_ceiling["invalid_exceptions"] == [finding["id"]]


def test_dependency_ratchet_normalizes_equivalent_module_imports(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "loopx"
    control_plane = package_root / "control_plane"
    control_plane.mkdir(parents=True)
    (package_root / "presentation.py").write_text("", encoding="utf-8")
    (package_root / "cli_commands").mkdir()
    (package_root / "quota.py").write_text(
        "from loopx.control_plane.quota import build_quota\n",
        encoding="utf-8",
    )
    (package_root / "status.py").write_text("", encoding="utf-8")
    (control_plane / "sample.py").write_text(
        "from loopx import cli_commands, presentation\n",
        encoding="utf-8",
    )
    direct_consumer = package_root / "direct_consumer.py"
    direct_consumer.write_text("import loopx.quota as quota\n", encoding="utf-8")
    parent_consumer = package_root / "parent_consumer.py"
    parent_consumer.write_text("from loopx import quota\n", encoding="utf-8")
    tracked_paths = set(tmp_path.rglob("*.py"))

    findings = collect_dependency_debt(tmp_path, tracked_paths=tracked_paths)
    finding_ids = {finding["id"] for finding in findings}

    assert (
        "dependency_debt:loopx.control_plane.sample->loopx.cli_commands" in finding_ids
    )
    assert (
        "dependency_debt:loopx.control_plane.sample->loopx.presentation" in finding_ids
    )
    assert "dependency_debt:loopx.direct_consumer->loopx.quota:*" in finding_ids
    assert "dependency_debt:loopx.parent_consumer->loopx.quota:*" in finding_ids


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
    assert all(
        finding["path"] != "loopx/control_plane/large_file.py" for finding in findings
    )


def test_decision_ratchet_covers_quota_cli_orchestration(tmp_path: Path) -> None:
    package_root = tmp_path / "loopx"
    cli_commands = package_root / "cli_commands"
    cli_commands.mkdir(parents=True)
    (package_root / "quota.py").write_text("", encoding="utf-8")
    (package_root / "status.py").write_text("", encoding="utf-8")
    (cli_commands / "quota.py").write_text(
        "def handle_quota_command(value):\n"
        "    if value > 0:\n"
        "        return 'run'\n"
        "    if value < 0:\n"
        "        return 'skip'\n"
        "    return 'wait'\n",
        encoding="utf-8",
    )

    findings = collect_oversized_decision_functions(
        tmp_path,
        statement_limit=100,
        decision_point_limit=1,
    )

    assert findings == [
        {
            "id": (
                "oversized_decision_function:"
                "loopx.cli_commands.quota:handle_quota_command"
            ),
            "category": "oversized_decision_function",
            "path": "loopx/cli_commands/quota.py",
            "module": "loopx.cli_commands.quota",
            "symbol": "handle_quota_command",
            "line": 1,
            "metrics": {"statements": 5, "decision_points": 2},
            "thresholds": {
                "max_statements": 100,
                "max_decision_points": 1,
            },
        }
    ]
