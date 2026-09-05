from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .contract import doctor, retrieve


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="loopx-obelisk")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--obelisk-bin", default="obelisk")
    parser.add_argument("--timeout-seconds", type=float, default=30)
    return parser


def _emit(payload: Any) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.doctor:
            doctor(
                obelisk_bin=args.obelisk_bin,
                timeout_seconds=args.timeout_seconds,
            )
            return 0
        request = json.load(sys.stdin)
        _emit(
            retrieve(
                request,
                obelisk_bin=args.obelisk_bin,
                timeout_cap_seconds=args.timeout_seconds,
            )
        )
        return 0
    except Exception:
        _emit({"ok": False, "error": "obelisk_provider_unavailable"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
