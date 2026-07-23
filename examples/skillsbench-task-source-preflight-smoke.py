#!/usr/bin/env python3
"""Smoke-test SkillsBench canonical task-source preflight."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_ledger import load_benchmark_run_ledger  # noqa: E402
from scripts.skillsbench_automation_loop import (  # noqa: E402
    _bootstrap_light_blocker_kind,
    _bootstrap_light_preflight_block_required,
    build_plan,
    main as skillsbench_automation_loop_main,
    parse_args,
)


def _write_task(root: Path, relative: str, *, verifier_text: str = "") -> None:
    task = root / relative
    dockerfile = task / "environment" / "Dockerfile"
    dockerfile.parent.mkdir(parents=True, exist_ok=True)
    dockerfile.write_text("FROM scratch\n", encoding="utf-8")
    (task / "task.toml").write_text('version = "1.1"\n', encoding="utf-8")
    if verifier_text:
        verifier = task / "verifier" / "test.sh"
        verifier.parent.mkdir(parents=True, exist_ok=True)
        verifier.write_text(verifier_text, encoding="utf-8")


def _write_task_registry(root: Path, rows: list[dict[str, object]]) -> None:
    registry = root / "website" / "src" / "data" / "tasks-registry.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def _latest_decision_run(case: dict[str, object]) -> dict[str, object]:
    latest = case.get("latest_decision") if isinstance(case, dict) else {}
    run_id = latest.get("baseline_run_id") if isinstance(latest, dict) else None
    runs = case.get("runs") if isinstance(case, dict) else []
    if isinstance(runs, list):
        for run in runs:
            if isinstance(run, dict) and run.get("run_id") == run_id:
                return run
    raise AssertionError(f"latest decision run not found: {case}")


def _app_goal_args(
    *,
    task_id: str,
    skillsbench_root: Path,
    jobs: Path,
    ledger: Path,
    job_name: str,
) -> list[str]:
    return [
        "--task-id",
        task_id,
        "--route",
        "codex-app-server-goal-baseline",
        "--skillsbench-root",
        str(skillsbench_root),
        "--jobs-dir",
        str(jobs),
        "--job-name",
        job_name,
        "--run-group-id",
        job_name,
        "--ledger-path",
        str(ledger),
        "--update-ledger",
        "--host-local-acp-launch",
        "--remote-command-file-bridge-ready",
        "--allow-deprecated-app-server-goal-route",
    ]


def test_sanity_task_source_fails_before_runner_spend() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-task-source-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        _write_task(skillsbench_root, "experiments/sanity-tasks/hello-world")
        _write_task(skillsbench_root, "tasks/citation-check")
        _write_task(skillsbench_root, "tasks/powerlifting-coef-calc")

        jobs = root / "jobs"
        ledger = root / "ledger.json"
        args = [
            "--task-id",
            "hello-world",
            "--route",
            "raw-codex-autonomous-max5",
            "--skillsbench-root",
            str(skillsbench_root),
            "--jobs-dir",
            str(jobs),
            "--job-name",
            "skillsbench-hello-world-task-source-preflight",
            "--run-group-id",
            "skillsbench-hello-world-task-source-preflight",
            "--ledger-path",
            str(ledger),
            "--update-ledger",
        ]
        plan = build_plan(parse_args(args))
        preflight = plan["task_setup_preflight"]
        assert preflight["status"] == "task_missing_from_canonical_tasks", preflight
        assert preflight["canonical_task_present"] is False, preflight
        assert preflight["alternate_source_kind"] == "experiments_sanity_tasks", (
            preflight
        )
        assert preflight["canonical_equivalent_status"] == (
            "no_close_canonical_match"
        ), preflight
        assert preflight["task_source_path_recorded"] is False, preflight
        assert preflight["task_source_content_recorded"] is False, preflight
        assert preflight["nearest_canonical_task_ids"] == [
            "citation-check",
            "powerlifting-coef-calc",
        ], preflight

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(args)

        assert rc == 0, stderr.getvalue()
        compact_path = (
            jobs
            / "skillsbench-hello-world-task-source-preflight"
            / "hello-world__raw_codex_autonomous_max5"
            / "benchmark_run.compact.json"
        )
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["first_blocker"] == "skillsbench_task_source_preflight_blocked"
        assert compact["score_failure_attribution"] == (
            "skillsbench_task_source_preflight_blocked"
        )
        assert compact["task_setup_preflight"]["status"] == (
            "task_missing_from_canonical_tasks"
        )
        assert compact["task_setup_preflight"]["alternate_source_kind"] == (
            "experiments_sanity_tasks"
        )
        assert compact["task_setup_preflight"]["canonical_equivalent_status"] == (
            "no_close_canonical_match"
        )
        assert compact["validation"]["no_raw_task_text_read"] is True, compact

        update = load_benchmark_run_ledger(ledger)
        case = update["benchmarks"]["skillsbench@1.1"]["cases"]["hello-world"]
        assert case["latest_decision"]["decision"] == (
            "baseline_task_source_preflight_selection_required"
        ), case
        latest_run = _latest_decision_run(case)
        assert latest_run["repair_class"] == (
            "skillsbench_task_source_preflight_selection"
        )


def test_tasks_extra_excluded_source_is_not_canonical_missing() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-no-canonical-equivalent-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        _write_task(skillsbench_root, "tasks/3d-scan-calc")
        _write_task(skillsbench_root, "tasks/offer-letter-generator")
        _write_task(skillsbench_root, "tasks/paratransit-routing")
        _write_task(skillsbench_root, "tasks/travel-planning")
        _write_task_registry(
            skillsbench_root,
            [
                {
                    "title": "scheduling-email-assistant",
                    "path": "tasks-extra/scheduling-email-assistant",
                    "excluded": True,
                }
            ],
        )

        jobs = root / "jobs"
        ledger = root / "ledger.json"
        args = [
            "--task-id",
            "scheduling-email-assistant",
            "--route",
            "raw-codex-autonomous-max5",
            "--skillsbench-root",
            str(skillsbench_root),
            "--jobs-dir",
            str(jobs),
            "--job-name",
            "skillsbench-scheduling-email-task-source-preflight",
            "--run-group-id",
            "skillsbench-scheduling-email-task-source-preflight",
            "--ledger-path",
            str(ledger),
            "--update-ledger",
        ]
        plan = build_plan(parse_args(args))
        preflight = plan["task_setup_preflight"]
        assert preflight["status"] == "task_excluded_from_formal_tasks", preflight
        assert preflight["first_blocker"] == "skillsbench_task_source_excluded", (
            preflight
        )
        assert preflight["canonical_task_present"] is False, preflight
        assert preflight["alternate_source_kind"] == "tasks_extra", preflight
        assert preflight["registry_task_present"] is True, preflight
        assert preflight["registry_task_path"] == (
            "tasks-extra/scheduling-email-assistant"
        ), preflight
        assert preflight["registry_excluded"] is True, preflight
        assert preflight["canonical_equivalent_status"] == (
            "no_close_canonical_match"
        ), preflight
        assert preflight["selection_recommendation"] == (
            "excluded_tasks_extra_requires_explicit_sanity_source_mode"
        ), preflight
        assert preflight["raw_task_text_read"] is False, preflight
        assert preflight["task_source_path_recorded"] is False, preflight
        assert preflight["task_source_content_recorded"] is False, preflight

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(args)

        assert rc == 0, stderr.getvalue()
        compact_path = (
            jobs
            / "skillsbench-scheduling-email-task-source-preflight"
            / "scheduling-email-assistant__raw_codex_autonomous_max5"
            / "benchmark_run.compact.json"
        )
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["first_blocker"] == "skillsbench_task_source_excluded"
        assert compact["score_failure_attribution"] == (
            "skillsbench_task_source_excluded"
        )
        assert compact["task_setup_preflight"]["status"] == (
            "task_excluded_from_formal_tasks"
        )
        assert compact["task_setup_preflight"]["alternate_source_kind"] == "tasks_extra"
        assert compact["task_setup_preflight"]["registry_excluded"] is True
        assert compact["validation"]["no_raw_task_text_read"] is True, compact

        update = load_benchmark_run_ledger(ledger)
        case = update["benchmarks"]["skillsbench@1.1"]["cases"][
            "scheduling-email-assistant"
        ]
        assert case["latest_decision"]["decision"] == (
            "baseline_task_source_excluded_from_formal_scoring"
        ), case
        latest_run = _latest_decision_run(case)
        assert latest_run["repair_class"] == "skillsbench_task_source_excluded"


def test_reverse_tunnel_app_goal_defaults_verifier_bootstrap_fail_fast() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-verifier-preflight-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        _write_task(
            skillsbench_root,
            "tasks/verifier-network-bootstrap",
            verifier_text=(
                "#!/usr/bin/env bash\n"
                "curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            ),
        )

        jobs = root / "jobs"
        ledger = root / "ledger.json"
        args = [
            "--task-id",
            "verifier-network-bootstrap",
            "--route",
            "codex-app-server-goal-baseline",
            "--skillsbench-root",
            str(skillsbench_root),
            "--jobs-dir",
            str(jobs),
            "--job-name",
            "skillsbench-verifier-bootstrap-preflight",
            "--run-group-id",
            "skillsbench-verifier-bootstrap-preflight",
            "--ledger-path",
            str(ledger),
            "--update-ledger",
            "--host-local-acp-launch",
            "--remote-command-file-bridge-ready",
            "--allow-deprecated-app-server-goal-route",
        ]
        parsed = parse_args(args)
        assert parsed.fail_fast_on_apt_risk is True
        assert parsed.apt_risk_fail_fast_defaulted is True
        assert parsed.fail_fast_on_verifier_bootstrap_risk is True
        assert parsed.verifier_bootstrap_fail_fast_defaulted is True
        assert parsed.bootstrap_light_fail_fast_defaulted is True
        plan = build_plan(parsed)
        preflight = plan["task_setup_preflight"]
        assert preflight["status"] == "verifier_bootstrap_risk_detected", preflight
        assert preflight["bootstrap_light_candidate_eligible"] is False, preflight
        assert "verifier_bootstrap_risk_detected" in preflight[
            "bootstrap_light_blocking_fields"
        ], preflight
        assert plan["bootstrap_light_candidate_required"] is True, plan
        assert plan["fail_fast_on_apt_risk"] is True, plan
        assert plan["apt_risk_fail_fast_defaulted"] is True, plan
        assert plan["fail_fast_on_verifier_bootstrap_risk"] is True, plan
        assert plan["verifier_bootstrap_fail_fast_defaulted"] is True, plan
        assert plan["bootstrap_light_fail_fast_defaulted"] is True, plan

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(args)

        assert rc == 0, stderr.getvalue()
        compact_path = (
            jobs
            / "skillsbench-verifier-bootstrap-preflight"
            / "verifier-network-bootstrap__codex_app_server_goal"
            / "benchmark_run.compact.json"
        )
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["first_blocker"] == (
            "skillsbench_verifier_bootstrap_risk_preflight_blocked"
        )
        assert compact["score_failure_attribution"] == (
            "skillsbench_verifier_bootstrap_risk_preflight_blocked"
        )
        assert compact["task_setup_preflight"][
            "bootstrap_light_candidate_eligible"
        ] is False
        assert "verifier_bootstrap_risk_detected" in compact[
            "task_setup_preflight"
        ]["bootstrap_light_blocking_fields"]
        assert compact["task_staging"]["verifier_bootstrap_risk_preflight_blocked"] is True
        assert compact["task_staging"]["bootstrap_light_preflight_blocked"] is True
        assert compact["task_staging"]["bootstrap_light_blocker_kind"] == "verifier"
        assert compact["runner_config"]["fail_fast_on_apt_risk"] is True
        assert compact["runner_config"]["apt_risk_fail_fast_defaulted"] is True
        assert compact["runner_config"]["fail_fast_on_verifier_bootstrap_risk"] is True
        assert compact["runner_config"]["verifier_bootstrap_fail_fast_defaulted"] is True
        assert compact["runner_config"]["bootstrap_light_fail_fast_defaulted"] is True


def test_reverse_tunnel_app_goal_defaults_apt_bootstrap_fail_fast() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-apt-bootstrap-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        _write_task(skillsbench_root, "tasks/apt-bootstrap")
        dockerfile = (
            skillsbench_root
            / "tasks"
            / "apt-bootstrap"
            / "environment"
            / "Dockerfile"
        )
        dockerfile.write_text(
            "FROM ubuntu:22.04\nRUN apt-get update && apt-get install -y curl\n",
            encoding="utf-8",
        )

        jobs = root / "jobs"
        ledger = root / "ledger.json"
        args = _app_goal_args(
            task_id="apt-bootstrap",
            skillsbench_root=skillsbench_root,
            jobs=jobs,
            ledger=ledger,
            job_name="skillsbench-apt-bootstrap-preflight",
        )
        parsed = parse_args(args)
        assert parsed.fail_fast_on_apt_risk is True
        assert parsed.apt_risk_fail_fast_defaulted is True
        assert parsed.fail_fast_on_verifier_bootstrap_risk is True
        assert parsed.bootstrap_light_fail_fast_defaulted is True
        plan = build_plan(parsed)
        preflight = plan["task_setup_preflight"]
        assert preflight["status"] == "dockerfile_package_bootstrap_risk_detected", (
            preflight
        )
        assert preflight["bootstrap_light_candidate_eligible"] is False, preflight
        assert "apt_setup_risk_detected" in preflight[
            "bootstrap_light_blocking_fields"
        ], preflight
        assert plan["bootstrap_light_candidate_required"] is True, plan

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(args)

        assert rc == 0, stderr.getvalue()
        compact_path = (
            jobs
            / "skillsbench-apt-bootstrap-preflight"
            / "apt-bootstrap__codex_app_server_goal"
            / "benchmark_run.compact.json"
        )
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["first_blocker"] == (
            "skillsbench_docker_apt_setup_risk_preflight_blocked"
        )
        assert compact["task_staging"]["bootstrap_light_preflight_blocked"] is True
        assert compact["task_staging"]["bootstrap_light_blocker_kind"] == "apt"
        assert compact["task_staging"]["apt_risk_preflight_blocked"] is True
        assert compact["runner_config"]["fail_fast_on_apt_risk"] is True
        assert compact["runner_config"]["apt_risk_fail_fast_defaulted"] is True
        assert compact["runner_config"]["bootstrap_light_fail_fast_defaulted"] is True

        update = load_benchmark_run_ledger(ledger)
        case = update["benchmarks"]["skillsbench@1.1"]["cases"]["apt-bootstrap"]
        assert case["latest_decision"]["decision"] == (
            "baseline_setup_preflight_selection_required"
        ), case
        latest_run = _latest_decision_run(case)
        assert latest_run["failure_class"] == (
            "skillsbench_runner_setup_blocked_before_agent_rounds"
        )
        assert latest_run["score_failure_attribution"] == (
            "skillsbench_docker_apt_setup_risk_preflight_blocked"
        )
        assert latest_run["repair_class"] == (
            "skillsbench_setup_preflight_selection"
        )
        assert (
            "skillsbench_docker_apt_setup_risk_preflight_blocked"
            in latest_run["failure_labels"]
        ), case
        assert latest_run["task_staging"]["apt_risk_preflight_blocked"] is True


def test_reverse_tunnel_app_goal_blocks_pip_bootstrap_light_risk() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-pip-bootstrap-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        _write_task(skillsbench_root, "tasks/pip-bootstrap")
        dockerfile = (
            skillsbench_root
            / "tasks"
            / "pip-bootstrap"
            / "environment"
            / "Dockerfile"
        )
        dockerfile.write_text(
            "FROM python:3.12-slim\nRUN python -m pip install pandas\n",
            encoding="utf-8",
        )

        jobs = root / "jobs"
        ledger = root / "ledger.json"
        args = _app_goal_args(
            task_id="pip-bootstrap",
            skillsbench_root=skillsbench_root,
            jobs=jobs,
            ledger=ledger,
            job_name="skillsbench-pip-bootstrap-preflight",
        )

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(args)

        assert rc == 0, stderr.getvalue()
        compact_path = (
            jobs
            / "skillsbench-pip-bootstrap-preflight"
            / "pip-bootstrap__codex_app_server_goal"
            / "benchmark_run.compact.json"
        )
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["first_blocker"] == (
            "skillsbench_dockerfile_package_bootstrap_risk_preflight_blocked"
        )
        assert compact["task_staging"]["bootstrap_light_preflight_blocked"] is True
        assert compact["task_staging"]["bootstrap_light_blocker_kind"] == (
            "dockerfile_package"
        )
        assert compact["task_staging"][
            "dockerfile_package_bootstrap_risk_preflight_blocked"
        ] is True
        assert compact["task_setup_preflight"][
            "dockerfile_pip_bootstrap_patch_required"
        ] is True


def test_reverse_tunnel_app_goal_allows_explicit_staged_bootstrap_repair() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-staged-bootstrap-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        _write_task(skillsbench_root, "tasks/pip-bootstrap")
        dockerfile = (
            skillsbench_root
            / "tasks"
            / "pip-bootstrap"
            / "environment"
            / "Dockerfile"
        )
        dockerfile.write_text(
            "FROM python:3.12-slim\nRUN python -m pip install pandas\n",
            encoding="utf-8",
        )

        jobs = root / "jobs"
        ledger = root / "ledger.json"
        args = _app_goal_args(
            task_id="pip-bootstrap",
            skillsbench_root=skillsbench_root,
            jobs=jobs,
            ledger=ledger,
            job_name="skillsbench-staged-bootstrap-allowed",
        )
        parsed = parse_args(args + ["--allow-staged-bootstrap-repair-run"])
        assert parsed.allow_staged_bootstrap_repair_run is True
        assert parsed.fail_fast_on_apt_risk is False
        assert parsed.apt_risk_fail_fast_defaulted is False
        assert parsed.fail_fast_on_verifier_bootstrap_risk is False
        assert parsed.verifier_bootstrap_fail_fast_defaulted is False
        assert parsed.bootstrap_light_fail_fast_defaulted is False

        plan = build_plan(parsed)
        preflight = plan["task_setup_preflight"]
        assert plan["bootstrap_light_candidate_required"] is True, plan
        assert plan["bootstrap_light_fail_fast_required"] is False, plan
        assert plan["allow_staged_bootstrap_repair_run"] is True, plan
        assert preflight["bootstrap_light_candidate_eligible"] is False, preflight
        assert "dockerfile_pip_bootstrap_patch_required" in preflight[
            "bootstrap_light_blocking_fields"
        ], preflight
        blocker_kind = _bootstrap_light_blocker_kind(
            preflight["bootstrap_light_blocking_fields"]
        )
        assert blocker_kind == "dockerfile_package"
        assert (
            _bootstrap_light_preflight_block_required(
                parsed,
                blocker_kind=blocker_kind,
            )
            is False
        )

        explicitly_blocked = parse_args(
            args
            + [
                "--allow-staged-bootstrap-repair-run",
                "--fail-fast-on-apt-risk",
            ]
        )
        assert explicitly_blocked.allow_staged_bootstrap_repair_run is True
        assert explicitly_blocked.fail_fast_on_apt_risk is True
        assert (
            _bootstrap_light_preflight_block_required(
                explicitly_blocked,
                blocker_kind=blocker_kind,
            )
            is True
        )


if __name__ == "__main__":
    test_sanity_task_source_fails_before_runner_spend()
    test_tasks_extra_excluded_source_is_not_canonical_missing()
    test_reverse_tunnel_app_goal_defaults_verifier_bootstrap_fail_fast()
    test_reverse_tunnel_app_goal_defaults_apt_bootstrap_fail_fast()
    test_reverse_tunnel_app_goal_blocks_pip_bootstrap_light_risk()
    test_reverse_tunnel_app_goal_allows_explicit_staged_bootstrap_repair()
    print("skillsbench-task-source-preflight-smoke ok")
