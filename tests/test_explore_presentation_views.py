from __future__ import annotations

import json
import re

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
    summary: str = "",
) -> dict[str, object]:
    return {
        "node_id": node_id,
        "title": f"Public fixture {node_id}",
        "node_kind": "experiment",
        "status": status,
        "parent_id": parent_id,
        "tags": tags or [],
        "summary": summary,
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


def _lane_projection() -> dict[str, object]:
    nodes = [
        {
            **_node("root", status="exploring"),
            "title": "Public Explore pilot",
            "node_kind": "area",
        },
        {
            **_node(
                "delivery-lane",
                parent_id="root",
                status="exploring",
                tags=["lane-delivery"],
            ),
            "title": "Delivery lane",
            "node_kind": "area",
        },
        {
            **_node(
                "capability-lane",
                parent_id="root",
                status="exploring",
                tags=["lane-capability"],
            ),
            "title": "Capability lane",
            "node_kind": "area",
        },
        _node(
            "fix-pr", parent_id="delivery-lane", status="exploring", tags=["open-pr"]
        ),
        _node("durable-capability", parent_id="capability-lane", status="resolved"),
    ]
    edges = [
        {
            "edge_id": "edge-fix-supports-capability",
            "from_node": "fix-pr",
            "to_node": "durable-capability",
            "edge_type": "supports",
        },
        {
            "edge_id": "edge-fix-subtopic",
            "from_node": "fix-pr",
            "to_node": "delivery-lane",
            "edge_type": "subtopic_of",
        },
    ]
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
    assert bundle["canonical"]["mermaid"].startswith("flowchart TB")
    assert "subgraph canonical_atlas" in bundle["canonical"]["mermaid"]
    assert (
        bundle["canonical"]["filter"]["layout"]["strategy"]
        == "vertical_evidence_timeline"
    )
    assert bundle["canonical"]["filter"]["layout"]["column_count"] == 1
    assert bundle["executive"]["mermaid"].startswith("flowchart TB")
    assert "subgraph executive_atlas" in bundle["executive"]["mermaid"]
    assert "Canonical evidence timeline" not in bundle["executive"]["mermaid"]
    assert (
        bundle["executive"]["filter"]["layout"]["orientation"]
        == "top_to_bottom"
    )
    canonical_mermaid = bundle["canonical"]["mermaid"]
    for node in projection["nodes"]:
        assert f'{str(node["node_id"]).replace("-", "_")}["' in canonical_mermaid
    for edge in projection["edges"]:
        source = str(edge["from_node"]).replace("-", "_")
        target = str(edge["to_node"]).replace("-", "_")
        assert f"{source} -->|supports| {target}" in canonical_mermaid
    canonical_ids = {node["node_id"] for node in bundle["canonical"]["nodes"]}
    assert len(bundle["executive"]["nodes"]) < len(canonical_ids)
    for node in bundle["executive"]["nodes"]:
        assert node["source_node_id"] in canonical_ids
        assert node["lineage"][-1] == node["source_node_id"]
    assert bundle["assessment"]["canonical_truncation_allowed"] is False


def test_both_views_render_status_metric_and_conclusion_from_node_summary() -> None:
    projection = _small_projection()
    projection["nodes"][1].update(
        {
            "title": "candidate_model_abc1234 with a deliberately long descriptive title",
            "status": "resolved",
            "summary": (
                "Aligned evaluation completed with stable sample parity. "
                "Target slice is +31.2/+72.4 bp and composite +51.8 bp; "
                "guardrail slice is -1.2 bp. "
                "Retain as incumbent with calibration as a guardrail."
            ),
        }
    )

    bundle = build_explore_presentation_bundle(projection)

    for role in ("canonical", "executive"):
        view = bundle[role]
        assert "candidate_model_abc1234 with a deliberately long descriptive… · DONE" in view["mermaid"]
        assert "+31.2/+72.4 bp" in view["mermaid"]
        assert "Retain as incumbent with calibration as a guardrail" in view["mermaid"]
        assert "+31.2/+72.4 bp" in view["svg"]
        assert "Retain as incumbent with calibration as a guardrail" in view["svg"]
        assert "+31.2/+72.4 bp" in view["svg_board"]
        assert "Retain as incumbent with calibration as a guardrail" in view["svg_board"]
        mermaid_coverage = view["filter"]["layout"]["node_detail_coverage"]
        svg_coverage = view["filter"]["renderer_layouts"]["svg_atlas"][
            "node_detail_coverage"
        ]
        board_coverage = view["filter"]["renderer_layouts"]["svg_board"][
            "node_detail_coverage"
        ]
        assert mermaid_coverage["complete"] is True
        assert mermaid_coverage["summary_rendered_node_count"] == 1
        assert mermaid_coverage["metric_rendered_node_count"] == 1
        assert svg_coverage == mermaid_coverage
        assert board_coverage == mermaid_coverage


def test_flat_large_graph_is_classified_as_a_readability_failure() -> None:
    projection = {
        "ok": True,
        "goal_id": "goal-public-fixture",
        "source_event_count": 80,
        "nodes": [_node(f"root-{index}") for index in range(80)],
        "edges": [],
        "findings": [],
    }

    bundle = build_explore_presentation_bundle(projection)

    assert "readability_check_failed" in bundle["reason_codes"]
    assert bundle["assessment"]["metrics"]["root_node_count"] == 80
    assert bundle["assessment"]["readability_check"]["failed"] is True
    assert bundle["canonical"]["filter"]["layout"]["column_count"] == 1


def test_configured_atlas_columns_fit_wide_whiteboard_embeds() -> None:
    bundle = build_explore_presentation_bundle(
        _complex_projection(),
        policy={"atlas_column_count": 4},
    )

    assert bundle["executive"]["mermaid"].startswith("flowchart LR")
    layout = bundle["executive"]["filter"]["layout"]
    assert layout["strategy"] == "multi_column_evidence_atlas"
    assert layout["column_count"] == layout["group_count"] == 2
    assert layout["orientation"] == "left_to_right"


def test_svg_atlas_owns_a_fixed_grid_and_keeps_executive_nodes_visible() -> None:
    bundle = build_explore_presentation_bundle(
        _complex_projection(),
        policy={"atlas_column_count": 2},
    )

    executive = bundle["executive"]
    svg = executive["svg"]
    layout = executive["filter"]["renderer_layouts"]["svg_atlas"]
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert "Executive Explore Evidence Atlas" in svg
    assert layout["strategy"] == "fixed_grid_evidence_atlas"
    assert layout["column_count"] == 2
    assert layout["row_count"] >= 1
    assert layout["rendered_relation_count"] == layout["group_count"] - 1
    for node in executive["nodes"]:
        assert str(node["title"]) in svg


def test_svg_board_preserves_bounded_stages_frontier_and_real_relations() -> None:
    bundle = build_explore_presentation_bundle(
        _lane_projection(),
        policy={"board_stage_capacity": 8},
    )

    canonical = bundle["canonical"]
    svg = canonical["svg_board"]
    layout = canonical["filter"]["renderer_layouts"]["svg_board"]
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert "Live Explore Evidence Stages" in svg
    assert "Evidence stage 01" in svg
    assert 'data-evidence-stage="1"' in svg
    assert 'data-stage-capacity="8"' in svg
    assert 'data-node-id="fix-pr"' in svg
    assert 'data-frontier="true"' in svg
    assert 'data-edge-id="edge-fix-supports-capability"' in svg
    assert 'data-edge-id="edge-fix-subtopic"' not in svg
    assert layout["strategy"] == "vertical_evidence_stage_board"
    assert layout["stage_count"] == 1
    assert layout["stage_capacity"] == 8
    assert layout["stage_sizes"] == [2]
    assert layout["frontier_node_count"] == 1
    assert layout["rendered_relation_count"] == 1
    assert layout["cross_stage_relation_count"] == 0
    assert layout["suppressed_relation_count"] == 1
    assert layout["source_edge_count"] == 2
    assert layout["semantic_contract"]["evidence_stage_capacity_bounded"] is True


def test_svg_board_caps_each_evidence_stage() -> None:
    bundle = build_explore_presentation_bundle(
        _complex_projection(),
        policy={"board_stage_capacity": 12},
    )

    layout = bundle["executive"]["filter"]["renderer_layouts"]["svg_board"]
    assert layout["stage_count"] >= 2
    assert layout["stage_capacity"] == 12
    assert all(1 <= size <= 12 for size in layout["stage_sizes"])
    assert sum(layout["stage_sizes"]) == layout["rendered_node_count"]


def test_executive_view_suppresses_dense_hub_scaffolding_edges() -> None:
    nodes = [_node("hub", status="open", tags=["decision"])]
    nodes.extend(
        _node(f"active-{index}", parent_id="hub", status="exploring")
        for index in range(6)
    )
    edges = [_edge("hub", f"active-{index}") for index in range(6)]
    edges.append(
        {
            "edge_id": "edge-active-sequence",
            "from_node": "active-0",
            "to_node": "active-1",
            "edge_type": "leads_to",
        }
    )
    projection = {
        "ok": True,
        "goal_id": "goal-public-fixture",
        "source_event_count": len(nodes) + len(edges),
        "nodes": nodes,
        "edges": edges,
        "findings": [],
    }

    bundle = build_explore_presentation_bundle(projection)

    assert bundle["canonical"]["graph_counts"]["edge_count"] == 7
    assert bundle["executive"]["graph_counts"]["edge_count"] == 1
    assert bundle["executive"]["graph_counts"]["suppressed_edge_count"] == 6
    edge_projection = bundle["executive"]["filter"]["edge_projection"]
    assert edge_projection["suppression_counts"]["dense_hub_scaffolding"] == 6
    assert "hub -->|supports|" not in bundle["executive"]["mermaid"]
    assert "active_0 -->|leads_to| active_1" in bundle["executive"]["mermaid"]


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
        atlas_column_count=4,
        renderer="svg_atlas",
        execute=True,
    )

    stored = read_lark_explore_local_config(config_path)
    assert stored["visual_sink"]["whiteboard_token"] == "wb_legacy_fixture"
    assert stored["visual_sinks"]["canonical"]["view_role"] == "canonical"
    assert stored["visual_sinks"]["executive"]["view_role"] == "executive"
    assert stored["visual_sinks"]["executive"]["atlas_column_count"] == 4
    assert stored["visual_sinks"]["executive"]["renderer"] == "svg_atlas"


