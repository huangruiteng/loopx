#!/usr/bin/env python3
"""Smoke-test material issue-fix -> Explore -> Lark projection."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.explore_projection import (  # noqa: E402
    project_issue_fix_explore_graph,
)
from loopx.capabilities.issue_fix.feasibility import (  # noqa: E402
    build_issue_fix_feasibility_packet,
)
from loopx.capabilities.issue_fix.pr_lifecycle import (  # noqa: E402
    build_issue_fix_pr_lifecycle_monitor_packet,
)
from loopx.capabilities.explore.activation import (  # noqa: E402
    sync_explore_graph_after_material_refresh,
)
from loopx.domain_packs.issue_fix import (  # noqa: E402
    default_issue_fix_domain_state_ledger_path,
    default_issue_fix_feasibility_ledger_path,
    upsert_issue_fix_feasibility_ledger_jsonl,
    upsert_issue_fix_pr_lifecycle_ledger_jsonl,
)
from loopx.history import load_registry  # noqa: E402
from loopx.paths import resolve_runtime_root  # noqa: E402
from loopx.presentation.sinks.lark import explore_results  # noqa: E402
from loopx.rollout_event_log import (  # noqa: E402
    append_rollout_event,
    build_rollout_event,
    rollout_event_log_path,
)


def feasibility_packet() -> dict[str, object]:
    return build_issue_fix_feasibility_packet(
        url="https://github.com/public-fixture/widgets/issues/7",
        reproduction_status="confirmed",
        scope_class="bounded",
        reproduction_label="focused parser reproduction",
        validation_label="focused parser validation",
    )


def lifecycle_packet() -> dict[str, object]:
    return build_issue_fix_pr_lifecycle_monitor_packet(
        url="https://github.com/public-fixture/widgets/pull/8",
        issue_ref="#7",
        provider_payload={
            "state": "OPEN",
            "reviewDecision": "REVIEW_REQUIRED",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [{"name": "focused", "conclusion": "SUCCESS"}],
        },
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-explore-") as tmp:
        project = Path(tmp)
        loopx_dir = project / ".loopx"
        loopx_dir.mkdir()
        goal_id = "public-issue-fix"
        runtime = project / "runtime"
        state = loopx_dir / "active-state.md"
        state.write_text(
            "\n".join(
                [
                    "## User Todo / Owner Review Reading Queue",
                    "",
                    "## Agent Todo",
                    "",
                    "- [ ] [P1] Fix the generic graph projection gap",
                    "  <!-- loopx: todo_id=todo_gap status=claimed claimed_by=codex-fixture target_capabilities=issue_fix_explore_projection explore_result_node_refs=cap_explore_projection -->",
                ]
            ),
            encoding="utf-8",
        )
        registry = loopx_dir / "registry.json"
        other_state = loopx_dir / "other-active-state.md"
        other_state.write_text(
            "## User Todo / Owner Review Reading Queue\n\n## Agent Todo\n",
            encoding="utf-8",
        )
        registry.write_text(
            json.dumps(
                {
                    "common_runtime_root": str(runtime),
                    "goals": [
                        {
                            "id": goal_id,
                            "repo": str(project),
                            "state_file": str(state),
                        },
                        {
                            "id": "unrelated-goal",
                            "repo": str(project),
                            "state_file": str(other_state),
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        activation_calls: list[tuple[bool, bool]] = []

        def activation_syncer(**kwargs: object) -> dict[str, object]:
            external_sink_delivery_authorized = bool(
                kwargs.get("external_sink_delivery_authorized", True)
            )
            activation_calls.append(
                (bool(kwargs.get("execute")), external_sink_delivery_authorized)
            )
            return {
                "ok": True,
                "status": (
                    "unchanged"
                    if external_sink_delivery_authorized
                    else "external_sink_suppressed"
                ),
                "needs_row_sync": not external_sink_delivery_authorized,
                "needs_visual_sync": False,
                "row_readback_verified": external_sink_delivery_authorized,
                "semantic_digest": "fixture-digest",
                "projection": {
                    "applicable": True,
                    "material_change": False,
                    "material_event_count": 0,
                    "appended_event_count": 0,
                },
            }

        graph_disabled = sync_explore_graph_after_material_refresh(
            registry_path=registry,
            goal_id=goal_id,
            agent_id="codex-fixture",
            project=project,
            syncer=activation_syncer,
        )
        assert graph_disabled["status"] == "disabled", graph_disabled
        assert graph_disabled["delivery_postcondition"]["satisfied"] is True, graph_disabled
        assert graph_disabled["delivery_postcondition"]["required"] is False, graph_disabled
        assert activation_calls == [], activation_calls

        registry_payload = json.loads(registry.read_text(encoding="utf-8"))
        registry_payload["goals"][0]["explore_graph"] = {"enabled": True}
        registry.write_text(json.dumps(registry_payload), encoding="utf-8")
        graph_enabled = sync_explore_graph_after_material_refresh(
            registry_path=registry,
            goal_id=goal_id,
            agent_id="codex-fixture",
            project=project,
            syncer=activation_syncer,
        )
        assert graph_enabled["status"] == "unchanged", graph_enabled
        assert graph_enabled["needs_row_sync"] is False, graph_enabled
        assert graph_enabled["delivery_postcondition"]["satisfied"] is True, graph_enabled
        assert graph_enabled["delivery_postcondition"]["disposition"] == "unchanged_verified", graph_enabled
        assert activation_calls == [(True, True)], activation_calls

        graph_suppressed = sync_explore_graph_after_material_refresh(
            registry_path=registry,
            goal_id=goal_id,
            agent_id="codex-fixture",
            project=project,
            syncer=activation_syncer,
            external_sink_delivery_authorized=False,
        )
        assert graph_suppressed["status"] == "external_sink_suppressed", graph_suppressed
        assert graph_suppressed["external_sink_delivery_authorized"] is False, graph_suppressed
        assert graph_suppressed["needs_row_sync"] is True, graph_suppressed
        assert graph_suppressed["delivery_postcondition"]["satisfied"] is False, graph_suppressed
        assert graph_suppressed["delivery_postcondition"]["blocks_delivery"] is False, graph_suppressed
        assert graph_suppressed["delivery_postcondition"]["retry_required"] is True, graph_suppressed
        assert activation_calls == [(True, True), (True, False)], activation_calls

        failure_calls: list[bool] = []

        def failing_syncer(**kwargs: object) -> dict[str, object]:
            failure_calls.append(bool(kwargs.get("execute")))
            raise RuntimeError("fixture transport failure")

        first_failure = sync_explore_graph_after_material_refresh(
            registry_path=registry,
            goal_id=goal_id,
            project=project,
            syncer=failing_syncer,
        )
        retry_failure = sync_explore_graph_after_material_refresh(
            registry_path=registry,
            goal_id=goal_id,
            project=project,
            syncer=failing_syncer,
        )
        assert first_failure["status"] == "sync_failed", first_failure
        assert first_failure["error_type"] == "RuntimeError", first_failure
        assert first_failure["delivery_postcondition"]["satisfied"] is False, first_failure
        assert first_failure["delivery_postcondition"]["blocks_delivery"] is True, first_failure
        assert retry_failure["status"] == "sync_failed", retry_failure
        assert failure_calls == [True, True], failure_calls

        unrelated = project_issue_fix_explore_graph(
            registry_path=registry,
            goal_id="unrelated-goal",
            project=project,
            execute=True,
        )
        assert unrelated["applicable"] is False, unrelated
        assert unrelated["material_event_count"] == 0, unrelated
        upsert_issue_fix_feasibility_ledger_jsonl(
            default_issue_fix_feasibility_ledger_path(project=project, goal_id=goal_id),
            feasibility_packet(),
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(
            default_issue_fix_domain_state_ledger_path(project=project, goal_id=goal_id),
            lifecycle_packet(),
        )
        rollout_log = rollout_event_log_path(resolve_runtime_root(load_registry(registry)), goal_id)
        append_rollout_event(
            rollout_log,
            build_rollout_event(
                goal_id=goal_id,
                event_kind="capability_gap",
                todo_id="todo_gap",
                agent_id="codex-fixture",
                status="found",
                summary="Material graph changes were not projected automatically.",
                details={
                    "target_capabilities": "issue_fix_explore_projection",
                    "evidence": "public-fixture-callsite",
                },
            ),
        )

        first = project_issue_fix_explore_graph(
            registry_path=registry,
            goal_id=goal_id,
            agent_id="codex-fixture",
            project=project,
            execute=True,
        )
        assert first["material_change"] is True, first
        assert first["appended_event_count"] > 0, first
        nodes = {item["node_id"]: item for item in first["projection"]["nodes"]}
        assert nodes["fix_7_8"]["status"] == "exploring", nodes
        assert nodes["cap_explore_projection"]["status"] == "exploring", nodes
        findings = {item["finding_id"] for item in first["projection"]["findings"]}
        assert "issue_7_8_lifecycle" in findings, findings
        issue_finding = next(
            item for item in first["projection"]["findings"] if item["finding_id"] == "issue_7_8_lifecycle"
        )
        assert "reproduction=confirmed" in issue_finding["summary"], issue_finding
        assert "PR #8 published" in issue_finding["summary"], issue_finding

        second = project_issue_fix_explore_graph(
            registry_path=registry,
            goal_id=goal_id,
            agent_id="codex-fixture",
            project=project,
            execute=True,
        )
        assert second["material_change"] is False, second
        assert second["appended_event_count"] == 0, second
        assert second["semantic_digest"] == first["semantic_digest"], second

        config_path = loopx_dir / "lark-explore.json"
        explore_results.write_lark_explore_local_config(
            config_path,
            {
                "board": {
                    "base_token": "PUBLIC_FIXTURE_BASE",
                    "tables": {"nodes": "tblN", "edges": "tblE", "findings": "tblF"},
                    "identity": "user",
                }
            },
        )
        configured = explore_results.configure_lark_explore_visual_sink(
            config_path=config_path,
            whiteboard_token="wb_public_fixture",
            docx_token="doc_public_fixture",
            projection_mode="executive_auto",
            view_role="executive",
            execute=True,
        )
        assert configured["status"] == "configured", configured
        sync_calls: list[str] = []
        visual_preview_calls: list[str] = []
        visual_publish_calls: list[str] = []
        delivery_version = ["delivery-v1"]
        original_sync = explore_results.sync_explore_results_to_lark
        original_visuals_sync = explore_results.sync_explore_visuals_to_lark

        def fake_sync(*args: object, **kwargs: object) -> dict[str, object]:
            projection = kwargs["projection"]
            assert isinstance(projection, dict)
            sync_calls.append(str(projection["source_event_count"]))
            persisted = explore_results.read_lark_explore_local_config(config_path)
            persisted["result_records"] = {"public-remote-row": "rec_public"}
            explore_results.write_lark_explore_local_config(config_path, persisted)
            return {
                "ok": True,
                "written_rows": sum(projection["counts"][key] for key in ("node_count", "edge_count", "finding_count")),
                "skipped_rows": 0,
                "duplicate_remote_rows": 0,
                "readback": {"ok": True, "performed": True, "verified": True},
                "error": None,
            }

        def fake_visuals_sync(*args: object, **kwargs: object) -> dict[str, object]:
            projection = kwargs["projection"]
            assert isinstance(projection, dict), projection
            digest = explore_results.explore_visual_semantic_digest(projection)
            delivery_digest = f"{delivery_version[0]}:{digest[:12]}"
            execute_visual = bool(kwargs.get("execute"))
            if not execute_visual:
                visual_preview_calls.append(delivery_digest)
                return {
                    "ok": True,
                    "status": "would_publish",
                    "presentation_mode": "dual_view",
                    "source_digest": digest,
                    "views": {
                        "executive": {
                            "ok": True,
                            "status": "would_publish",
                            "published": False,
                            "delivery_digest": delivery_digest,
                        }
                    },
                }
            visual_publish_calls.append(delivery_digest)
            if len(visual_publish_calls) == 1:
                return {
                    "ok": False,
                    "status": "publish_failed",
                    "presentation_mode": "dual_view",
                    "source_digest": digest,
                    "views": {
                        "executive": {
                            "ok": False,
                            "status": "publish_failed",
                            "published": False,
                            "delivery_digest": delivery_digest,
                        }
                    },
                    "error": "fixture visual transport failure",
                }
            return {
                "ok": True,
                "status": "published",
                "presentation_mode": "dual_view",
                "source_digest": digest,
                "views": {
                    "executive": {
                        "ok": True,
                        "status": "published",
                        "published": True,
                        "delivery_digest": delivery_digest,
                    }
                },
            }

        explore_results.sync_explore_results_to_lark = fake_sync
        explore_results.sync_explore_visuals_to_lark = fake_visuals_sync
        try:
            suppressed = explore_results.sync_issue_fix_explore_on_material_change(
                registry_path=registry,
                goal_id=goal_id,
                agent_id="codex-fixture",
                project=project,
                execute=True,
                external_sink_delivery_authorized=False,
            )
            assert suppressed["status"] == "external_sink_suppressed", suppressed
            assert suppressed["external_sink_delivery_authorized"] is False, suppressed
            assert suppressed["needs_row_sync"] is True, suppressed
            assert suppressed["needs_visual_sync"] is True, suppressed
            assert suppressed["projection"]["applicable"] is True, suppressed
            assert sync_calls == [], sync_calls
            assert visual_publish_calls == [], visual_publish_calls
            assert len(visual_preview_calls) == 1, visual_preview_calls
            suppressed_config = json.loads(config_path.read_text(encoding="utf-8"))
            assert goal_id not in suppressed_config.get("automatic_projection_sync", {}), suppressed_config

            partial = explore_results.sync_issue_fix_explore_on_material_change(
                registry_path=registry,
                goal_id=goal_id,
                agent_id="codex-fixture",
                project=project,
                execute=True,
            )
            assert partial["status"] == "sync_failed", partial
            assert partial["canonical_rows_sync"]["ok"] is True, partial
            assert partial["visual_sync"]["status"] == "publish_failed", partial
            retry = explore_results.sync_issue_fix_explore_on_material_change(
                registry_path=registry,
                goal_id=goal_id,
                agent_id="codex-fixture",
                project=project,
                execute=True,
            )
            assert retry["status"] == "synced", retry
            assert retry["canonical_rows_sync"] is None, retry
            assert retry["visual_sync"]["status"] == "published", retry
            unchanged = explore_results.sync_issue_fix_explore_on_material_change(
                registry_path=registry,
                goal_id=goal_id,
                agent_id="codex-fixture",
                project=project,
                execute=True,
            )
            assert unchanged["status"] == "unchanged", unchanged
            assert unchanged["row_readback_verified"] is True, unchanged
            assert len(sync_calls) == 1, sync_calls
            assert len(visual_publish_calls) == 2, visual_publish_calls

            delivery_version[0] = "delivery-v2"
            renderer_changed = explore_results.sync_issue_fix_explore_on_material_change(
                registry_path=registry,
                goal_id=goal_id,
                agent_id="codex-fixture",
                project=project,
                execute=True,
            )
            assert renderer_changed["status"] == "synced", renderer_changed
            assert renderer_changed["canonical_rows_sync"] is None, renderer_changed
            assert renderer_changed["visual_sync"]["status"] == "published", renderer_changed
            assert len(sync_calls) == 1, sync_calls
            assert len(visual_publish_calls) == 3, visual_publish_calls

            append_rollout_event(
                rollout_log,
                build_rollout_event(
                    goal_id=goal_id,
                    event_kind="capability_gap",
                    todo_id="todo_gap",
                    agent_id="codex-fixture",
                    status="real_callsite_verified",
                    summary="Projection verified in a real issue-fix sync call site.",
                    details={
                        "target_capabilities": "issue_fix_explore_projection",
                        "evidence": "public-fixture-callsite",
                    },
                ),
            )
            changed = explore_results.sync_issue_fix_explore_on_material_change(
                registry_path=registry,
                goal_id=goal_id,
                agent_id="codex-fixture",
                project=project,
                execute=True,
            )
            assert changed["status"] == "synced", changed
            assert len(sync_calls) == 2, sync_calls
            assert len(visual_publish_calls) == 4, visual_publish_calls
            changed_nodes = {item["node_id"]: item for item in changed["projection"]["projection"]["nodes"]}
            assert changed_nodes["cap_explore_projection"]["status"] == "resolved"
        finally:
            explore_results.sync_explore_results_to_lark = original_sync
            explore_results.sync_explore_visuals_to_lark = original_visuals_sync

        stored = json.loads(config_path.read_text(encoding="utf-8"))
        assert stored["result_records"] == {"public-remote-row": "rec_public"}, stored
        assert stored["visual_sinks"]["executive"]["whiteboard_token"] == "wb_public_fixture", stored
        assert stored["automatic_projection_sync"][goal_id]["semantic_digest"] == changed["semantic_digest"]
        assert stored["automatic_projection_sync"][goal_id]["visual_semantic_digest"] == changed["semantic_digest"]
        assert stored["automatic_projection_sync"][goal_id]["visual_delivery_digests"]["executive"].startswith(
            "delivery-v2:"
        ), stored
        assert str(project) not in json.dumps(changed["projection"]["projection"])

    print("issue-fix explore projection smoke: ok")


if __name__ == "__main__":
    main()
