#!/usr/bin/env python3
"""Prove Lark Explore sync routes to source and rejects projection shrinkage."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.explore.result_log import (  # noqa: E402
    NODE_KIND_AREA,
    NODE_STATUS_EXPLORING,
    append_explore_result_event,
    build_explore_node_event,
    explore_result_log_path,
)
from loopx.capabilities.issue_fix.explore_projection import (  # noqa: E402
    ISSUE_FIX_LANE_ID,
)
from loopx.capabilities.explore.activation import (  # noqa: E402
    sync_explore_graph_after_material_refresh,
)
from loopx.extensions.lark.presentation.explore_results import (  # noqa: E402
    sync_issue_fix_explore_on_material_change,
    write_lark_explore_local_config,
)
from loopx.extensions.lark.presentation.explore_singleflight import (  # noqa: E402
    explore_feishu_sync_singleflight,
)
from loopx.extensions.lark.presentation.explore_source_guard import (  # noqa: E402
    source_projection_coverage_guard,
)
from examples.lark_extension_test_support import (  # noqa: E402
    install_bundled_lark_extension,
)


GOAL_ID = "public-route-fixture"


def _write_registry(path: Path, *, runtime: Path, project: Path, state: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "repo": str(project),
                        "state_file": str(state),
                        "explore_graph": {"enabled": True},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _append_node(runtime: Path, *, node_id: str, title: str) -> None:
    result_log = explore_result_log_path(runtime, GOAL_ID)
    append_explore_result_event(
        result_log,
        build_explore_node_event(
            goal_id=GOAL_ID,
            node_id=node_id,
            title=title,
            node_kind=NODE_KIND_AREA,
            status=NODE_STATUS_EXPLORING,
            summary=f"Public fixture node {node_id}.",
        ),
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-lark-explore-source-route-") as tmp:
        root = Path(tmp)
        project = root / "project"
        project_loopx = project / ".loopx"
        state = project_loopx / "active-state.md"
        state.parent.mkdir(parents=True)
        state.write_text(
            "## User Todo / Owner Review Reading Queue\n\n## Agent Todo\n",
            encoding="utf-8",
        )
        source_runtime = project_loopx / "runtime"
        source_registry = project_loopx / "registry.json"
        _write_registry(
            source_registry,
            runtime=source_runtime,
            project=project,
            state=state,
        )

        shared_root = root / "shared" / ".loopx"
        shared_runtime = shared_root / "runtime"
        shared_registry = shared_root / "registry.global.json"
        _write_registry(
            shared_registry,
            runtime=shared_runtime,
            project=project,
            state=state,
        )
        shared_payload = json.loads(shared_registry.read_text(encoding="utf-8"))
        shared_payload["registry_role"] = "global-local"
        shared_payload["goals"][0]["source_registry"] = str(source_registry)
        shared_registry.write_text(json.dumps(shared_payload), encoding="utf-8")

        _append_node(
            source_runtime,
            node_id=ISSUE_FIX_LANE_ID,
            title="Canonical issue-fix lane",
        )
        _append_node(source_runtime, node_id="source_node", title="Canonical source")
        _append_node(
            shared_runtime,
            node_id=ISSUE_FIX_LANE_ID,
            title="Shared issue-fix lane",
        )
        _append_node(shared_runtime, node_id="shared_only", title="Stale shared node")

        config_path = project_loopx / "lark-explore.json"
        stale_config_path = shared_root / "lark-explore.json"
        baseline_config = {
            "board": {
                "base_token": "PUBLIC_FIXTURE_BASE",
                "tables": {
                    "nodes": "tblNodes",
                    "edges": "tblEdges",
                    "findings": "tblFindings",
                },
                "identity": "user",
            },
            "result_records": {
                f"{GOAL_ID}:nodes:source_node": "rec_source",
            },
            "automatic_projection_sync": {
                GOAL_ID: {
                    "canonical_rows_semantic_digest": "prior-digest",
                    "canonical_rows_readback_semantic_digest": "prior-digest",
                }
            },
        }
        write_lark_explore_local_config(config_path, baseline_config)
        assert not stale_config_path.exists()

        install_bundled_lark_extension(
            repo_root=ROOT,
            registry=shared_registry,
            runtime_root=shared_runtime,
        )

        cli_sync = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "--registry",
                str(shared_registry),
                "explore",
                "feishu-sync",
                "--goal-id",
                GOAL_ID,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cli_payload = json.loads(cli_sync.stdout)
        assert Path(cli_payload["config_path"]).resolve() == config_path.resolve(), cli_payload
        assert cli_payload["source_runtime_route"]["status"] == "source_registry", cli_payload
        assert cli_payload["extension_activation"]["doctor_verified"] is True, cli_payload
        assert cli_payload["extension_activation"]["required_permissions"] == [
            "lark.projection_sink.use"
        ], cli_payload
        assert not stale_config_path.exists()

        routed = sync_issue_fix_explore_on_material_change(
            registry_path=shared_registry,
            goal_id=GOAL_ID,
            project=project,
            state_file=state,
            execute=False,
        )
        projected_node_ids = {
            item["node_id"] for item in routed["projection"]["projection"]["nodes"]
        }
        assert routed["ok"] is True, routed
        assert routed["status"] == "would_sync", routed
        assert "source_node" in projected_node_ids, projected_node_ids
        assert "shared_only" not in projected_node_ids, projected_node_ids
        route = routed["projection"]["source_runtime_route"]
        assert route["status"] == "source_registry", route
        assert route["routed_to_source_registry"] is True, route
        assert not any("/" in str(value) for value in route.values() if value), route
        assert Path(routed["config_path"]).resolve() == config_path.resolve(), routed
        assert not stale_config_path.exists()

        activated = sync_explore_graph_after_material_refresh(
            registry_path=shared_registry,
            goal_id=GOAL_ID,
            project=project,
            state_file=state,
            external_sink_delivery_authorized=False,
            syncer=sync_issue_fix_explore_on_material_change,
        )
        assert activated["status"] == "external_sink_suppressed", activated
        assert activated["source_runtime_route"]["status"] == "source_registry", activated
        assert activated["delivery_postcondition"]["blocks_delivery"] is False, activated

        current_config = json.loads(config_path.read_text(encoding="utf-8"))
        current_config["automatic_projection_sync"][GOAL_ID].update(
            {
                "canonical_rows_semantic_digest": routed["semantic_digest"],
                "canonical_rows_readback_semantic_digest": routed[
                    "semantic_digest"
                ],
            }
        )
        write_lark_explore_local_config(config_path, current_config)
        with explore_feishu_sync_singleflight(config_path=config_path, execute=True):
            reentrant = sync_issue_fix_explore_on_material_change(
                registry_path=shared_registry,
                goal_id=GOAL_ID,
                project=project,
                state_file=state,
                execute=True,
            )
        assert reentrant["status"] == "unchanged", reentrant
        assert reentrant["row_readback_verified"] is True, reentrant
        assert not stale_config_path.exists()

        derived_edge_guard = source_projection_coverage_guard(
            local={
                "result_records": {
                    f"{GOAL_ID}:nodes:source_node": "rec_source",
                    f"{GOAL_ID}:edges:parent_retired": "rec_parent",
                }
            },
            projection={
                "nodes": [{"node_id": "source_node"}],
                "edges": [],
                "findings": [],
            },
            goal_id=GOAL_ID,
        )
        assert derived_edge_guard["ok"] is True, derived_edge_guard
        assert (
            derived_edge_guard["status"]
            == "covered_with_projection_derived_omissions"
        ), derived_edge_guard
        assert derived_edge_guard["missing_result_count"] == 0, derived_edge_guard
        assert (
            derived_edge_guard["retired_projection_derived_result_count"] == 1
        ), derived_edge_guard

        divergent_config = json.loads(config_path.read_text(encoding="utf-8"))
        divergent_config["result_records"][
            f"{GOAL_ID}:findings:registered_missing"
        ] = "rec_missing"
        write_lark_explore_local_config(config_path, divergent_config)
        before = config_path.read_text(encoding="utf-8")
        runner_calls: list[list[str]] = []

        def runner(args: list[str], **_: object) -> dict[str, object]:
            runner_calls.append(args)
            raise AssertionError("projection guard must run before connector writes")

        blocked = sync_issue_fix_explore_on_material_change(
            registry_path=shared_registry,
            goal_id=GOAL_ID,
            project=project,
            state_file=state,
            execute=True,
            runner=runner,
        )
        assert blocked["ok"] is False, blocked
        assert blocked["status"] == "source_projection_regression_blocked", blocked
        assert blocked["external_write_performed"] is False, blocked
        assert blocked["source_projection_guard"]["missing_result_count"] == 1, blocked
        assert blocked["source_projection_guard"]["missing_result_ids_sha256_16"], blocked
        assert blocked["source_runtime_route"]["status"] == "source_registry", blocked
        assert runner_calls == [], runner_calls
        assert config_path.read_text(encoding="utf-8") == before

    print("lark-explore-source-runtime-route-smoke: ok")


if __name__ == "__main__":
    main()