def test_svg_atlas_configuration_requires_an_explicit_view_role(tmp_path) -> None:
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

    with pytest.raises(ValueError, match="requires a canonical or executive"):
        configure_lark_explore_visual_sink(
            config_path=config_path,
            whiteboard_token="wb_legacy_fixture",
            renderer="svg_atlas",
        )

    with pytest.raises(ValueError, match="requires a canonical or executive"):
        configure_lark_explore_visual_sink(
            config_path=config_path,
            whiteboard_token="wb_legacy_fixture",
            renderer="svg_board",
        )


def test_dual_visual_sync_applies_role_specific_atlas_columns(tmp_path) -> None:
    projection = _complex_projection()
    config = LarkExploreConfig(base_token="PUBLIC_FIXTURE_BASE")
    synced = sync_explore_visuals_to_lark(
        config,
        projection=projection,
        visual_sinks={
            "executive": {
                "whiteboard_token": "wb_executive_fixture",
                "view_role": "executive",
                "atlas_column_count": 4,
                "renderer": "svg_atlas",
            }
        },
        config_path=tmp_path / "lark-explore.json",
    )

    view = synced["views"]["executive"]
    assert view["filter"]["renderer_layouts"]["svg_atlas"]["column_count"] == 2
    assert view["renderer"] == "svg_atlas"
    assert view["input_format"] == "svg"
    command = view["command"]["command"]
    assert "--input_format svg" in command
    assert ".svg --overwrite" in command


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


