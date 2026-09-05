from __future__ import annotations

import json
import shlex
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import loopx.canary.planner as canary_planner
import loopx.cli_commands.canary as canary_command
from loopx.canary.planner import CURRENT_REPO_PROFILES
from loopx.canary.premerge import classify_premerge_surfaces
from loopx.canary.qualification_profiles import (
    BENCHMARK_TOOLKIT_DEEP_TEST_COMMAND,
    BENCHMARK_TOOLKIT_DEEP_TEST_PATHS,
)
from loopx.canary.quality_surface_catalog import (
    QUALITY_SURFACE_CATALOG,
    build_quality_surface_catalog_audit,
)
from loopx.canary.runner import EXPLICIT_GROUPED_SMOKES, build_canary_smoke_suite_run
from loopx.cli import main


def test_current_high_risk_surfaces_have_no_catalog_drift() -> None:
    audit = build_quality_surface_catalog_audit(
        CURRENT_REPO_PROFILES,
        repo_root=Path(__file__).resolve().parents[2],
    )

    assert audit["ok"] is True
    assert audit["drift_count"] == 0
    assert audit["repository_reference_validation"] == "performed"
    assert audit["classified_surface_count"] == audit["high_risk_profile_count"]
    assert audit["gaps"] == []


def test_benchmark_integrity_launch_lineage_has_deterministic_coverage() -> None:
    profile = next(
        profile
        for profile in CURRENT_REPO_PROFILES
        if profile["id"] == "benchmark-toolkit-boundary"
    )
    surfaces = [
        surface
        for surface in QUALITY_SURFACE_CATALOG
        if surface["canary_profile_id"] == "benchmark-toolkit-boundary"
    ]

    assert profile["quality_risk"] == "high"
    profile_commands = [check["command"] for check in profile["checks"]]
    assert profile_commands[0] == (
        "python3 examples/benchmark-integrity-launch-lineage-smoke.py"
    )
    deep_check = next(check for check in profile["checks"] if check["tier"] == "deep")
    assert deep_check["command"] == BENCHMARK_TOOLKIT_DEEP_TEST_COMMAND
    assert deep_check["check_kind"] == "unit_gate"
    assert "not durable smoke evidence" in deep_check["reason"]
    assert all(check["mandatory"] is True for check in profile["checks"])
    assert BENCHMARK_TOOLKIT_DEEP_TEST_PATHS == (
        "tests/capabilities/test_benchmark_launch_admission.py",
        "tests/capabilities/test_benchmark_route_receipt.py",
        "tests/capabilities/test_benchmark_external_agent.py",
        "tests/capabilities/test_traex_benchmark_evidence.py",
        "tests/capabilities/test_benchmark_strict_integrity.py",
        "tests/capabilities/test_benchmark_toolkit.py",
    )
    assert all(
        denied not in profile_commands[0].casefold()
        for denied in ("docker", "model", "benchmark run")
    )
    assert [surface["surface_id"] for surface in surfaces] == [
        "benchmark-integrity-launch-lineage"
    ]
    layers = surfaces[0]["layers"]
    assert {
        layer: layers[layer]["status"]
        for layer in ("unit_contract", "durable_smoke", "catalog_canary")
    } == {
        "unit_contract": "covered",
        "durable_smoke": "covered",
        "catalog_canary": "covered",
    }
    assert layers["durable_smoke"]["refs"] == [
        "examples/benchmark-integrity-launch-lineage-smoke.py"
    ]
    release_command = layers["release_gate"]["refs"][0]
    assert release_command == (
        "loopx canary premerge --profile benchmark-toolkit-boundary --tier deep"
    )
    assert "benchmark-integrity-deep-pytest-gate.py" not in EXPLICIT_GROUPED_SMOKES
    for layer in ("host_upgrade", "model_behavior"):
        assert layers[layer]["status"] == "not_applicable"
        assert layers[layer]["rationale"]


