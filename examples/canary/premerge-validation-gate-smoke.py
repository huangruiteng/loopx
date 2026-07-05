#!/usr/bin/env python3
"""Smoke-test the canary pre-merge validation gate contract."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.canary.premerge import (  # noqa: E402
    _gate_status,
    build_premerge_validation_gate,
    downgrade_inherited_baseline_failures,
)


def commands_from(run: dict | None) -> list[str]:
    if not isinstance(run, dict):
        return []
    commands: list[str] = []
    for check in run.get("selected_checks", []):
        if not isinstance(check, dict):
            continue
        commands.append(str(check.get("command") or ""))
    return commands


def assert_control_plane_change_selects_state_machine_validation() -> None:
    payload = build_premerge_validation_gate(
        changed_files=[
            "loopx/control_plane/work_items/interaction_contract.py",
            "loopx/quota.py",
        ],
        execute=False,
    )
    assert payload["ok"] is True, payload
    assert payload["dry_run"] is True, payload
    classification = payload["classification"]
    assert "control_plane" in classification["surfaces"], payload
    assert "core-control-plane" in classification["risk_profiles"], payload
    assert "canary-runner" in classification["risk_profiles"], payload
    catalog_commands = commands_from(payload["catalog_run"])
    risk_commands = commands_from(payload["risk_profile_run"])
    summary = payload["validation_summary"]
    assert summary["schema_version"] == "premerge_validation_summary_v0", payload
    assert summary["selected_check_count"] >= len(catalog_commands), payload
    assert "python3 examples/control_plane/interaction-contract-state-machine-smoke.py" in (
        summary["selected_commands"]
    ), payload
    assert any("interaction-contract-state-machine-smoke.py" in item for item in catalog_commands), payload
    assert any("control-plane-integrated-canary-smoke.py" in item for item in catalog_commands), payload
    assert any("bounded-context-namespace-smoke.py" in item for item in catalog_commands), payload
    assert risk_commands, payload
    assert payload["gate"]["status"] == "preview_only", payload
    assert payload["gate"]["merge_gate_passed"] is False, payload


def assert_public_docs_change_adds_boundary_scan() -> None:
    payload = build_premerge_validation_gate(
        changed_files=["AGENTS.md", "docs/product/core-control-plane/foo.md"],
        execute=False,
    )
    classification = payload["classification"]
    assert "docs_project_content" in classification["surfaces"], payload
    assert classification["public_boundary_scan_recommended"] is True, payload
    boundary_commands = commands_from(payload["boundary_run"])
    assert boundary_commands == [
        "python3 examples/control_plane/check-public-boundary-smoke.py"
    ], payload


def assert_changed_python_gets_compile_check() -> None:
    payload = build_premerge_validation_gate(
        changed_files=["loopx/canary/premerge.py"],
        execute=False,
    )
    direct_ids = [check["id"] for check in payload["direct_checks"]]
    assert "changed_python_py_compile" in direct_ids, payload
    compile_check = next(
        check
        for check in payload["direct_checks"]
        if check["id"] == "changed_python_py_compile"
    )
    assert "loopx/canary/premerge.py" in compile_check["display_argv"], payload


def assert_benchmark_sensitive_change_blocks_self_merge() -> None:
    payload = build_premerge_validation_gate(
        changed_files=["loopx/benchmark_adapters/skillsbench.py"],
        execute=False,
    )
    assert "benchmark_sensitive" in payload["classification"]["surfaces"], payload
    assert payload["classification"]["manual_holds"], payload
    assert payload["gate"]["status"] == "manual_review_required", payload
    assert payload["gate"]["self_merge_allowed"] is False, payload


def assert_cli_json_preview() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "premerge",
            "--changed-file",
            "loopx/canary/premerge.py",
            "--no-execute",
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["schema_version"] == "loopx_premerge_validation_gate_v0", payload
    assert payload["gate"]["status"] == "preview_only", payload
    summary = payload["validation_summary"]
    assert summary["schema_version"] == "premerge_validation_summary_v0", payload
    assert summary["direct_check_count"] >= 4, payload
    assert any("git diff --check" in command for command in summary["direct_commands"]), payload
    assert "python3 examples/canary/premerge-validation-gate-smoke.py" in (
        summary["selected_commands"]
    ), payload
    assert len(summary["all_commands"]) >= len(summary["direct_commands"]) + len(
        summary["selected_commands"]
    ), payload
    assert summary["failed_commands"] == [], payload
    selector_sources = payload.get("selector_sources")
    assert selector_sources is None or isinstance(selector_sources, dict), payload


def assert_no_changes_does_not_mask_direct_failures() -> None:
    status = _gate_status(
        execute=True,
        changed_files=[],
        direct_checks=[{"ok": False, "status": "failed", "id": "diff_check_committed"}],
        catalog_run={"ok": True},
        risk_profile_run=None,
        boundary_run=None,
        manual_holds=[],
    )
    assert status["status"] == "failed", status
    assert status["merge_gate_passed"] is False, status


def assert_installed_wrapper_premerge_redirects_to_checkout() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        release_root = Path(temp_dir) / "release"
        scripts_dir = release_root / "scripts"
        scripts_dir.mkdir(parents=True)
        wrapper = scripts_dir / "loopx"
        shutil.copy2(REPO_ROOT / "scripts" / "loopx", wrapper)
        completed = subprocess.run(
            [
                str(wrapper),
                "--format",
                "json",
                "canary",
                "premerge",
                "--changed-file",
                "loopx/canary/premerge.py",
                "--no-execute",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True, payload
    assert payload["gate"]["status"] == "preview_only", payload
    assert Path(payload["repo_root"]).resolve() == REPO_ROOT.resolve(), payload


def assert_inherited_line_budget_red_is_advisory_only() -> None:
    inherited_run = {
        "ok": False,
        "warning_count": 0,
        "selected_checks": [
            {
                "ok": False,
                "status": "failed",
                "command": "python3 examples/control_plane/repo-python-line-budget-smoke.py",
                "stderr_tail": "loopx/benchmark_adapters/skillsbench_acp_relay.py has 3775 lines",
            }
        ],
    }
    downgraded = downgrade_inherited_baseline_failures(
        inherited_run,
        changed_files=["loopx/canary/premerge.py"],
    )
    assert downgraded["ok"] is True, downgraded
    assert downgraded["failure_count"] == 0, downgraded
    assert downgraded["advisory_failure_count"] == 1, downgraded
    assert downgraded["selected_checks"][0]["status"] == "advisory_inherited_failure", downgraded

    extensionless_path_run = {
        "ok": False,
        "warning_count": 0,
        "selected_checks": [
            {
                "ok": False,
                "status": "failed",
                "command": "python3 examples/control_plane/repo-python-line-budget-smoke.py",
                "stderr_tail": "loopx/benchmark_adapters/skillsbench_acp_relay.py has 3775 lines",
            }
        ],
    }
    extensionless_path_downgraded = downgrade_inherited_baseline_failures(
        extensionless_path_run,
        changed_files=["scripts/loopx"],
    )
    assert extensionless_path_downgraded["ok"] is True, extensionless_path_downgraded

    current_diff_run = {
        "ok": False,
        "warning_count": 0,
        "selected_checks": [
            {
                "ok": False,
                "status": "failed",
                "command": "python3 examples/control_plane/repo-python-line-budget-smoke.py",
                "stderr_tail": "loopx/canary/premerge.py has 2200 lines",
            }
        ],
    }
    still_failed = downgrade_inherited_baseline_failures(
        current_diff_run,
        changed_files=["loopx/canary/premerge.py"],
    )
    assert still_failed["ok"] is False, still_failed
    assert still_failed["selected_checks"][0]["status"] == "failed", still_failed


def main() -> None:
    assert_control_plane_change_selects_state_machine_validation()
    assert_public_docs_change_adds_boundary_scan()
    assert_changed_python_gets_compile_check()
    assert_benchmark_sensitive_change_blocks_self_merge()
    assert_cli_json_preview()
    assert_no_changes_does_not_mask_direct_failures()
    assert_installed_wrapper_premerge_redirects_to_checkout()
    assert_inherited_line_budget_red_is_advisory_only()
    print("premerge-validation-gate-smoke ok")


if __name__ == "__main__":
    main()