def test_visual_delivery_digest_changes_when_only_rendered_mermaid_changes(tmp_path) -> None:
    projection = _complex_projection()
    config = LarkExploreConfig(base_token="PUBLIC_FIXTURE_BASE")
    sink = {
        "whiteboard_token": "wb_canonical_fixture",
        "view_role": "canonical",
    }
    bundle = build_explore_presentation_bundle(projection)
    first_view = bundle["canonical"]
    changed_view = json.loads(json.dumps(first_view))
    changed_view["mermaid"] += "\n    %% renderer contract changed"

    first = sync_explore_visual_to_lark(
        config,
        projection=projection,
        visual_sink=sink,
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=first_view,
        view_key="canonical",
    )
    changed = sync_explore_visual_to_lark(
        config,
        projection=projection,
        visual_sink=sink,
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=changed_view,
        view_key="canonical",
    )

    assert first["source_digest"] == changed["source_digest"]
    assert first["delivery_digest"] != changed["delivery_digest"]
    assert first["command"]["command"] != changed["command"]["command"]


def test_visual_delivery_digest_and_command_include_renderer(tmp_path) -> None:
    projection = _complex_projection()
    config = LarkExploreConfig(base_token="PUBLIC_FIXTURE_BASE")
    bundle = build_explore_presentation_bundle(
        projection,
        policy={"atlas_column_count": 2},
    )
    view = bundle["executive"]

    mermaid = sync_explore_visual_to_lark(
        config,
        projection=projection,
        visual_sink={
            "whiteboard_token": "wb_executive_fixture",
            "view_role": "executive",
            "renderer": "mermaid",
        },
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=view,
        view_key="executive",
    )
    svg = sync_explore_visual_to_lark(
        config,
        projection=projection,
        visual_sink={
            "whiteboard_token": "wb_executive_fixture",
            "view_role": "executive",
            "renderer": "svg_atlas",
        },
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=view,
        view_key="executive",
    )
    board = sync_explore_visual_to_lark(
        config,
        projection=projection,
        visual_sink={
            "whiteboard_token": "wb_executive_fixture",
            "view_role": "executive",
            "renderer": "svg_board",
        },
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=view,
        view_key="executive",
    )

    assert mermaid["source_digest"] == svg["source_digest"] == board["source_digest"]
    assert mermaid["delivery_digest"] != svg["delivery_digest"]
    assert board["delivery_digest"] not in {
        mermaid["delivery_digest"],
        svg["delivery_digest"],
    }
    assert mermaid["input_format"] == "mermaid"
    assert svg["input_format"] == "svg"
    assert board["input_format"] == "svg"


