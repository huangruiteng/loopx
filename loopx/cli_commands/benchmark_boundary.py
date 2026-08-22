from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path

from ..capabilities.benchmark_toolkit import (
    BENCHMARK_INTEGRITY_QUALIFICATION_SCHEMA_VERSION,
    BENCHMARK_SOURCE_REVISION_FENCE_SCHEMA_VERSION,
    BenchmarkJobReceiptState,
    BenchmarkRunnerOwnerState,
    BenchmarkSourceRevisionFenceError,
    build_benchmark_candidate_source_boundary,
    build_benchmark_integrity_qualification,
    build_benchmark_runtime_observation,
    compact_benchmark_source_revision_fence_receipt,
    filter_public_benchmark_artifact_paths,
    inspect_benchmark_source_revision_fence,
    verify_verifier_reward_file,
)

PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

BENCHMARK_TOOLKIT_COMMANDS = {
    "candidate-source-boundary",
    "classify-artifacts",
    "integrity-qualification",
    "runtime-observation",
    "source-revision-fence",
    "verify-verifier-reward",
}


def _read_json_object(path_text: str, label: str) -> dict[str, object]:
    raw = (
        sys.stdin.read()
        if path_text == "-"
        else Path(path_text).expanduser().read_text(encoding="utf-8")
    )
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise TypeError(f"{label} must contain a JSON object")
    return loaded


def _render_artifact_filter(payload: dict[str, object]) -> str:
    return (
        "# Benchmark Artifact Boundary\n\n"
        f"- Allowed: `{payload.get('allowed_to_read_count')}`\n"
        f"- Blocked: `{payload.get('blocked_count')}`\n"
        f"- Full paths recorded: `{payload.get('path_recorded')}`\n"
    )


def _render_candidate_boundary(payload: dict[str, object]) -> str:
    return (
        "# Benchmark Candidate Source Boundary\n\n"
        f"- Clean: `{payload.get('clean')}`\n"
        f"- Allowed: `{payload.get('allowed_source_count')}`\n"
        f"- Blocked: `{payload.get('blocked_source_count')}`\n"
        f"- Full paths recorded: `{payload.get('path_recorded')}`\n"
    )


def _render_integrity(payload: dict[str, object]) -> str:
    blockers = payload.get("blockers")
    blocker_text = ""
    if isinstance(blockers, list) and blockers:
        blocker_text = (
            "- Blockers: " + ", ".join(f"`{item}`" for item in blockers) + "\n"
        )
    return (
        "# Benchmark Integrity Qualification\n\n"
        f"- Classification: `{payload.get('classification')}`\n"
        f"- Integrity qualified: `{payload.get('integrity_qualified')}`\n"
        f"- Score claim eligible: `{payload.get('score_claim_eligible')}`\n"
        f"- Cheating detected: `{payload.get('benchmark_cheating_detected')}`\n"
        + blocker_text
    )


def _render_source_revision_fence(payload: dict[str, object]) -> str:
    return (
        "# Benchmark Source Revision Fence\n\n"
        f"- Admitted: `{payload.get('admitted')}`\n"
        f"- Reason: `{payload.get('reason_code')}`\n"
        f"- Source clean: `{payload.get('source_clean')}`\n"
        f"- Local matches expected: `{payload.get('local_matches_expected')}`\n"
        "- Observed reference matches expected: "
        f"`{payload.get('observed_reference_matches_expected')}`\n"
        f"- Source path recorded: `{payload.get('source_path_recorded')}`\n"
        f"- Revision values recorded: `{payload.get('revision_values_recorded')}`\n"
    )


def _render_runtime_observation(payload: dict[str, object]) -> str:
    return (
        "# Benchmark Runtime Observation\n\n"
        f"- Classification: `{payload.get('classification')}`\n"
        f"- Healthy active: `{payload.get('healthy_active')}`\n"
        f"- Reconciliation required: `{payload.get('reconciliation_required')}`\n"
        f"- Recommended transition: `{payload.get('recommended_transition')}`\n"
        "- Admission ledger alone proves liveness: `False`\n"
    )


