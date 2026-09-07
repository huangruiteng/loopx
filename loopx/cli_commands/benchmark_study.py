from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..capabilities.benchmark_toolkit import (
    build_benchmark_study_dashboard,
    build_benchmark_upload_envelope,
    normalize_benchmark_study_manifest,
    normalize_benchmark_upload_envelope,
    read_benchmark_local_upload_records,
    read_benchmark_upload_receipt,
    simulate_benchmark_upload,
)
from ..capabilities.benchmark_toolkit.behavior_finding import (
    build_benchmark_behavior_report,
)

PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]], None
]
OutputFormat = Callable[[argparse.Namespace], str]

BENCHMARK_STUDY_COMMANDS = {
    "study-validate",
    "upload-envelope",
    "upload-local",
    "upload-readback",
    "study-dashboard",
    "behavior-report",
}


def _read_object(path_text: str, label: str) -> dict[str, Any]:
    raw = (
        sys.stdin.read()
        if path_text == "-"
        else Path(path_text).expanduser().read_text(encoding="utf-8")
    )
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError(f"{label} must contain a JSON object")
    return payload


def _render(payload: dict[str, object]) -> str:
    status = payload.get("status", payload.get("disposition"))
    if status is None:
        status = (
            "valid"
            if payload.get("schema_version") == "benchmark_study_manifest_v0"
            else "ok"
        )
    return (
        "# Benchmark Study Contract\n\n"
        f"- Schema: `{payload.get('schema_version')}`\n"
        f"- Status: `{status}`\n"
        f"- Write performed: `{payload.get('write_performed', False)}`\n"
        f"- External write performed: `{payload.get('external_write_performed', False)}`\n"
        f"- Network access performed: `{payload.get('network_access_performed', False)}`\n"
    )


def register_benchmark_study_commands(
    subparsers: argparse._SubParsersAction,
    add_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    validate = subparsers.add_parser(
        "study-validate", help="Validate one provider-neutral benchmark study manifest."
    )
    add_format(validate)
    validate.add_argument("--manifest-json", required=True)
    validate.set_defaults(benchmark_study_parser=validate)

    envelope = subparsers.add_parser(
        "upload-envelope", help="Build and validate one public-safe upload envelope."
    )
    add_format(envelope)
    envelope.add_argument("--payload-json", required=True)
    envelope.add_argument(
        "--record-kind",
        choices=[
            "study_manifest",
            "experiment_board_row",
            "case_insight_projection",
            "runtime_observation",
            "behavior_finding",
        ],
        required=True,
    )
    for name in (
        "producer-id",
        "producer-version",
        "benchmark-id",
        "study-id",
        "idempotency-key",
        "observed-at",
        "source-revision",
    ):
        envelope.add_argument(f"--{name}", required=True)
    envelope.add_argument("--supersedes-record-id")
    envelope.set_defaults(benchmark_study_parser=envelope)

    upload = subparsers.add_parser(
        "upload-local",
        help="Preview or write one envelope to an explicit local simulation store.",
    )
    add_format(upload)
    upload.add_argument("--envelope-json", required=True)
    upload.add_argument("--store", required=True)
    upload.add_argument("--execute", action="store_true")
    upload.set_defaults(benchmark_study_parser=upload)

    readback = subparsers.add_parser(
        "upload-readback",
        help="Verify one digest-bound record in a local simulation store.",
    )
    add_format(readback)
    readback.add_argument("--store", required=True)
    readback.add_argument("--record-id", required=True)
    readback.set_defaults(benchmark_study_parser=readback)

    dashboard = subparsers.add_parser(
        "study-dashboard",
        help="Derive a read-only campaign/arm/case/run data packet from local records.",
    )
    add_format(dashboard)
    dashboard.add_argument("--manifest-json", required=True)
    dashboard.add_argument("--store", required=True)
    dashboard.add_argument(
        "--four-arm-contract-json",
        help="Optional qualified four-arm contract for factorial projections.",
    )
    dashboard.set_defaults(benchmark_study_parser=dashboard)

    behavior = subparsers.add_parser(
        "behavior-report",
        help="Project exploratory findings without a full result upload.",
    )
    add_format(behavior)
    behavior.add_argument("--store", required=True)
    behavior.add_argument("--benchmark-id", required=True)
    behavior.add_argument("--study-id", required=True)
    behavior.set_defaults(benchmark_study_parser=behavior)


def handle_benchmark_study_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in BENCHMARK_STUDY_COMMANDS:
        return None
    try:
        if args.benchmark_command == "study-validate":
            payload = normalize_benchmark_study_manifest(
                _read_object(args.manifest_json, "--manifest-json")
            )
        elif args.benchmark_command == "upload-envelope":
            payload = build_benchmark_upload_envelope(
                _read_object(args.payload_json, "--payload-json"),
                record_kind=args.record_kind,
                producer_id=args.producer_id,
                producer_version=args.producer_version,
                benchmark_id=args.benchmark_id,
                study_id=args.study_id,
                idempotency_key=args.idempotency_key,
                observed_at=args.observed_at,
                source_revision=args.source_revision,
                supersedes_record_id=args.supersedes_record_id,
            )
        elif args.benchmark_command == "upload-local":
            payload = simulate_benchmark_upload(
                args.store,
                normalize_benchmark_upload_envelope(
                    _read_object(args.envelope_json, "--envelope-json")
                ),
                execute=args.execute,
            )
        elif args.benchmark_command == "upload-readback":
            payload = read_benchmark_upload_receipt(
                args.store, record_id=args.record_id
            )
        elif args.benchmark_command == "behavior-report":
            payload = build_benchmark_behavior_report(
                read_benchmark_local_upload_records(args.store),
                benchmark_id=args.benchmark_id,
                study_id=args.study_id,
            )
        else:
            manifest = normalize_benchmark_study_manifest(
                _read_object(args.manifest_json, "--manifest-json")
            )
            records = read_benchmark_local_upload_records(args.store)
            four_arm_contract = (
                _read_object(
                    args.four_arm_contract_json,
                    "--four-arm-contract-json",
                )
                if args.four_arm_contract_json
                else None
            )
            payload = build_benchmark_study_dashboard(
                manifest,
                records,
                four_arm_contract=four_arm_contract,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        args.benchmark_study_parser.error("invalid public-safe benchmark study input")
    print_payload(payload, output_format(args), _render)
    return 0