def test_svg_visual_publish_reads_back_remote_delivery_marker(tmp_path) -> None:
    projection = _complex_projection()
    config = LarkExploreConfig(base_token="PUBLIC_FIXTURE_BASE")
    bundle = build_explore_presentation_bundle(projection)
    calls: list[list[str]] = []
    published_marker = ""

    def runner(args, cwd, _timeout):
        nonlocal published_marker
        calls.append(args)
        if "+update" in args:
            source_arg = args[args.index("--source") + 1]
            source = (cwd / source_arg.removeprefix("@")).read_text(
                encoding="utf-8"
            )
            marker_match = re.search(r"LoopX delivery [0-9a-f]{20}", source)
            assert marker_match
            published_marker = marker_match.group(0)
            return {
                "returncode": 0,
                "stdout": json.dumps({"ok": True}),
                "stderr": "",
            }
        assert "+query" in args
        return {
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "ok": True,
                    "data": {
                        "nodes": [
                            {
                                "type": "text_shape",
                                "text": {"text": published_marker},
                            }
                        ]
                    },
                }
            ),
            "stderr": "",
        }

    synced = sync_explore_visual_to_lark(
        config,
        projection=projection,
        visual_sink={
            "whiteboard_token": "wb_executive_fixture",
            "view_role": "executive",
            "renderer": "svg_board",
        },
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=bundle["executive"],
        view_key="executive",
        execute=True,
        runner=runner,
    )

    assert len(calls) == 2
    assert synced["ok"] is True
    assert synced["status"] == "published"
    assert synced["published"] is True
    assert synced["readback"]["performed"] is True
    assert synced["readback"]["verified"] is True
    assert synced["readback"]["observed_marker"] == published_marker


