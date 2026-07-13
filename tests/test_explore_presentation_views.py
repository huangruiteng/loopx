from __future__ import annotations

import json

import pytest

from loopx.presentation.explore_views import (
    PRESENTATION_MODE_CANONICAL_ONLY,
    PRESENTATION_MODE_DUAL_VIEW,
    build_explore_presentation_bundle,
    explore_source_digest,
    validate_explore_view_freshness,
)
from loopx.presentation.sinks.lark.explore_results import (
    LarkExploreConfig,
    configure_lark_explore_visual_sink,
    read_lark_explore_local_config,
    sync_explore_visual_to_lark,
    sync_explore_visuals_to_lark,
    write_lark_explore_local_config,
)


def _node(
    node_id: str,
    *,
    parent_id: str = "",
    status: str = "resolved",
    tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "node_id": node_id,
        "title": f"Public fixture {node_id}",
        "node_kind": "experiment",
        "status": status,
        "parent_id": parent_id,
        "tags": tags or [],
    }


def _edge(source: str, target: str) -> dict[str, object]:
    return {
        "edge_id": f"edge-{source}-{target}",
        "from_node": source,
        "to_node": target,
        "edge_type": "supports",
    }


def _small_projection() -> dict[str, object]:
    return {
        "ok": True,
        "goal_id": "goal-public-fixture",
        "source_event_count": 3,
        "nodes": [
            _node("root", status="resolved", tags=["baseline"]),
            _node("candidate", parent_id="root", status="exploring", tags=["current-best"]),
        ],
        "edges": [_edge("root", "candidate")],
        "findings": [
            {
                "finding_id": "finding-candidate",
                "finding": "Candidate evidence",
                "node_id": "candidate",
                "status": "confirmed",
            }
        ],
    }


def _complex_projection() -> dict[str, object]:
    nodes = [_node("root", status="open", tags=["decision"])]
    edges = []
    for branch_index in range(8):
        branch_id = f"branch-{branch_index}"
        nodes.append(_node(branch_id, parent_id="root"))
        edges.append(_edge("root", branch_id))
        for leaf_index in range(4):
            leaf_id = f"leaf-{branch_index}-{leaf_index}"
            nodes.append(_node(leaf_id, parent_id=branch_id, status="dead_end"))
            edges.append(_edge(branch_id, leaf_id))
    nodes.append(
        _node(
            "candidate",
            parent_id="root",
            status="exploring",
            tags=["current-best"],
        )
    )
    edges.append(_edge("root", "candidate"))
    return {
        "ok": True,
        "goal_id": "goal-public-fixture",
        "source_event_count": len(nodes) + len(edges),
        "nodes": nodes,
        "edges": edges,
        "findings": [],
    }


def test_small_graph_keeps_canonical_only_and_complete() -> None:
    projection = _small_projection()

    bundle = build_explore_presentation_bundle(projection)

    assert bundle["presentation_mode"] == PRESENTATION_MODE_CANONICAL_ONLY
    assert bundle["canonical"]["graph_counts"]["node_count"] == len(projection["nodes"])
    assert bundle["canonical"]["filter"]["truncated"] is False


def test_complex_graph_recommends_traceable_dual_view() -> None:
    projection = _complex_projection()

    bundle = build_explore_presentation_bundle(projection)

    assert bundle["presentation_mode"] == PRESENTATION_MODE_DUAL_VIEW
    assert {
        "low_decision_density",
        "excessive_terminal_branches",
    }.issubset(bundle["reason_codes"])
    assert bundle["canonical"]["source_digest"] == bundle["executive"]["source_digest"]
    assert bundle["canonical"]["source_revision"] == bundle["executive"]["source_revision"]
    canonical_ids = {node["node_id"] for node in bundle["canonical"]["nodes"]}
    assert len(bundle["executive"]["nodes"]) < len(canonical_ids)
    for node in bundle["executive"]["nodes"]:
        assert node["source_node_id"] in canonical_ids
        assert node["lineage"][-1] == node["source_node_id"]
    assert bundle["assessment"]["canonical_truncation_allowed"] is False


def test_findings_change_digest_and_stale_view_is_rejected() -> None:
    projection = _small_projection()
    bundle = build_explore_presentation_bundle(projection)
    changed = json.loads(json.dumps(projection))
    changed["findings"][0]["finding"] = "Updated candidate evidence"

    assert explore_source_digest(changed) != bundle["source_digest"]
    freshness = validate_explore_view_freshness(changed, bundle["executive"])
    assert freshness["fresh"] is False
    assert freshness["reason"]


def test_presentation_rejects_a_bounded_canonical_finding_projection() -> None:
    projection = _small_projection()
    projection["counts"] = {"finding_count": 2}

    with pytest.raises(ValueError, match="complete canonical finding set"):
        build_explore_presentation_bundle(projection)


def test_visual_configuration_preserves_legacy_and_supports_roles(tmp_path) -> None:
    config_path = tmp_path / "lark-explore.json"
    write_lark_explore_local_config(
        config_path,
        {
            "board": {
                "base_token": "PUBLIC_FIXTURE_BASE",
                "tables": {"nodes": "tblN", "edges": "tblE", "findings": "tblF"},
            }
        },
    )
    configure_lark_explore_visual_sink(
        config_path=config_path,
        whiteboard_token="wb_legacy_fixture",
        execute=True,
    )
    configure_lark_explore_visual_sink(
        config_path=config_path,
        whiteboard_token="wb_canonical_fixture",
        projection_mode="canonical_full",
        view_role="canonical",
        execute=True,
    )
    configure_lark_explore_visual_sink(
        config_path=config_path,
        whiteboard_token="wb_executive_fixture",
        projection_mode="executive_auto",
        view_role="executive",
        execute=True,
    )

    stored = read_lark_explore_local_config(config_path)
    assert stored["visual_sink"]["whiteboard_token"] == "wb_legacy_fixture"
    assert stored["visual_sinks"]["canonical"]["view_role"] == "canonical"
    assert stored["visual_sinks"]["executive"]["view_role"] == "executive"


def test_dual_visual_sync_uses_one_revision_and_rejects_stale_view(tmp_path) -> None:
    projection = _complex_projection()
    config = LarkExploreConfig(
        base_token="PUBLIC_FIXTURE_BASE",
        table_ids={"nodes": "tblN", "edges": "tblE", "findings": "tblF"},
    )
    sinks = {
        "canonical": {
            "whiteboard_token": "wb_canonical_fixture",
            "view_role": "canonical",
        },
        "executive": {
            "whiteboard_token": "wb_executive_fixture",
            "view_role": "executive",
        },
    }

    synced = sync_explore_visuals_to_lark(
        config,
        projection=projection,
        visual_sinks=sinks,
        config_path=tmp_path / "lark-explore.json",
    )

    assert synced["ok"] is True
    assert synced["presentation_mode"] == PRESENTATION_MODE_DUAL_VIEW
    revisions = {view["source_revision"] for view in synced["views"].values()}
    assert revisions == {synced["source_revision"]}

    bundle = build_explore_presentation_bundle(projection)
    changed = json.loads(json.dumps(projection))
    changed["nodes"][0]["title"] = "Changed canonical source"
    stale = sync_explore_visual_to_lark(
        config,
        projection=changed,
        visual_sink=sinks["executive"],
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=bundle["executive"],
    )
    assert stale["ok"] is False
    assert stale["status"] == "stale_projection"
    assert "command" not in stale
