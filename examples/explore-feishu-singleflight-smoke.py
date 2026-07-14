#!/usr/bin/env python3
"""Prove overlapping Explore Feishu deliveries fail before remote writes."""

from __future__ import annotations

import argparse
import multiprocessing
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.cli_commands import explore as explore_cli  # noqa: E402
from loopx.presentation.sinks.lark.explore_results import (  # noqa: E402
    sync_issue_fix_explore_on_material_change,
)
from loopx.presentation.sinks.lark.explore_singleflight import (  # noqa: E402
    explore_feishu_sync_singleflight,
)


def _child_attempt(config_path: str, queue: multiprocessing.Queue) -> None:
    with explore_feishu_sync_singleflight(
        config_path=Path(config_path), execute=True
    ) as acquired:
        queue.put(acquired)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-explore-singleflight-") as tmp:
        root = Path(tmp)
        config_path = root / ".loopx" / "lark-explore.json"
        registry_path = root / ".loopx" / "registry.json"
        config_path.parent.mkdir(parents=True)
        sentinel = '{"sentinel":"unchanged"}\n'
        config_path.write_text(sentinel, encoding="utf-8")

        runner_calls: list[list[str]] = []

        def runner(args, cwd=None, timeout=None):
            runner_calls.append(list(args))
            raise AssertionError("busy sync must fail before connector calls")

        with explore_feishu_sync_singleflight(
            config_path=config_path, execute=True
        ) as acquired:
            assert acquired is True

            ctx = multiprocessing.get_context("spawn")
            queue = ctx.Queue()
            child = ctx.Process(
                target=_child_attempt,
                args=(str(config_path), queue),
            )
            child.start()
            child.join(timeout=10)
            assert child.exitcode == 0, child.exitcode
            assert queue.get(timeout=2) is False

            with explore_feishu_sync_singleflight(
                config_path=config_path, execute=False
            ) as dry_run_acquired:
                assert dry_run_acquired is True

            material = sync_issue_fix_explore_on_material_change(
                registry_path=registry_path,
                goal_id="fixture-goal",
                execute=True,
                runner=runner,
            )
            assert material["status"] == "sync_busy", material
            assert material["retryable"] is True, material
            assert material["external_write_performed"] is False, material

            captured: list[dict[str, object]] = []
            original_load_registry = explore_cli.load_registry
            original_resolve_runtime_root = explore_cli.resolve_runtime_root
            explore_cli.load_registry = lambda _path: {}
            explore_cli.resolve_runtime_root = lambda _registry, _arg: root
            try:
                result = explore_cli.handle_explore_command(
                    argparse.Namespace(
                        command="explore",
                        explore_command="feishu-sync",
                        config_path=str(config_path),
                        execute=True,
                    ),
                    registry_path=registry_path,
                    runtime_root_arg=None,
                    print_payload=lambda payload, _fmt, _renderer: captured.append(
                        payload
                    ),
                    output_format=lambda _args: "json",
                )
            finally:
                explore_cli.load_registry = original_load_registry
                explore_cli.resolve_runtime_root = original_resolve_runtime_root
            assert result == 1, result
            assert captured[0]["status"] == "sync_busy", captured
            assert captured[0]["visual_sync"]["status"] == (
                "not_attempted_sync_busy"
            ), captured
            assert config_path.read_text(encoding="utf-8") == sentinel
            assert runner_calls == []

        with explore_feishu_sync_singleflight(
            config_path=config_path, execute=True
        ) as acquired_after_release:
            assert acquired_after_release is True

    print("explore-feishu-singleflight-smoke: ok")


if __name__ == "__main__":
    main()
