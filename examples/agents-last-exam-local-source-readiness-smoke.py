#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    build_agents_last_exam_local_source_readiness,
)

OFFICIAL_REPO = "https://github.com/rdi-berkeley/agents-last-exam.git"


def make_source_root(root: Path, *, remote: str = OFFICIAL_REPO) -> Path:
    source_root = root / "ale-source"
    (source_root / "ale_run").mkdir(parents=True)
    (source_root / "ale_run" / "__init__.py").write_text("", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=source_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "loopx@example.invalid"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "LoopX Smoke"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=source_root, check=True)
    subprocess.run(["git", "add", "ale_run/__init__.py"], cwd=source_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "fixture"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", "HEAD"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=source_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "branch", "--set-upstream-to", "origin/main", current_branch],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    return source_root


def advance_origin_main_without_advancing_head(source_root: Path) -> None:
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    (source_root / "upstream-only.txt").write_text("new upstream fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "upstream-only.txt"], cwd=source_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "upstream fixture"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    upstream_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=source_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", upstream_head],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "update-ref", f"refs/heads/{current_branch}", head_before],
        cwd=source_root,
        check=True,
        capture_output=True,
    )


def assert_redacted(payload: dict[str, object]) -> None:
    source = payload["source"]
    assert isinstance(source, dict)
    assert source["source_root_path_recorded"] is False
    assert source["upstream_head"] is None or "/" not in source["upstream_head"]
    assert source["fetch_origin_attempted"] in {False, True}
    runner_probe = payload["runner_probe"]
    assert isinstance(runner_probe, dict)
    assert runner_probe["source_root_path_recorded"] is False
    assert runner_probe["python_module_path_recorded"] is False
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["container_started"] is False
    assert boundary["task_body_read"] is False
    assert boundary["model_api_invoked"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["screenshot_captured"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["hidden_references_allowed"] is False
    assert boundary["production_actions_allowed"] is False
    assert boundary["local_paths_recorded"] is False
    assert boundary["command_argv_recorded"] is False


def run_fixture_smoke() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source_root = make_source_root(Path(tmp))
        payload = build_agents_last_exam_local_source_readiness(
            source_root=str(source_root),
        )
        assert payload["schema_version"] == "agents_last_exam_local_source_readiness_v0"
        assert payload["ready"] is True
        assert payload["first_blocker"] == "ready_for_redacted_ale_source_lock"
        assert payload["source"]["remote_matches_expected"] is True
        assert payload["source"]["head"]
        assert payload["source"]["upstream_declared"] is True
        assert payload["source"]["head_matches_upstream"] is True
        assert payload["source"]["upstream_ahead_count"] == 0
        assert payload["source"]["upstream_behind_count"] == 0
        assert payload["runner_probe"]["python_module_available"] is True
        assert_redacted(payload)

        current = build_agents_last_exam_local_source_readiness(
            source_root=str(source_root),
            require_upstream_current=True,
        )
        assert current["ready"] is True
        assert current["source"]["require_upstream_current"] is True
        assert_redacted(current)

        current_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=source_root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "checkout", "--detach", "HEAD"],
            cwd=source_root,
            check=True,
            capture_output=True,
        )
        detached = build_agents_last_exam_local_source_readiness(
            source_root=str(source_root),
            require_upstream_current=True,
        )
        assert detached["ready"] is True
        assert detached["source"]["upstream_ref"] == "origin__main", detached
        assert detached["source"]["upstream_fallback_ref"] is True, detached
        assert detached["source"]["head_matches_upstream"] is True, detached
        assert_redacted(detached)
        subprocess.run(
            ["git", "checkout", current_branch],
            cwd=source_root,
            check=True,
            capture_output=True,
        )

        advance_origin_main_without_advancing_head(source_root)
        behind = build_agents_last_exam_local_source_readiness(
            source_root=str(source_root),
            require_upstream_current=True,
        )
        assert behind["ready"] is False
        assert behind["first_blocker"] == "source_root_behind_upstream"
        assert behind["source"]["head_matches_upstream"] is False
        assert behind["source"]["upstream_behind_count"] == 1
        assert_redacted(behind)

        mismatch = build_agents_last_exam_local_source_readiness(
            source_root=str(source_root),
            expected_repo_url="https://github.com/example/not-ale.git",
        )
        assert mismatch["ready"] is False
        assert mismatch["first_blocker"] == "source_root_origin_mismatch"
        assert_redacted(mismatch)

    missing = build_agents_last_exam_local_source_readiness(
        source_root="/definitely/not/a/real/ale/source/root",
    )
    assert missing["ready"] is False
    assert missing["first_blocker"] == "source_root_not_available"
    assert missing["source"]["source_root_path_recorded"] is False


def run_cli_smoke() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source_root = make_source_root(Path(tmp))
        base_cmd = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "ale-local-source-readiness",
            "--source-root",
            str(source_root),
        ]
        result = subprocess.run(
            base_cmd,
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["ready"] is True
        assert_redacted(payload)

        current = subprocess.run(
            [
                *base_cmd,
                "--require-upstream-current",
                "--require-ready",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        current_payload = json.loads(current.stdout)
        assert current_payload["ok"] is True
        assert current_payload["source"]["head_matches_upstream"] is True
        assert_redacted(current_payload)

        advance_origin_main_without_advancing_head(source_root)
        behind = subprocess.run(
            [
                *base_cmd,
                "--require-upstream-current",
                "--require-ready",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert behind.returncode == 1
        behind_payload = json.loads(behind.stdout)
        assert behind_payload["ok"] is False
        assert behind_payload["error"] == "source_root_behind_upstream"
        assert_redacted(behind_payload)

        mismatch = subprocess.run(
            [
                *base_cmd,
                "--expected-repo-url",
                "https://github.com/example/not-ale.git",
                "--require-ready",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert mismatch.returncode == 1
        mismatch_payload = json.loads(mismatch.stdout)
        assert mismatch_payload["ok"] is False
        assert mismatch_payload["error"] == "source_root_origin_mismatch"
        assert_redacted(mismatch_payload)


if __name__ == "__main__":
    run_fixture_smoke()
    run_cli_smoke()
    print("agents-last-exam-local-source-readiness-smoke ok")
