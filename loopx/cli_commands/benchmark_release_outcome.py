from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..control_plane.testing.release_outcome_baseline import (
    RELEASE_OUTCOME_BASELINE_SCHEMA_VERSION,
    build_release_outcome_baseline,
)
from ..control_plane.runtime.public_safety import public_safe_compact_text


def _public_error(exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return "manifest_invalid_json"
    if isinstance(exc, OSError):
        return "manifest_unreadable"
    if isinstance(exc, ValueError):
        return public_safe_compact_text(str(exc), limit=220) or "manifest_invalid"
    return "release_outcome_invalid_input"


def render_release_outcome_baseline_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Release Outcome Baseline",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- comparison_kind: `{payload.get('comparison_kind')}`",
        f"- baseline_ref: `{payload.get('baseline_ref')}`",
        f"- candidate_ref: `{payload.get('candidate_ref')}`",
        f"- eligible_for_owner_review: `{payload.get('eligible_for_owner_review')}`",
        f"- automatic_release_promotion_allowed: `{payload.get('automatic_release_promotion_allowed')}`",
    ]
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    if coverage:
        lines.extend(
            [
                f"- distinct_case_count: `{coverage.get('distinct_case_count')}`",
                f"- paired_attempt_count: `{coverage.get('paired_attempt_count')}`",
                f"- evidence_gaps: `{coverage.get('evidence_gaps')}`",
            ]
        )
    if payload.get("regressions") is not None:
        lines.append(f"- regressions: `{payload.get('regressions')}`")
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def register_benchmark_release_outcome_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = benchmark_subparsers.add_parser(
        "release-outcome-baseline",
        help=(
            "Reduce paired compact benchmark_result_v0 outcomes into a review-only "
            "release qualification receipt. This never runs a benchmark or model."
        ),
    )
    add_subcommand_format(parser)
    parser.add_argument(
        "--manifest-json",
        required=True,
        help=(
            "Path to a release_outcome_pair_manifest_v0 JSON object comparing "
            "a stable LoopX release with a distinct candidate revision."
        ),
    )
    parser.add_argument(
        "--require-owner-review-ready",
        action="store_true",
        help="Return non-zero unless the paired evidence is ready for owner review.",
    )


def handle_benchmark_release_outcome_command(
    args: argparse.Namespace,
    *,
    print_payload: Callable[..., None],
    output_format: Callable[..., str],
) -> int | None:
    if args.command != "benchmark" or args.benchmark_command != "release-outcome-baseline":
        return None
    try:
        raw = json.loads(Path(args.manifest_json).expanduser().read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("--manifest-json must contain a JSON object")
        payload = build_release_outcome_baseline(raw)
        payload["ok"] = not args.require_owner_review_ready or payload.get(
            "eligible_for_owner_review"
        ) is True
        if not payload["ok"]:
            payload["error"] = payload.get("decision") or "release_outcome_not_review_ready"
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": RELEASE_OUTCOME_BASELINE_SCHEMA_VERSION,
            "decision": "invalid_input",
            "eligible_for_owner_review": False,
            "automatic_release_promotion_allowed": False,
            "error": _public_error(exc),
            "read_boundary": {
                "compact_benchmark_results_only": True,
                "raw_task_text_read": False,
                "raw_trajectory_read": False,
                "raw_verifier_output_read": False,
                "local_paths_recorded": False,
                "model_api_invoked": False,
                "benchmark_execution_invoked": False,
                "release_mutation_invoked": False,
            },
        }
    print_payload(
        payload,
        output_format(args),
        render_release_outcome_baseline_markdown,
    )
    return 0 if payload.get("ok") else 1
