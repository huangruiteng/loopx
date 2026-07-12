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
            tags=["issue-fix"],
            projection_mode="issue_fix_two_lane",
            execute=True,
        )
        assert configured["status"] == "configured", configured
        sync_calls: list[str] = []
        visual_calls: list[str] = []
        original_sync = explore_results.sync_explore_results_to_lark
        original_visual_sync = explore_results.sync_explore_visual_to_lark

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
                "error": None,
            }

        def fake_visual_sync(*args: object, **kwargs: object) -> dict[str, object]:
            digest = str(kwargs["semantic_digest"])
            display = kwargs["display_projection"]
            assert isinstance(display, dict), display
            assert display["schema_version"] == "issue_fix_executive_visual_projection_v0"
            assert display["graph_counts"]["delivery_node_count"] == 1, display
            expected_capability_nodes = 0 if len(visual_calls) >= 2 else 1
            assert display["graph_counts"]["capability_node_count"] == expected_capability_nodes, display
            visual_calls.append(digest)
            if len(visual_calls) == 1:
                return {
                    "ok": False,
                    "status": "publish_failed",
                    "published": False,
                    "error": "fixture visual transport failure",
                }
            return {
                "ok": True,
                "status": "published",
                "published": True,
                "semantic_digest": digest,
                "graph_counts": {"node_count": 3, "edge_count": 2},
                "error": None,
            }

        explore_results.sync_explore_results_to_lark = fake_sync
        explore_results.sync_explore_visual_to_lark = fake_visual_sync
        try:
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
            assert len(sync_calls) == 1, sync_calls
            assert len(visual_calls) == 2, visual_calls

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
            assert len(visual_calls) == 3, visual_calls
            changed_nodes = {item["node_id"]: item for item in changed["projection"]["projection"]["nodes"]}
            assert changed_nodes["cap_explore_projection"]["status"] == "resolved"
        finally:
            explore_results.sync_explore_results_to_lark = original_sync
            explore_results.sync_explore_visual_to_lark = original_visual_sync

        stored = json.loads(config_path.read_text(encoding="utf-8"))
        assert stored["result_records"] == {"public-remote-row": "rec_public"}, stored
        assert stored["visual_sink"]["whiteboard_token"] == "wb_public_fixture", stored
        assert stored["automatic_projection_sync"][goal_id]["semantic_digest"] == changed["semantic_digest"]
        assert stored["automatic_projection_sync"][goal_id]["visual_semantic_digest"] == changed["semantic_digest"]
        assert str(project) not in json.dumps(changed["projection"]["projection"])

    print("issue-fix explore projection smoke: ok")


if __name__ == "__main__":
    main()
