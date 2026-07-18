from __future__ import annotations

import argparse
from importlib import import_module
import sys
from collections.abc import Sequence


REQUIRED_EXPORTS = {
    "loopx.extensions.lark.event_collector": (
        "inspect_lark_event_collector",
        "install_lark_event_collector",
        "plan_lark_event_collector",
    ),
    "loopx.extensions.lark.event_collector_runtime": ("run_lark_event_collector",),
    "loopx.extensions.lark.event_inbox": (
        "acknowledge_lark_event_inbox",
        "ingest_lark_event_inbox",
        "inspect_lark_event_inbox",
    ),
    "loopx.extensions.lark.inbox_reply": ("reply_lark_event_inbox",),
}


def doctor_lark_provider() -> None:
    for module_name, exports in REQUIRED_EXPORTS.items():
        module = import_module(module_name)
        missing = [
            name for name in exports if not callable(getattr(module, name, None))
        ]
        if missing:
            raise RuntimeError(
                f"Lark provider module `{module_name}` is missing exports {missing}"
            )


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoopX Lark extension provider.")
    parser.add_argument("--doctor", action="store_true")
    args = parser.parse_args(argv)
    if not args.doctor:
        raise ValueError(
            "the Lark subprocess protocol is not active; use the LoopX compatibility CLI"
        )
    doctor_lark_provider()
    return 0


def main() -> int:
    try:
        return run()
    except Exception as exc:
        print(f"LoopX Lark provider failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