@pytest.mark.parametrize(
    ("tier", "extra_args", "expect_deep"),
    [
        ("deep", [], True),
        ("standard", [], False),
        ("standard", ["--include-deep-checks"], True),
    ],
)
def test_premerge_cli_resolves_deep_checks_from_tier_or_explicit_flag(
    tier: str,
    extra_args: list[str],
    expect_deep: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "--format",
            "json",
            "canary",
            "premerge",
            "--profile",
            "benchmark-toolkit-boundary",
            "--tier",
            tier,
            "--no-execute",
            *extra_args,
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    commands = [check["command"] for check in payload["catalog_run"]["selected_checks"]]

    assert exit_code == 0
    assert payload["gate"]["status"] == "preview_only"
    assert payload["catalog_run"]["selection_inputs"]["catalog_profiles"] == [
        "benchmark-toolkit-boundary"
    ]
    assert (
        payload["catalog_run"]["selection_inputs"]["check_soft_target_per_profile"] == 4
    )
    assert (BENCHMARK_TOOLKIT_DEEP_TEST_COMMAND in commands) is expect_deep
    assert "python3 examples/benchmark-artifact-path-filter-smoke.py" in commands


def test_benchmark_release_gate_command_selects_deep_pytest_gate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    surface = next(
        item
        for item in QUALITY_SURFACE_CATALOG
        if item["surface_id"] == "benchmark-integrity-launch-lineage"
    )
    command = surface["layers"]["release_gate"]["refs"][0]

    exit_code = main([*shlex.split(command)[1:], "--no-execute", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    commands = [check["command"] for check in payload["catalog_run"]["selected_checks"]]

    assert exit_code == 0
    assert BENCHMARK_TOOLKIT_DEEP_TEST_COMMAND in commands


def test_mandatory_profile_checks_survive_a_smaller_requested_cap() -> None:
    plan = canary_planner.build_catalog_canary_plan(
        profiles=["benchmark-toolkit-boundary"],
        include_deep_checks=True,
        max_checks_per_profile=1,
    )
    profile = plan["domain_profiles"][0]
    commands = [check["command"] for check in profile["checks"]]

    assert profile["check_soft_target"] == 1
    assert profile["mandatory_check_count"] == 5
    assert profile["check_soft_target_expanded_for_mandatory"] is True
    assert commands == [
        "python3 examples/benchmark-integrity-launch-lineage-smoke.py",
        "python3 examples/benchmark-run-permission-policy-smoke.py",
        "python3 examples/benchmark-candidate-source-boundary-smoke.py",
        BENCHMARK_TOOLKIT_DEEP_TEST_COMMAND,
        "python3 examples/benchmark-artifact-path-filter-smoke.py",
    ]


def test_runner_limit_expands_to_preserve_mandatory_profile_checks() -> None:
    payload = build_canary_smoke_suite_run(
        suite="catalog-plan",
        profiles=["benchmark-toolkit-boundary"],
        include_deep_checks=True,
        max_checks_per_profile=1,
        limit=1,
        execute=False,
    )

    assert payload["ok"] is True
    assert payload["limit"] == 1
    assert payload["effective_limit"] == 5
    assert payload["limit_expanded_for_mandatory"] is True
    assert payload["selected_check_count"] == 5
    assert all(check["mandatory"] is True for check in payload["selected_checks"])


@pytest.mark.parametrize(
    ("option", "value", "error_kind"),
    [
        ("--profile", "benchmark-toolkit-boundry", "unknown_profile"),
        ("--family", "Unknown Family", "unknown_family"),
        ("--surface", "unknown surface sentinel", "unknown_surface"),
    ],
)
def test_premerge_cli_fails_closed_for_unknown_explicit_selector(
    option: str,
    value: str,
    error_kind: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "--format",
            "json",
            "canary",
            "premerge",
            option,
            value,
            "--no-execute",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["gate"]["status"] == "failed"
    assert payload["catalog_run"]["warning_count"] == 1
    assert payload["catalog_run"]["warnings"] == [
        {"kind": error_kind, "selector": value.lower().replace(" ", "-")}
        if option != "--surface"
        else {"kind": error_kind, "selector": value}
    ]


@pytest.mark.parametrize(
    "changed_file",
    [
        "loopx/capabilities/benchmark_toolkit/integrity.py",
        "tests/capabilities/test_benchmark_toolkit.py",
        "tests/fixtures/benchmark_integrity/case.json",
    ],
)
def test_benchmark_paths_require_hold_and_public_boundary_scan(
    changed_file: str,
) -> None:
    classification = classify_premerge_surfaces([changed_file])

    assert "benchmark_sensitive" in classification["surfaces"]
    assert "public_boundary" in classification["surfaces"]
    assert classification["public_boundary_scan_recommended"] is True
    assert [hold["kind"] for hold in classification["manual_holds"]] == [
        "benchmark_sensitive"
    ]


def test_non_benchmark_test_does_not_inherit_benchmark_hold() -> None:
    classification = classify_premerge_surfaces(
        ["tests/capabilities/test_change_quality.py"]
    )

    assert "benchmark_sensitive" not in classification["surfaces"]
    assert classification["manual_holds"] == []


@pytest.mark.parametrize(
    ("option", "value", "selection_key"),
    [
        ("--surface", "benchmark integrity", "surfaces"),
        ("--family", "Evidence Lifecycle", "families"),
    ],
)
def test_premerge_cli_forwards_explicit_catalog_selectors(
    option: str,
    value: str,
    selection_key: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "--format",
            "json",
            "canary",
            "premerge",
            option,
            value,
            "--no-execute",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["gate"]["status"] == "preview_only"
    assert payload["catalog_run"]["selection_inputs"][selection_key] == [value]
    assert payload["catalog_run"]["selected_check_count"] > 0


def test_packaged_audit_keeps_classification_without_source_checkout() -> None:
    audit = build_quality_surface_catalog_audit(CURRENT_REPO_PROFILES)

    assert audit["ok"] is True
    assert audit["repository_reference_validation"] == "source_checkout_unavailable"


def test_planner_quality_audit_prefers_explicit_source_checkout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packaged_root = tmp_path / "release"
    (packaged_root / "loopx" / "canary").mkdir(parents=True)
    (packaged_root / "pyproject.toml").write_text("", encoding="utf-8")
    (packaged_root / "loopx" / "canary" / "quality_surface_catalog.py").write_text(
        "",
        encoding="utf-8",
    )
    monkeypatch.setattr(canary_planner, "REPO_ROOT", packaged_root)

    packaged_audit = canary_planner.build_quality_surface_catalog_audit()
    checkout_audit = canary_planner.build_quality_surface_catalog_audit(
        repo_root=Path(__file__).resolve().parents[2]
    )

    assert packaged_audit["ok"] is True
    assert (
        packaged_audit["repository_reference_validation"]
        == "source_checkout_unavailable"
    )
    assert checkout_audit["ok"] is True
    assert checkout_audit["drift_count"] == 0
    assert checkout_audit["repository_reference_validation"] == "performed"


def test_quality_audit_cli_passes_invoking_checkout_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, Path] = {}

    def build_audit(*, repo_root: Path) -> dict[str, bool]:
        captured["repo_root"] = repo_root
        return {"ok": True}

    monkeypatch.setattr(
        canary_command,
        "_resolve_git_repo_root",
        lambda candidate: tmp_path,
    )
    monkeypatch.setattr(
        canary_command,
        "build_quality_surface_catalog_audit",
        build_audit,
    )

    result = canary_command.handle_canary_command(
        SimpleNamespace(command="canary", canary_command="quality-audit"),
        output_format=lambda args: "json",
        print_payload=lambda payload, output_format, renderer: None,
    )

    assert result == 0
    assert captured["repo_root"] == tmp_path


def test_unclassified_high_risk_profile_is_drift() -> None:
    profiles = [*CURRENT_REPO_PROFILES, {"id": "new-risk", "quality_risk": "high"}]

    audit = build_quality_surface_catalog_audit(profiles)

    assert audit["ok"] is False
    assert {
        (item["code"], item.get("canary_profile_id")) for item in audit["drift"]
    } >= {("unclassified_high_risk_profile", "new-risk")}


def test_oracle_cannot_reuse_product_source_as_expected_truth() -> None:
    catalog = deepcopy(QUALITY_SURFACE_CATALOG)
    catalog[0]["semantic_oracle"]["refs"] = [catalog[0]["owner_paths"][0]]

    audit = build_quality_surface_catalog_audit(
        CURRENT_REPO_PROFILES,
        catalog=catalog,
    )

    assert audit["ok"] is False
    assert any(
        item["code"] == "circular_oracle_uses_product_source" for item in audit["drift"]
    )


def test_not_applicable_layer_requires_a_reason_but_is_not_a_gap() -> None:
    catalog = deepcopy(QUALITY_SURFACE_CATALOG)
    catalog[0]["layers"]["model_behavior"] = {"status": "not_applicable"}

    invalid = build_quality_surface_catalog_audit(
        CURRENT_REPO_PROFILES,
        catalog=catalog,
    )
    assert any(
        item["code"] == "not_applicable_without_rationale" for item in invalid["drift"]
    )

    catalog[0]["layers"]["model_behavior"]["rationale"] = (
        "Scheduler precedence is deterministic."
    )
    valid = build_quality_surface_catalog_audit(
        CURRENT_REPO_PROFILES,
        catalog=catalog,
    )
    assert valid["ok"] is True
    assert not any(
        gap["surface_id"] == "interaction-scheduler-authority" for gap in valid["gaps"]
    )


def test_same_evidence_cannot_stand_in_for_multiple_layers() -> None:
    catalog = deepcopy(QUALITY_SURFACE_CATALOG)
    shared_ref = catalog[0]["layers"]["durable_smoke"]["refs"][0]
    catalog[0]["layers"]["release_gate"] = {
        "status": "covered",
        "refs": [shared_ref],
    }

    audit = build_quality_surface_catalog_audit(
        CURRENT_REPO_PROFILES,
        catalog=catalog,
    )

    assert any(
        item["code"] == "duplicate_evidence_across_layers" for item in audit["drift"]
    )
