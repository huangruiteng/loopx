from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .attribution import (
    FINANCE_BETA_ATTRIBUTION_INPUT_SCHEMA_VERSION,
    build_finance_beta_attribution,
    replay_finance_beta_attribution,
)
from .contract import FINANCE_CASE_INPUT_SCHEMA_VERSION
from .metric_packs import (
    FINANCE_METRIC_PACK_INPUT_SCHEMA_VERSION,
    build_finance_metric_pack_evaluation,
    list_finance_metric_packs,
    replay_finance_metric_pack_evaluation,
)
from .reducer import (
    FINANCE_VALUE_DISCOVERY_ERROR_SCHEMA_VERSION,
    build_finance_value_discovery_packet,
    render_finance_value_discovery_markdown,
)
from .replay import (
    build_finance_case_evaluation,
    replay_finance_case_evaluation,
)
from .presentation_compat import presentation_api_error


FINANCE_RESEARCH_DASHBOARD_INPUT_SCHEMA_VERSION = "finance_research_dashboard_input_v0"


def _load_json(path_text: str) -> dict[str, Any]:
    raw = (
        sys.stdin.read()
        if path_text == "-"
        else Path(path_text).read_text(encoding="utf-8")
    )
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("finance value-discovery input must be a JSON object")
    return payload


def _error_packet(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, json.JSONDecodeError):
        error = "finance value-discovery input must be valid JSON"
    elif isinstance(exc, OSError):
        error = "finance value-discovery input file could not be read"
    else:
        error = str(exc)
    return {
        "ok": False,
        "schema_version": FINANCE_VALUE_DISCOVERY_ERROR_SCHEMA_VERSION,
        "mode": "finance-value-discovery",
        "error": error,
        "external_reads_performed": False,
        "external_writes_performed": False,
        "investment_advice": False,
        "trading_allowed": False,
        "continuous_watch_allowed": False,
    }


def _direct_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="loopx-finance-value-discovery")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--doctor", action="store_true")
    sub = parser.add_subparsers(dest="command")
    reduce_parser = sub.add_parser(
        "reduce",
        help="Reduce frozen public-safe evidence into a bounded research packet.",
    )
    reduce_parser.add_argument(
        "--input-json",
        required=True,
        help="Path to a finance_value_discovery_input_v0 object, or '-' for stdin.",
    )
    reduce_parser.add_argument(
        "--format", choices=("json", "markdown"), default="markdown"
    )
    evaluate_parser = sub.add_parser(
        "evaluate",
        help="Evaluate ordered finance gates over frozen public evidence.",
    )
    evaluate_parser.add_argument(
        "--input-json",
        required=True,
        help=f"Path to a {FINANCE_CASE_INPUT_SCHEMA_VERSION} object, or '-' for stdin.",
    )
    replay_parser = sub.add_parser(
        "replay",
        help="Verify a prior finance gate evaluation byte-for-byte.",
    )
    replay_parser.add_argument("--input-json", required=True)
    replay_parser.add_argument("--expected-json", required=True)
    beta_parser = sub.add_parser(
        "attribute-beta",
        help="Decompose a frozen total move into six explained layers and residual.",
    )
    beta_parser.add_argument("--input-json", required=True)
    beta_replay_parser = sub.add_parser(
        "replay-beta",
        help="Verify a prior beta attribution byte-for-byte.",
    )
    beta_replay_parser.add_argument("--input-json", required=True)
    beta_replay_parser.add_argument("--expected-json", required=True)
    pack_parser = sub.add_parser(
        "evaluate-pack",
        help="Evaluate a case against an installed industry metric pack.",
    )
    pack_parser.add_argument("--input-json", required=True)
    pack_replay_parser = sub.add_parser(
        "replay-pack",
        help="Verify a prior metric-pack evaluation byte-for-byte.",
    )
    pack_replay_parser.add_argument("--input-json", required=True)
    pack_replay_parser.add_argument("--expected-json", required=True)
    sub.add_parser("list-packs", help="List bundled industry metric packs.")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if not arguments:
        try:
            payload = json.load(sys.stdin)
            if not isinstance(payload, Mapping):
                raise ValueError("provider input must be a JSON object")
            schema_version = payload.get("schema_version")
            if schema_version == FINANCE_CASE_INPUT_SCHEMA_VERSION:
                packet = build_finance_case_evaluation(payload)
            elif schema_version == FINANCE_BETA_ATTRIBUTION_INPUT_SCHEMA_VERSION:
                packet = build_finance_beta_attribution(payload)
            elif schema_version == FINANCE_METRIC_PACK_INPUT_SCHEMA_VERSION:
                packet = build_finance_metric_pack_evaluation(payload)
            elif schema_version == FINANCE_RESEARCH_DASHBOARD_INPUT_SCHEMA_VERSION:
                from .dashboard import build_finance_research_dashboard_packet

                packet = build_finance_research_dashboard_packet(payload)
            else:
                packet = build_finance_value_discovery_packet(payload)
        except Exception as exc:
            print(json.dumps(_error_packet(exc), sort_keys=True))
            return 1
        print(json.dumps(packet, sort_keys=True))
        return 0

    args = _direct_parser().parse_args(arguments)
    if args.doctor:
        if error := presentation_api_error():
            print(json.dumps(_error_packet(RuntimeError(error)), sort_keys=True))
            return 1
        return 0
    try:
        if args.command == "reduce":
            packet = build_finance_value_discovery_packet(_load_json(args.input_json))
        elif args.command == "evaluate":
            packet = build_finance_case_evaluation(_load_json(args.input_json))
        elif args.command == "replay":
            packet = replay_finance_case_evaluation(
                _load_json(args.input_json),
                _load_json(args.expected_json),
            )
        elif args.command == "attribute-beta":
            packet = build_finance_beta_attribution(_load_json(args.input_json))
        elif args.command == "replay-beta":
            packet = replay_finance_beta_attribution(
                _load_json(args.input_json),
                _load_json(args.expected_json),
            )
        elif args.command == "evaluate-pack":
            packet = build_finance_metric_pack_evaluation(_load_json(args.input_json))
        elif args.command == "replay-pack":
            packet = replay_finance_metric_pack_evaluation(
                _load_json(args.input_json),
                _load_json(args.expected_json),
            )
        elif args.command == "list-packs":
            packet = list_finance_metric_packs()
        else:
            raise ValueError(
                "use --doctor, reduce, evaluate, replay, attribute-beta, "
                "replay-beta, evaluate-pack, replay-pack, or list-packs"
            )
    except Exception as exc:
        print(json.dumps(_error_packet(exc), indent=2, sort_keys=True))
        return 1
    if args.command != "reduce" or args.format == "json":
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(render_finance_value_discovery_markdown(packet), end="")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except Exception as exc:
        print(
            f"finance value-discovery extension failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