def register_benchmark_boundary_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    artifact_parser = benchmark_subparsers.add_parser(
        "classify-artifacts",
        help="Classify compact benchmark artifact paths without reading files.",
    )
    add_subcommand_format(artifact_parser)
    artifact_parser.add_argument("artifact_paths", nargs="+")
    artifact_parser.add_argument("--allow-public-filename", action="append", default=[])

    source_parser = benchmark_subparsers.add_parser(
        "candidate-source-boundary",
        help="Reject raw/private candidate-selection sources before reading them.",
    )
    add_subcommand_format(source_parser)
    source_parser.add_argument("source_paths", nargs="+")
    source_parser.add_argument("--allow-public-filename", action="append", default=[])
    source_parser.add_argument("--require-clean", action="store_true")

    revision_parser = benchmark_subparsers.add_parser(
        "source-revision-fence",
        help="Fail closed when a clean pinned source no longer matches its ref head.",
    )
    add_subcommand_format(revision_parser)
    revision_parser.add_argument("--source-checkout", required=True)
    revision_parser.add_argument("--expected-revision", required=True)
    revision_parser.add_argument("--observed-reference-revision", required=True)
    revision_parser.add_argument("--require-admitted", action="store_true")

    runtime_parser = benchmark_subparsers.add_parser(
        "runtime-observation",
        help="Classify exact-job runtime evidence without trusting ledger occupancy.",
    )
    add_subcommand_format(runtime_parser)
    runtime_parser.add_argument("--admission-active", action="store_true")
    runtime_parser.add_argument(
        "--job-receipt-state",
        choices=[item.value for item in BenchmarkJobReceiptState],
        required=True,
    )
    runtime_parser.add_argument(
        "--runner-owner-state",
        choices=[item.value for item in BenchmarkRunnerOwnerState],
        required=True,
    )
    runtime_parser.add_argument("--terminal-result-present", action="store_true")
    runtime_parser.add_argument("--typed-fatal-runner-error", action="store_true")
    runtime_parser.add_argument("--require-healthy", action="store_true")

    integrity_parser = benchmark_subparsers.add_parser(
        "integrity-qualification",
        help="Reduce private trajectory and runner attestations to a compact receipt.",
    )
    add_subcommand_format(integrity_parser)
    integrity_parser.add_argument("--trajectory-json", required=True)
    integrity_parser.add_argument("--runtime-attestation-json", required=True)
    integrity_parser.add_argument("--policy-json")
    integrity_parser.add_argument("--sensitive-value-env", action="append", default=[])
    integrity_parser.add_argument("--require-qualified", action="store_true")

    reward_parser = benchmark_subparsers.add_parser(
        "verify-verifier-reward",
        help="Validate a verifier reward.json against the numeric-only contract.",
    )
    add_subcommand_format(reward_parser)
    reward_parser.add_argument("reward_json", help="Path to a verifier reward.json.")
    reward_parser.add_argument("--require-valid", action="store_true")


def _invalid_integrity_input() -> dict[str, object]:
    return {
        "ok": False,
        "schema_version": BENCHMARK_INTEGRITY_QUALIFICATION_SCHEMA_VERSION,
        "classification": "trajectory_audit_input_invalid",
        "integrity_qualified": False,
        "integrity_countable": False,
        "score_claim_eligible": False,
        "score_claim_countable": False,
        "matched_pair_countable": False,
        "benchmark_cheating_detected": False,
        "blockers": ["benchmark_integrity_input_invalid"],
        "public_boundary": {
            "raw_content_recorded": False,
            "input_paths_recorded": False,
            "sensitive_values_recorded": False,
        },
    }


