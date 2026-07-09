from __future__ import annotations

from argparse import Namespace

from ..benchmark_adapters.terminal_bench import (
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_PREFLIGHT_MODE,
)


def benchmark_run_ledger_classification(args: Namespace) -> str:
    if args.classification:
        return str(args.classification)
    if args.benchmark_name == "skillsbench":
        if args.skillsbench_result_json or args.skillsbench_result_root:
            return "skillsbench_official_benchflow_result_ingest_v0"
        return "skillsbench_" + str(args.skillsbench_route).replace("-", "_") + "_skeleton_v0"
    if args.harbor_job_dir:
        return "terminal_bench_harbor_runner_result_ingest_v0"
    if args.active_user_observation_fixture:
        return "terminal_bench_active_user_assisted_observation_fixture_v0"
    if args.active_user_assisted_treatment:
        return "terminal_bench_active_user_assisted_treatment_preflight_v0"
    if args.active_cli_bridge:
        return "terminal_bench_codex_loopx_active_cli_bridge_preflight_v0"
    if args.worker_cli_bridge_fixture:
        return "terminal_bench_codex_loopx_worker_cli_bridge_fixture_v0"
    if args.cli_bridge_contract:
        return "terminal_bench_codex_loopx_cli_bridge_contract_runner_fixture_v0"
    if args.preflight_guard:
        if args.mode == "codex-loopx":
            return "terminal_bench_codex_loopx_preflight_guard_v0"
        if args.mode == "hardened-codex":
            return TERMINAL_BENCH_HARDENED_CODEX_BASELINE_PREFLIGHT_MODE + "_v0"
        if args.mode == "codex-goal-mode":
            return "terminal_bench_codex_goal_mode_baseline_preflight_guard_v0"
        return "terminal_bench_managed_real_run_preflight_guard_v0"
    if args.fake_worker:
        if args.mode == "codex-loopx":
            return "terminal_bench_codex_loopx_fake_worker_v0"
        return "terminal_bench_cli_fake_worker_v0"
    if args.mode == "codex-loopx":
        return "terminal_bench_codex_loopx_dry_run_v0"
    if args.mode == "codex-goal-mode":
        return "terminal_bench_codex_goal_mode_baseline_dry_run_v0"
    return "terminal_bench_cli_dry_run_v0"
