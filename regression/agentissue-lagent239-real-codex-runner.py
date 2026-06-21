#!/usr/bin/env python3
"""Opt-in real Codex CLI regression for AgentIssue-Bench lagent_239.

The default path materializes the private runner contract without invoking
Codex or Docker. Pass --real-codex with a private prompt path to execute the
host-local Codex CLI plus the selected Docker image, then verify only compact
public evidence and boundary flags.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "agentissue-real-codex-regression-fixture"
SELECTED_TAG = "lagent_239"
SELECTED_IMAGE = "alfin06/agentissue-bench:lagent_239"
PLACEHOLDER = "Synthetic AgentIssue-Bench lagent_239 Prompt Placeholder"
FORBIDDEN_TEXT = [
    "/" + "Users/",
    "~/.codex",
    ".codex/auth.json",
    "OPENAI" + "_API_KEY",
    "ANTHROPIC" + "_API_KEY",
    "GOOGLE" + "_API_KEY",
    "CODEX" + "_ACCESS_TOKEN",
    "raw" + "_patch:",
    "raw" + "_log:",
    "trajectory.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real-codex",
        action="store_true",
        help="Invoke the real host Codex CLI and Docker selected image.",
    )
    parser.add_argument(
        "--prompt-path",
        help="Private AgentIssue prompt path. Required with --real-codex.",
    )
    parser.add_argument("--codex-cli", default="codex")
    parser.add_argument("--docker-cli", default="docker")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=900,
        help="Timeout for the real private runner.",
    )
    parser.add_argument(
        "--keep-root",
        action="store_true",
        help="Keep the private temporary root for local debugging.",
    )
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    runner_root = root / "private-runner-root"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-13T00:00:00+00:00\n"
        "---\n\n"
        "# AgentIssue Real Codex Regression Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Materialize and optionally execute lagent_239 real Codex regression.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-13T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "loopx-platform",
                    "status": "active-read-only",
                    "state_file": state_file,
                    "repo": str(project),
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                    "heartbeat": {"enabled": True},
                }
            ],
        },
    )
    return registry_path, runtime, runner_root


def run_cli(args: list[str], *, cwd: Path = REPO_ROOT) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def materialize_runner(registry: Path, runtime: Path, runner_root: Path) -> dict[str, Any]:
    return run_cli(
        [
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "benchmark",
            "agentissue-codex-runner-flow",
            "--goal-id",
            GOAL_ID,
            "--tag",
            SELECTED_TAG,
            "--private-runner-root",
            str(runner_root),
            "--no-global-sync",
        ]
    )


def assert_no_forbidden_text(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked


def assert_materialized_contract(runner_root: Path, payload: dict[str, Any]) -> None:
    script = runner_root / "run-lagent239.private.sh"
    manifest_path = runner_root / "private-runner.public.json"
    compact_run = runner_root / "benchmark_run.compact.json"
    assert script.exists(), script
    assert script.stat().st_mode & stat.S_IXUSR, oct(script.stat().st_mode)
    assert manifest_path.exists(), manifest_path
    assert compact_run.exists(), compact_run

    script_text = script.read_text(encoding="utf-8")
    for snippet in (
        "PRECHECK_ONLY",
        "run_host_local_codex_cli_patch_worker",
        "evaluate_selected_tag_container",
        "write_compact_public_evidence",
        "export TAG IMAGE BUGGY_SOURCE PATCH_PATH MARKER_DIR",
        "/app/source_code_buggy",
        "/usr/local/bin/run_test_entrypoint.sh apply_patch /patches/attempt.patch",
        "/usr/local/bin/run_test_entrypoint.sh test_patched",
    ):
        assert snippet in script_text, snippet
    assert "~/.codex" not in script_text
    assert "CODEX" + "_ACCESS_TOKEN" not in script_text

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["path_recorded"] is False, manifest
    assert manifest["root_path_recorded"] is False, manifest
    assert manifest["selected_tag"] == SELECTED_TAG, manifest
    assert manifest["selected_image"] == SELECTED_IMAGE, manifest
    assert manifest["generator_boundary"]["codex_cli_invoked"] is False, manifest
    assert manifest["generator_boundary"]["docker_container_started"] is False, manifest
    assert manifest["later_script_boundary"]["will_invoke_host_codex_cli"] is True, manifest
    assert manifest["later_script_boundary"]["will_start_selected_container"] is True, manifest
    assert payload["benchmark_cli"]["real_codex_invoked"] is False, payload
    assert payload["benchmark_cli"]["real_docker_invoked"] is False, payload
    assert_no_forbidden_text(manifest)


def write_loopx_wrapper(root: Path) -> Path:
    wrapper = root / "loopx-wrapper.sh"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"cd {str(REPO_ROOT)!r}\n"
        f"exec {sys.executable!r} -m loopx.cli \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return wrapper


def compact_runner_failure_summary(runner_root: Path) -> dict[str, Any]:
    markers = runner_root / "result-markers"
    patch = runner_root / "Patches" / "lagent_239" / "attempt.patch"
    run_json = runner_root / "benchmark_run.compact.json"
    result_json = runner_root / "benchmark_result.compact.json"
    last_message = runner_root / "codex-last-message.txt"
    exec_log = runner_root / "artifacts" / "private-runner-exec.private.log"
    summary: dict[str, Any] = {
        "codex_last_message_exists": last_message.exists(),
        "codex_last_message_bytes": last_message.stat().st_size if last_message.exists() else 0,
        "patch_exists": patch.exists(),
        "patch_bytes": patch.stat().st_size if patch.exists() else 0,
        "benchmark_run_exists": run_json.exists(),
        "benchmark_result_exists": result_json.exists(),
        "private_exec_log_exists": exec_log.exists(),
        "private_exec_log_bytes": exec_log.stat().st_size if exec_log.exists() else 0,
        "markers": sorted(p.name for p in markers.iterdir()) if markers.exists() else [],
    }
    if patch.exists():
        patch_text = patch.read_text(encoding="utf-8", errors="ignore")
        summary["patch_file_count"] = sum(
            1 for line in patch_text.splitlines() if line.startswith("diff --git ")
        )
        summary["patch_hunk_count"] = sum(
            1 for line in patch_text.splitlines() if line.startswith("@@ ")
        )
    patched_exit = markers / "patched_exit_code"
    if patched_exit.exists():
        summary["patched_exit_code"] = patched_exit.read_text(encoding="utf-8").strip()
    return summary


def run_private_script(
    *,
    root: Path,
    runner_root: Path,
    prompt_path: Path,
    codex_cli: str,
    docker_cli: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    if not prompt_path.exists() or prompt_path.stat().st_size == 0:
        raise AssertionError("private prompt path is missing or empty")
    prompt_text = prompt_path.read_text(encoding="utf-8", errors="ignore")
    if PLACEHOLDER in prompt_text:
        raise AssertionError("private prompt still contains the synthetic placeholder")

    artifacts = runner_root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    wrapper = write_loopx_wrapper(root)
    script = runner_root / "run-lagent239.private.sh"

    common_env = {
        **os.environ,
        "PROMPT_PATH": str(prompt_path),
        "CODEX_BIN": codex_cli,
        "DOCKER_BIN": docker_cli,
        "LOOPX_BIN": str(wrapper),
        "APPEND_HISTORY": "0",
    }
    with (artifacts / "precheck.private.log").open("w", encoding="utf-8") as stream:
        subprocess.run(
            [str(script)],
            cwd=runner_root,
            env={**common_env, "PRECHECK_ONLY": "1"},
            check=True,
            text=True,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
        )
    with (artifacts / "private-runner-exec.private.log").open("w", encoding="utf-8") as stream:
        try:
            subprocess.run(
                [str(script)],
                cwd=runner_root,
                env=common_env,
                check=True,
                text=True,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            summary = compact_runner_failure_summary(runner_root)
            summary["failure_kind"] = "private_runner_timeout"
            raise AssertionError(json.dumps(summary, ensure_ascii=False, sort_keys=True)) from exc
        except subprocess.CalledProcessError as exc:
            summary = compact_runner_failure_summary(runner_root)
            summary["failure_kind"] = "private_runner_nonzero_exit"
            summary["returncode"] = exc.returncode
            raise AssertionError(json.dumps(summary, ensure_ascii=False, sort_keys=True)) from exc

    run_payload = json.loads((runner_root / "benchmark_run.compact.json").read_text(encoding="utf-8"))
    result_payload = json.loads(
        (runner_root / "benchmark_result.compact.json").read_text(encoding="utf-8")
    )
    validation = run_payload["validation"]
    for key in (
        "selected_image_only",
        "single_tag_only",
        "buggy_source_extracted",
        "host_codex_cli_invoked",
        "patch_exported_from_buggy_source_git_diff",
        "patch_applied_in_container",
        "no_upload",
        "no_submit",
        "no_public_ranking_path",
    ):
        assert validation[key] is True, (key, validation)
    for key in (
        "raw_logs_public",
        "patch_content_public",
        "credential_values_recorded",
        "codex_auth_synced_to_container_or_remote",
    ):
        assert validation[key] is False, (key, validation)
    assert run_payload["selected_tag"] == SELECTED_TAG, run_payload
    assert run_payload["selected_image"] == SELECTED_IMAGE, run_payload
    assert result_payload["selected_tag"] == SELECTED_TAG, result_payload

    score = run_payload["official_task_score"]
    summary = {
        "mode": "real-codex",
        "selected_tag": run_payload["selected_tag"],
        "selected_image": run_payload["selected_image"],
        "resolved": bool(score.get("resolved")),
        "score_value": score.get("value"),
        "patched_exit_code": run_payload.get("patched_exit_code"),
        "patch_bytes": run_payload.get("patch_bytes"),
        "changed_file_count": run_payload.get("changed_file_count"),
        "hunk_count": run_payload.get("hunk_count"),
        "boundary": {
            "no_upload": validation["no_upload"],
            "no_submit": validation["no_submit"],
            "no_public_ranking_path": validation["no_public_ranking_path"],
            "codex_auth_synced_to_container_or_remote": validation[
                "codex_auth_synced_to_container_or_remote"
            ],
        },
    }
    assert_no_forbidden_text(summary)
    return summary


def main() -> int:
    args = parse_args()
    if args.real_codex and not args.prompt_path:
        raise SystemExit("--prompt-path is required with --real-codex")

    temp_root = Path(tempfile.mkdtemp(prefix="agentissue-real-codex-regression-"))
    try:
        registry, runtime, runner_root = write_fixture(temp_root)
        payload = materialize_runner(registry, runtime, runner_root)
        assert_materialized_contract(runner_root, payload)
        if args.real_codex:
            try:
                summary = run_private_script(
                    root=temp_root,
                    runner_root=runner_root,
                    prompt_path=Path(args.prompt_path).expanduser(),
                    codex_cli=args.codex_cli,
                    docker_cli=args.docker_cli,
                    timeout_seconds=args.timeout_seconds,
                )
            except AssertionError as exc:
                print(f"agentissue-lagent239-real-codex-runner failed {exc}")
                return 1
            print(
                "agentissue-lagent239-real-codex-runner ok "
                + json.dumps(summary, ensure_ascii=False, sort_keys=True)
            )
        else:
            print(
                "agentissue-lagent239-real-codex-runner ok "
                "mode=contract-only; pass --real-codex --prompt-path <private> "
                "to invoke host Codex CLI and Docker"
            )
    finally:
        if args.keep_root:
            print(f"kept_private_root={temp_root}")
        else:
            shutil.rmtree(temp_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