def test_svg_visual_readback_retries_lark_doc_applying(tmp_path, monkeypatch) -> None:
    projection = _complex_projection()
    config = LarkExploreConfig(base_token="PUBLIC_FIXTURE_BASE")
    bundle = build_explore_presentation_bundle(projection)
    published_marker = ""
    query_count = 0
    delays: list[float] = []
    monkeypatch.setattr(
        "loopx.presentation.sinks.lark.explore_results.time.sleep",
        delays.append,
    )

    def runner(args, cwd, _timeout):
        nonlocal published_marker, query_count
        if "+update" in args:
            source_arg = args[args.index("--source") + 1]
            source = (cwd / source_arg.removeprefix("@")).read_text(
                encoding="utf-8"
            )
            published_marker = re.search(
                r"LoopX delivery [0-9a-f]{20}",
                source,
            ).group(0)
            payload = {"ok": True}
        else:
            query_count += 1
            payload = (
                {
                    "ok": False,
                    "error": {
                        "code": 4003101,
                        "message": "doc is applying; doc data is not ready",
                    },
                }
                if query_count == 1
                else {
                    "ok": True,
                    "data": {
                        "nodes": [{"text": {"text": published_marker}}]
                    },
                }
            )
        return {
            "returncode": 0 if payload.get("ok") else 1,
            "stdout": json.dumps(payload) if payload.get("ok") else "",
            "stderr": "" if payload.get("ok") else json.dumps(payload),
        }

    synced = sync_explore_visual_to_lark(
        config,
        projection=projection,
        visual_sink={
            "whiteboard_token": "wb_executive_fixture",
            "view_role": "executive",
            "renderer": "svg_board",
        },
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=bundle["executive"],
        view_key="executive",
        execute=True,
        runner=runner,
    )

    assert synced["ok"] is True
    assert synced["published"] is True
    assert synced["readback"]["verified"] is True
    assert synced["readback"]["attempt_count"] == 2
    assert synced["readback"]["attempts"][0]["error_code"] == 4003101
    assert delays == [0.25]


def test_svg_visual_publish_fails_closed_when_remote_marker_is_missing(
    tmp_path,
) -> None:
    projection = _complex_projection()
    config = LarkExploreConfig(base_token="PUBLIC_FIXTURE_BASE")
    bundle = build_explore_presentation_bundle(projection)

    def runner(args, _cwd, _timeout):
        payload = (
            {
                "ok": True,
                "data": {"nodes": [{"text": {"text": "stale visual"}}]},
            }
            if "+query" in args
            else {"ok": True}
        )
        return {
            "returncode": 0,
            "stdout": json.dumps(payload),
            "stderr": "",
        }

    synced = sync_explore_visual_to_lark(
        config,
        projection=projection,
        visual_sink={
            "whiteboard_token": "wb_executive_fixture",
            "view_role": "executive",
            "renderer": "svg_board",
        },
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=bundle["executive"],
        view_key="executive",
        execute=True,
        runner=runner,
    )

    assert synced["ok"] is False
    assert synced["status"] == "publish_unverified"
    assert synced["published"] is False
    assert synced["readback"]["performed"] is True
    assert synced["readback"]["verified"] is False
    assert "expected delivery marker" in synced["error"]


def test_visual_delivery_digest_changes_when_target_whiteboard_changes(tmp_path) -> None:
    projection = _complex_projection()
    config = LarkExploreConfig(base_token="PUBLIC_FIXTURE_BASE")
    bundle = build_explore_presentation_bundle(projection)

    first = sync_explore_visual_to_lark(
        config,
        projection=projection,
        visual_sink={"whiteboard_token": "wb_first", "view_role": "executive"},
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=bundle["executive"],
        view_key="executive",
    )
    changed = sync_explore_visual_to_lark(
        config,
        projection=projection,
        visual_sink={"whiteboard_token": "wb_second", "view_role": "executive"},
        config_path=tmp_path / "lark-explore.json",
        semantic_digest=bundle["source_digest"],
        display_projection=bundle["executive"],
        view_key="executive",
    )

    assert first["source_digest"] == changed["source_digest"]
    assert first["delivery_digest"] != changed["delivery_digest"]
    assert first["command"]["command"] != changed["command"]["command"]
