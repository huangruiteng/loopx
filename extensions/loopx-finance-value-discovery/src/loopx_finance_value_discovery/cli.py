from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .market_regime import (
    FINANCE_MARKET_REGIME_INPUT_SCHEMA_VERSION,
    build_finance_market_regime_packet,
    render_finance_market_regime_markdown,
)
from .reducer import (
    FINANCE_VALUE_DISCOVERY_ERROR_SCHEMA_VERSION,
    build_finance_value_discovery_packet,
    render_finance_value_discovery_markdown,
)


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
    regime_parser = sub.add_parser(
        "market-signals",
        help="Classify market-specific pre-crash and post-drawdown repair signals.",
    )
    regime_parser.add_argument(
        "--input-json",
        required=True,
        help="Path to a finance_market_regime_input_v0 object, or '-' for stdin.",
    )
    regime_parser.add_argument(
        "--format", choices=("json", "markdown"), default="markdown"
    )
    return parser


def _build_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") == FINANCE_MARKET_REGIME_INPUT_SCHEMA_VERSION:
        return build_finance_market_regime_packet(payload)
    return build_finance_value_discovery_packet(payload)


def run(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if not arguments:
        try:
            payload = json.load(sys.stdin)
            if not isinstance(payload, Mapping):
                raise ValueError("provider input must be a JSON object")
            packet = _build_packet(payload)
        except Exception as exc:
            print(json.dumps(_error_packet(exc), sort_keys=True))
            return 1
        print(json.dumps(packet, sort_keys=True))
        return 0

    args = _direct_parser().parse_args(arguments)
    if args.doctor:
        return 0
    if args.command not in {"reduce", "market-signals"}:
        raise ValueError("use --doctor, reduce, or market-signals")
    try:
        payload = _load_json(args.input_json)
        packet = (
            build_finance_market_regime_packet(payload)
            if args.command == "market-signals"
            else build_finance_value_discovery_packet(payload)
        )
    except Exception as exc:
        print(json.dumps(_error_packet(exc), indent=2, sort_keys=True))
        return 1
    if args.format == "json":
        print(json.dumps(packet, indent=2, sort_keys=True))
    elif args.command == "market-signals":
        print(render_finance_market_regime_markdown(packet), end="")
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