def _render_reward_contract(payload: dict[str, object]) -> str:
    return (
        "# Verifier Reward Contract\n\n"
        f"- Valid: `{payload.get('valid')}`\n"
        f"- Reason: `{payload.get('reason_code')}`\n"
        f"- Entries: `{payload.get('entry_count')}`\n"
        f"- Invalid keys: `{','.join(payload.get('invalid_keys') or [])}`\n"
    )


def _invalid_source_revision_fence_input() -> dict[str, object]:
    return {
        "schema_version": BENCHMARK_SOURCE_REVISION_FENCE_SCHEMA_VERSION,
        "admitted": False,
        "reason_code": "source_revision_fence_input_invalid",
        "source_clean": False,
        "local_matches_expected": False,
        "observed_reference_matches_expected": False,
        "source_path_recorded": False,
        "revision_values_recorded": False,
        "network_access_performed": False,
        "write_performed": False,
    }


def handle_benchmark_boundary_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in BENCHMARK_TOOLKIT_COMMANDS:
        return None

    if args.benchmark_command == "classify-artifacts":
        payload = filter_public_benchmark_artifact_paths(
            args.artifact_paths,
            extra_public_filenames=args.allow_public_filename,
        )
        print_payload(payload, output_format(args), _render_artifact_filter)
        return 0

    if args.benchmark_command == "candidate-source-boundary":
        payload = build_benchmark_candidate_source_boundary(
            args.source_paths,
            extra_public_filenames=args.allow_public_filename,
        )
        print_payload(payload, output_format(args), _render_candidate_boundary)
        return 1 if args.require_clean and not payload.get("clean") else 0

    if args.benchmark_command == "source-revision-fence":
        try:
            fence = inspect_benchmark_source_revision_fence(
                args.source_checkout,
                expected_revision=args.expected_revision,
                observed_reference_revision=args.observed_reference_revision,
            )
            payload = compact_benchmark_source_revision_fence_receipt(fence)
        except BenchmarkSourceRevisionFenceError:
            payload = _invalid_source_revision_fence_input()
        print_payload(payload, output_format(args), _render_source_revision_fence)
        return 1 if args.require_admitted and not payload.get("admitted") else 0

    if args.benchmark_command == "runtime-observation":
        payload = build_benchmark_runtime_observation(
            admission_active=args.admission_active,
            job_receipt_state=args.job_receipt_state,
            runner_owner_state=args.runner_owner_state,
            terminal_result_present=args.terminal_result_present,
            typed_fatal_runner_error=args.typed_fatal_runner_error,
        )
        print_payload(payload, output_format(args), _render_runtime_observation)
        return 1 if args.require_healthy and not payload.get("healthy_active") else 0

    if args.benchmark_command == "verify-verifier-reward":
        if args.reward_json == "-":
            raise ValueError("verify-verifier-reward requires a file path")
        payload = verify_verifier_reward_file(args.reward_json)
        print_payload(payload, output_format(args), _render_reward_contract)
        return 1 if args.require_valid and not payload.get("valid") else 0

    try:
        trajectory = _read_json_object(args.trajectory_json, "--trajectory-json")
        attestation = _read_json_object(
            args.runtime_attestation_json,
            "--runtime-attestation-json",
        )
        policy = (
            _read_json_object(args.policy_json, "--policy-json")
            if args.policy_json
            else None
        )
        sensitive_values: list[str] = []
        for env_name in args.sensitive_value_env:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name):
                raise ValueError("invalid sensitive value environment name")
            value = os.environ.get(env_name)
            if not value:
                raise ValueError("missing sensitive value environment variable")
            sensitive_values.append(value)
        payload = build_benchmark_integrity_qualification(
            trajectory=trajectory,
            runtime_attestation=attestation,
            policy=policy,
            sensitive_values=sensitive_values,
        )
    except (OSError, UnicodeError, TypeError, ValueError):
        payload = _invalid_integrity_input()
    print_payload(payload, output_format(args), _render_integrity)
    if not payload.get("ok"):
        return 1
    return 1 if args.require_qualified and not payload.get("integrity_qualified") else 0
