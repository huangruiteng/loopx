from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from loopx import __version__
from loopx.control_plane.testing.release_commit_qualification import (
    EXPECTED_RESULT_SCHEMA_BY_QUALIFICATION,
    OUTCOME_QUALIFICATION_ID,
    REQUIRED_QUALIFICATION_IDS,
    build_exact_release_commit_qualification,
    collect_release_source_identity,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
COMMIT = "1" * 40
TREE = "2" * 40
DIGEST = "sha256:" + "3" * 64


def _source(*, commit: str = COMMIT, tree: str = TREE, dirty: bool = False) -> dict[str, object]:
    return {
        "git_commit": commit,
        "git_tree": tree,
        "git_dirty": dirty,
        "package_version": __version__,
        "version_tag": f"v{__version__}",
    }


def _summary(qualification_id: str, *, commit: str = COMMIT) -> dict[str, object]:
    summaries: dict[str, dict[str, object]] = {
        "pytest": {"passed_count": 634, "failed_count": 0, "skipped_count": 2},
        "ruff": {"violation_count": 0},
        "mypy": {"error_count": 0},
        "risk_canary": {
            "selected_check_count": 13,
            "failure_count": 0,
            "manual_hold_count": 0,
        },
        "full_public": {
            "ready": True,
            "shard_count": 6,
            "failure_count": 0,
            "timeout_count": 0,
        },
        "install_upgrade_host": {
            "install_passed": True,
            "upgrade_passed": True,
            "host_passed": True,
        },
        "public_boundary": {"scanned_path_count": 8, "violation_count": 0},
        "doubao_actual_default": {
            "model_id": "doubao-seed-1.6",
            "topology": "actual_default_one_arm",
            "scenario_count": 12,
            "repeats_per_scenario": 2,
            "actor_call_count": 24,
            "failure_count": 0,
            "skip_count": 0,
            "qualification_passed": True,
        },
        OUTCOME_QUALIFICATION_ID: {
            "decision": "owner_review_required",
            "eligible_for_owner_review": True,
            "candidate_ref": f"git:{commit}",
            "distinct_case_count": 3,
            "paired_attempt_count": 6,
            "regression_count": 0,
            "evidence_gap_count": 0,
        },
    }
    return summaries[qualification_id]


def _check(
    qualification_id: str,
    *,
    source: dict[str, object] | None = None,
    commit: str = COMMIT,
) -> dict[str, object]:
    return {
        "schema_version": "exact_release_check_receipt_v0",
        "source": copy.deepcopy(source or _source(commit=commit)),
        "status": "passed",
        "result_schema_version": EXPECTED_RESULT_SCHEMA_BY_QUALIFICATION[
            qualification_id
        ],
        "result_digest": DIGEST,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "summary": _summary(qualification_id, commit=commit),
    }


def _manifest(
    *,
    outcome_claimed: bool = False,
    source: dict[str, object] | None = None,
) -> dict[str, object]:
    candidate = source or _source()
    checks = {
        qualification_id: _check(qualification_id, source=candidate)
        for qualification_id in REQUIRED_QUALIFICATION_IDS
    }
    if outcome_claimed:
        checks[OUTCOME_QUALIFICATION_ID] = _check(
            OUTCOME_QUALIFICATION_ID,
            source=candidate,
            commit=str(candidate["git_commit"]),
        )
    return {
        "schema_version": "exact_release_commit_qualification_manifest_v0",
        "candidate": candidate,
        "claims": {"long_horizon_outcome_uplift": outcome_claimed},
        "qualifications": checks,
    }


def test_exact_release_manifest_qualifies_one_arm_default_without_outcome_pair() -> None:
    receipt = build_exact_release_commit_qualification(
        _manifest(),
        observed_source=_source(),
    )

    assert receipt["ready_for_release"] is True
    assert receipt["decision"] == "ready_for_owner_release"
    assert receipt["automatic_release_promotion_allowed"] is False
    assert receipt["outcome_baseline_requirement"] == (
        "not_required_without_outcome_uplift_claim"
    )
    assert receipt["required_qualification_ids"] == list(REQUIRED_QUALIFICATION_IDS)
    assert receipt["qualification_failures"] == []
    assert receipt["source_mismatches"] == []
    assert receipt["read_boundary"]["model_api_invoked"] is False
    assert receipt["read_boundary"]["release_mutation_invoked"] is False


def test_outcome_claim_requires_matched_baseline_receipt() -> None:
    manifest = _manifest(outcome_claimed=True)
    receipt = build_exact_release_commit_qualification(manifest, observed_source=_source())
    assert receipt["ready_for_release"] is True
    assert receipt["required_qualification_ids"][-1] == OUTCOME_QUALIFICATION_ID

    del manifest["qualifications"][OUTCOME_QUALIFICATION_ID]
    receipt = build_exact_release_commit_qualification(manifest, observed_source=_source())
    assert receipt["ready_for_release"] is False
    assert receipt["decision"] == "hold_missing_qualification"
    assert receipt["missing_qualification_ids"] == [OUTCOME_QUALIFICATION_ID]


def test_source_identity_drift_and_dirty_checkout_fail_closed() -> None:
    manifest = _manifest()
    manifest["qualifications"]["full_public"]["source"]["git_tree"] = "4" * 40
    receipt = build_exact_release_commit_qualification(
        manifest,
        observed_source=_source(commit="5" * 40, dirty=True),
    )

    assert receipt["ready_for_release"] is False
    assert receipt["decision"] == "hold_source_mismatch"
    assert set(receipt["source_mismatches"]) >= {
        "full_public:git_tree",
        "observed_source:git_commit",
        "observed_source:git_dirty",
    }

    dirty_candidate = _manifest(source=_source(dirty=True))
    receipt = build_exact_release_commit_qualification(dirty_candidate)
    assert "candidate:git_dirty" in receipt["source_mismatches"]


def test_failed_skipped_and_semantically_invalid_checks_do_not_qualify() -> None:
    manifest = _manifest()
    manifest["qualifications"]["ruff"]["status"] = "skipped"
    manifest["qualifications"]["doubao_actual_default"]["summary"][
        "actor_call_count"
    ] = 13
    receipt = build_exact_release_commit_qualification(manifest, observed_source=_source())

    assert receipt["ready_for_release"] is False
    assert receipt["decision"] == "hold_failed_qualification"
    assert set(receipt["qualification_failures"]) == {
        "doubao_actual_default_failed",
        "ruff_skipped",
    }


def test_manifest_rejects_unknown_or_noncompact_evidence() -> None:
    unknown = _manifest()
    unknown["qualifications"]["ad_hoc_smoke"] = _check("pytest")
    with pytest.raises(ValueError, match="unknown ids"):
        build_exact_release_commit_qualification(unknown)

    raw = _manifest()
    raw["qualifications"]["pytest"]["raw_log"] = "must not enter the manifest"
    with pytest.raises(ValueError, match="unknown fields"):
        build_exact_release_commit_qualification(raw)

    bad_outcome = _manifest(outcome_claimed=True)
    bad_outcome["qualifications"][OUTCOME_QUALIFICATION_ID]["summary"][
        "candidate_ref"
    ] = "git:" + "9" * 40
    receipt = build_exact_release_commit_qualification(bad_outcome)
    assert receipt["qualification_failures"] == ["release_outcome_baseline_failed"]


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_release_qualification_cli_matches_clean_git_source_and_is_read_only(
    tmp_path: Path,
) -> None:
    source_repo = tmp_path / "source"
    (source_repo / "loopx").mkdir(parents=True)
    _git(source_repo, "init")
    _git(source_repo, "config", "user.email", "loopx@example.invalid")
    _git(source_repo, "config", "user.name", "LoopX Test")
    (source_repo / "source.txt").write_text("release source\n", encoding="utf-8")
    (source_repo / "pyproject.toml").write_text(
        '[project]\nname = "loopx"\nversion = "9.8.7"\n',
        encoding="utf-8",
    )
    (source_repo / "loopx" / "__init__.py").write_text(
        '__version__ = "9.8.7"\n',
        encoding="utf-8",
    )
    _git(source_repo, "add", "source.txt", "pyproject.toml", "loopx/__init__.py")
    _git(source_repo, "commit", "-m", "release source")
    source = collect_release_source_identity(source_repo)
    manifest = _manifest(source=source)
    manifest_path = tmp_path / "qualification.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "release-qualification",
            "--manifest-json",
            str(manifest_path),
            "--repo-root",
            str(source_repo),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["ready_for_release"] is True
    assert payload["observed_source"] == source
    assert payload["candidate"]["package_version"] == "9.8.7"
    assert str(tmp_path) not in result.stdout

    (source_repo / "source.txt").write_text("dirty release source\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "release-qualification",
            "--manifest-json",
            str(manifest_path),
            "--repo-root",
            str(source_repo),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["decision"] == "hold_source_mismatch"
    assert payload["source_mismatches"] == ["observed_source:git_dirty"]


def test_release_qualification_cli_redacts_manifest_path_errors(tmp_path: Path) -> None:
    missing = tmp_path / "private-release-name.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "release-qualification",
            "--manifest-json",
            str(missing),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"] == "manifest_unreadable"
    assert str(tmp_path) not in result.stdout
