#!/usr/bin/env python3
"""Smoke-test the public benchmark developer workflow guide."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "benchmark-developer-workflow.md"
README = REPO_ROOT / "README.md"
DOCS_INDEX = REPO_ROOT / "docs" / "README.md"
TASKS = REPO_ROOT / "CONTRIBUTOR_TASKS.md"

FORBIDDEN_SNIPPETS = (
    "/Users/",
    "~/.codex",
    ".codex/auth.json",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "HF_TOKEN",
    "password",
    "secret",
)


def require(text: str, snippets: list[str], *, source: Path) -> None:
    missing = [snippet for snippet in snippets if snippet not in text]
    assert not missing, f"{source} missing {missing}"


def main() -> int:
    doc = DOC.read_text(encoding="utf-8")
    require(
        doc,
        [
            "# Benchmark Developer Workflow",
            "LoopX treats benchmark execution as a developer workflow",
            "## Golden Path",
            "## Capture The Process While Running",
            "Each real run should improve the developer workflow",
            "Before launch, write down the intended route",
            "## Cloud ECS Benchmark Host Route",
            "Use the cloud ECS benchmark host route as the default",
            "ECS-style cloud VM",
            "Cloud-host Codex connectivity is its own preflight",
            "### ECS Host Bootstrap SOP",
            "scripts/benchmark_ecs_bootstrap.py",
            "scripts/benchmark_agent_runtime_layer.py",
            "preinstalled as a stable layer",
            "harbor_codex_cli_tools",
            "No module named 'harbor_host_codex_goal_agent'",
            "importlib.import_module(\"harbor_host_codex_goal_agent\")",
            "importlib.import_module(\"loopx.benchmark_core.loop_protocol\")",
            "tmux`, `launchd`, or a generated `run.sh`",
            "packet_only_observation",
            "loopx.benchmark_core.loop_protocol",
            "baseline: native Codex app-server Goal mode",
            "test: LoopX prompt-driven polling",
            "loopx-prompt-polling-test",
            "loopx_experiment_protocol=max5_blind_loop_no_feedback",
            "loopx_prompt_polling_rounds=5",
            "loopx_prompt_polling_round_timeout_sec=21600",
            "follow-up",
            "`turn/start` calls in the same thread",
            "harbor_prompt_polling_round_timeout_before_completion",
            "max_rounds_budget=5",
            "official_feedback_forwarded=false",
            "official_feedback_blinded_count",
            "do not compare it as test",
            "official case-local LoopX product",
            "case-local LoopX active todo state",
            "completion_source_of_truth",
            "/app/.local/bin/loopx",
            "real `loopx` CLI",
            "bootstraps a case-local registry",
            "`loopx todo add`",
            "host must not claim or complete the case todo",
            "treatment proof is prompt-driven",
            "prompt-driven",
            "worker should",
            "case-local CLI through `harbor-env-exec`",
            "The controller may still run",
            "scheduler route is not sufficient",
            "loopx_prompt_driven_case_cli_call_count",
            "loopx_prompt_driven_event_counts",
            "loopx_prompt_driven_lifecycle_observed",
            "loopx_prompt_driven_trace.public.json",
            "prompt_driven_loopx_lifecycle_absent",
            "loopx_case_scheduler_command_count",
            "loopx_case_rollout_event_counts",
            "loopx_case_rollout_trace.public.json",
            "main project goal or an unrelated peer lane",
            "benchflow_js_agent_runtime",
            "scripts/skillsbench_agent_runtime_layer.py",
            "scripts/terminal_bench_no_upload_smoke.py",
            "scripts/terminal_bench_compose_startup_reducer.py",
            "Classify pre-agent failures before comparing model or LoopX behavior",
            "invalid or unsafe run ids are launch-shape blockers",
            "runner materialization blocked",
            "job-materialization blockers",
            "Do not report them as agent failures",
            "scripts/skillsbench_verifier_prewarm_plan.py",
            "For SkillsBench, prove the verifier dependency substrate",
            "skillsbench_verifier_dependency_prewarm_required",
            "Do not repair that first by globally extending timeouts",
            "single-checkout invariant",
            "Do not rely on `PYTHONPATH` alone",
            "loopx_controller_trace.public.json",
            "app_server_goal_worker_traces/*.compact.json",
            "worker_prompt_received_no_turn_trace",
            ".loopx-upstream",
            "materialized copy",
            "**Auth**",
            "**Network**",
            "**Execution**",
            "loopback-only proxy or tunnel",
            "The reusable trick is the shape, not the private wiring",
            "### SSH Session Hygiene",
            "SSH multiplexed master",
            "ControlPath ~/.ssh/cm/%C",
            "ControlPersist 8h",
            "ssh -MNf",
            "Keep commands through the master connection mostly serial",
            "foreground SSH session",
            "tmux",
            "capture-pane",
            "## Split-Control Route",
            "fallback and research route",
            "### Cross-Family Compact Workflow Shape",
            "After one benchmark family has a live cloud-host smoke",
            "Copy the workflow shape",
            "Run the family-specific public-safe readiness surface",
            "Launch at most one no-upload case or task-free worker proof",
            "compact ready/blocker packet",
            "--host-local-acp-codex-exec-preflight",
            "--host-local-acp-launch",
            "--require-preinstalled-benchflow-agent-runtime",
            "--remote-command-file-bridge-probe",
            "canonical `loopx-product-mode` lifecycle readiness",
            "loopx/benchmark_adapters/agents_last_exam.py",
            "build_agents_last_exam_local_source_readiness",
            "build_agents_last_exam_task_material_readiness",
            "build_agents_last_exam_host_codex_cua_no_task_smoke",
            "build_agents_last_exam_validation_run_gate",
            "The public packet shape is the contract",
            "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count",
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count",
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count",
            "Prefer wrappers, reducers, and adapter-side compact builders",
            "Do not expand to more cases",
            "## Current Benchmark Families",
            "Terminal-Bench",
            "SkillsBench",
            "Agents' Last Exam",
            "Benchmark evidence must not include",
            "raw task text",
            "raw trajectories",
            "credentials",
            "uploads, submit paths, or leaderboard claims",
        ],
        source=DOC,
    )
    leaked = [snippet for snippet in FORBIDDEN_SNIPPETS if snippet in doc]
    assert not leaked, leaked

    readme = README.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")
    tasks = TASKS.read_text(encoding="utf-8")
    require(readme, ["docs/benchmark-developer-workflow.md"], source=README)
    require(docs_index, ["benchmark-developer-workflow.md"], source=DOCS_INDEX)
    require(
        tasks,
        [
            "GH-C40",
            "bounded benchmark lifecycle/read-model seams",
            "raw logs, task text, verifier output, or host paths",
        ],
        source=TASKS,
    )

    print("benchmark-developer-workflow-doc-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
