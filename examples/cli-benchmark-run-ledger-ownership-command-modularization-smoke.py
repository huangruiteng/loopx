#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"expected to find {needle!r} in source")


def assert_markers_owned_by(
    *,
    parent_source: str,
    owner_source: str,
    markers: list[str],
    parent_name: str,
) -> None:
    for marker in markers:
        if marker in parent_source:
            raise AssertionError(f"{marker} leaked back into {parent_name}")
        assert_contains(owner_source, marker)


def main() -> int:
    sources = {
        "cli": (ROOT / "loopx" / "cli.py").read_text(encoding="utf-8"),
        "init": (ROOT / "loopx" / "cli_commands" / "__init__.py").read_text(
            encoding="utf-8"
        ),
        "dispatch": (
            ROOT / "loopx" / "cli_commands" / "benchmark_dispatch.py"
        ).read_text(encoding="utf-8"),
        "ledger": (
            ROOT / "loopx" / "cli_commands" / "benchmark_run_ledger.py"
        ).read_text(encoding="utf-8"),
        "maintenance": (
            ROOT / "loopx" / "cli_commands" / "benchmark_run_ledger_maintenance.py"
        ).read_text(encoding="utf-8"),
        "maintenance_registration": (
            ROOT
            / "loopx"
            / "cli_commands"
            / "benchmark_run_ledger_maintenance_registration.py"
        ).read_text(encoding="utf-8"),
        "maintenance_rendering": (
            ROOT
            / "loopx"
            / "cli_commands"
            / "benchmark_run_ledger_maintenance_rendering.py"
        ).read_text(encoding="utf-8"),
        "case_analysis": (
            ROOT
            / "loopx"
            / "cli_commands"
            / "benchmark_run_ledger_case_analysis.py"
        ).read_text(encoding="utf-8"),
        "parity": (
            ROOT / "loopx" / "cli_commands" / "benchmark_run_ledger_parity.py"
        ).read_text(encoding="utf-8"),
    }

    for marker in [
        "benchmark_run_parser = benchmark_sub.add_parser",
        "benchmark_run_ledger_upsert_parser = benchmark_sub.add_parser",
        "benchmark_case_analysis_candidates_parser = benchmark_sub.add_parser",
        "def render_benchmark_run_ledger_upsert_markdown",
        "build_terminal_bench_benchmark_run(",
        "build_case_analysis_candidate_report(",
        'if args.benchmark_command == "run":',
    ]:
        if marker in sources["cli"]:
            raise AssertionError(f"{marker} leaked back into loopx/cli.py")

    for marker in [
        "register_benchmark_run_ledger_commands",
        "handle_benchmark_run_ledger_command",
        "register_benchmark_run_ledger_case_analysis_commands",
        "handle_benchmark_run_ledger_case_analysis_command",
        "register_benchmark_run_ledger_maintenance_commands",
        "handle_benchmark_run_ledger_maintenance_command",
        "register_benchmark_run_ledger_parity_commands",
        "handle_benchmark_run_ledger_parity_command",
    ]:
        assert_contains(sources["init"], marker)

    for marker in [
        "register_benchmark_run_ledger_commands(",
        "handle_benchmark_run_ledger_command(",
    ]:
        assert_contains(sources["dispatch"], marker)

    for marker in [
        "BENCHMARK_RUN_LEDGER_COMMANDS",
        "register_benchmark_run_ledger_case_analysis_commands(benchmark_subparsers)",
        "handle_benchmark_run_ledger_case_analysis_command(",
        "register_benchmark_run_ledger_parity_commands(",
        "handle_benchmark_run_ledger_parity_command(",
        "register_benchmark_run_ledger_maintenance_commands(benchmark_subparsers)",
        "handle_benchmark_run_ledger_maintenance_command(",
    ]:
        assert_contains(sources["ledger"], marker)

    assert_markers_owned_by(
        parent_source=sources["ledger"],
        owner_source=sources["maintenance_registration"],
        markers=[
            "benchmark_run_ledger_upsert_parser = benchmark_subparsers.add_parser",
            "benchmark_run_ledger_check_parser = benchmark_subparsers.add_parser",
        ],
        parent_name="benchmark_run_ledger.py",
    )
    assert_markers_owned_by(
        parent_source=sources["ledger"],
        owner_source=sources["maintenance_rendering"],
        markers=[
            "def render_benchmark_run_ledger_upsert_markdown",
            "def render_benchmark_run_ledger_check_markdown",
        ],
        parent_name="benchmark_run_ledger.py",
    )
    assert_markers_owned_by(
        parent_source=sources["ledger"],
        owner_source=sources["maintenance"],
        markers=[
            'if args.benchmark_command == "run-ledger-upsert":',
            'if args.benchmark_command == "run-ledger-check":',
            "compact_benchmark_post_launch_materialization",
            "check_benchmark_run_ledger_drift(",
        ],
        parent_name="benchmark_run_ledger.py",
    )
    assert_markers_owned_by(
        parent_source=sources["ledger"],
        owner_source=sources["case_analysis"],
        markers=[
            "benchmark_case_analysis_candidates_parser = benchmark_subparsers.add_parser",
            "def render_benchmark_case_analysis_candidates_markdown",
            'if args.benchmark_command == "case-analysis-candidates":',
            "build_case_analysis_candidate_report(",
            "apply_accepted_case_analysis_records(",
            "render_case_analysis_markdown(",
        ],
        parent_name="benchmark_run_ledger.py",
    )
    assert_markers_owned_by(
        parent_source=sources["ledger"],
        owner_source=sources["parity"],
        markers=[
            "benchmark_parity_check_parser = benchmark_subparsers.add_parser",
            'if args.benchmark_command == "parity-check":',
            "build_codex_app_parity_posthoc_check(",
            "render_codex_app_parity_posthoc_check_markdown(",
        ],
        parent_name="benchmark_run_ledger.py",
    )

    print("cli-benchmark-run-ledger-ownership-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
