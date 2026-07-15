#!/usr/bin/env python3
"""Verify cross-role token isolation and batch-final Explore marker readback."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.presentation.sinks.lark import explore_results  # noqa: E402


def _bundle(
    _: Mapping[str, Any], policy: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    del policy
    roles = {}
    for role in ("canonical", "executive"):
        roles[role] = {
            "view_role": role,
            "nodes": [{"node_id": f"{role}_node"}],
            "edges": [],
            "stage_views": [
                {
                    "stage_index": 1,
                    "node_ids": [f"{role}_node"],
                    "mermaid": "flowchart TB",
                    "svg": "<svg></svg>",
                }
            ],
        }
    return {
        "presentation_mode": "dual_view",
        "reason_codes": ["readability_check_failed"],
        "source_digest": "public-source-digest",
        "source_revision": "public-source-revision",
        **roles,
    }


def _sink(token: str) -> dict[str, Any]:
    return {
        "stage_capacity": 14,
        "board_style": "semantic_lane_columns",
        "stage_whiteboards": [{"stage_index": 1, "whiteboard_token": token}],
    }


def main() -> int:
    original_bundle = explore_results.build_explore_presentation_bundle
    original_ensure = explore_results.ensure_stage_whiteboards
    original_sync = explore_results.sync_explore_visual_to_lark
    original_settle = explore_results.settle_visual_stage_readbacks
    writes: list[str] = []
    settlements: list[list[str]] = []

    def ensure(
        config: Any,
        *,
        role: str,
        role_sink: Mapping[str, Any],
        stage_views: list[Mapping[str, Any]],
        **_: Any,
    ) -> tuple[dict[int, dict[str, Any]], list[Any], list[Any], dict[str, Any], None]:
        del config, role, stage_views
        item = dict(role_sink["stage_whiteboards"][0])
        return {1: item}, [], [], {"required": False}, None

    def sync(
        config: Any,
        *,
        view_key: str,
        visual_sink: Mapping[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        del config
        writes.append(view_key)
        marker = f"marker:{view_key}"
        return {
            "ok": False,
            "status": "publish_unverified",
            "published": False,
            "retryable": True,
            "delivery_digest": view_key,
            "board_style": "semantic_lane_columns",
            "renderer": "mermaid",
            "command": {"ok": True},
            "readback": {"expected_marker": marker, "retryable": True},
        }

    def settle(*, stage_targets: list[tuple[dict[str, Any], str]], **_: Any) -> None:
        settlements.append(
            [str(item[0]["readback"]["expected_marker"]) for item in stage_targets]
        )
        assert writes == ["canonical_stage_01", "executive_stage_01"], writes
        for result, _token in stage_targets:
            result.update(
                ok=True,
                status="published",
                published=True,
                retryable=False,
                readback={"ok": True, "verified": True},
            )

    explore_results.build_explore_presentation_bundle = _bundle
    explore_results.ensure_stage_whiteboards = ensure
    explore_results.sync_explore_visual_to_lark = sync
    explore_results.settle_visual_stage_readbacks = settle
    try:
        config = explore_results.LarkExploreConfig(
            **{"base_" + "token": "PUBLIC_BASE"},
            table_ids={"nodes": "N", "edges": "E", "findings": "F"},
        )
        with tempfile.TemporaryDirectory(prefix="loopx-visual-integrity-") as tmp:
            config_path = Path(tmp) / "lark-explore.json"
            conflict = explore_results.sync_explore_visuals_to_lark(
                config,
                projection={},
                visual_sinks={
                    "canonical": _sink("shared-board"),
                    "executive": _sink("shared-board"),
                },
                config_path=config_path,
                execute=True,
            )
            assert conflict["status"] == "configuration_conflict", conflict
            assert (
                conflict["views"]["canonical"]["status"]
                == "stage_whiteboard_token_conflict"
            ), conflict
            assert "shared-board" not in str(conflict), conflict
            assert not writes and not settlements, (writes, settlements)

            delivered = explore_results.sync_explore_visuals_to_lark(
                config,
                projection={},
                visual_sinks={
                    "canonical": _sink("canonical-board"),
                    "executive": _sink("executive-board"),
                },
                config_path=config_path,
                execute=True,
            )
            assert delivered["ok"] is True and delivered["status"] == "published", (
                delivered
            )
            assert settlements == [
                ["marker:canonical_stage_01", "marker:executive_stage_01"]
            ], settlements
            assert all(view["ok"] is True for view in delivered["views"].values()), (
                delivered
            )
    finally:
        explore_results.build_explore_presentation_bundle = original_bundle
        explore_results.ensure_stage_whiteboards = original_ensure
        explore_results.sync_explore_visual_to_lark = original_sync
        explore_results.settle_visual_stage_readbacks = original_settle
    print("explore visual cross-role integrity smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
