#!/usr/bin/env python3
"""Smoke-test the exploration result layer: topology log, Lark board sync, card.

Covers the durable public contracts:
- result events (node/edge/finding) fold into a bounded public-safe projection
  with topology tree, blocked reasons, findings, and Mermaid graph source;
- absolute local paths are rejected at record time and never reach generated
  Lark record values (shared_adapter_local_path_leak guard);
- feishu-sync is dry-run by default, upserts idempotently by record id on the
  second executed sync, and shared visibility redacts private links;
- the result card is transport-free content built from the same projection;
- the CLI surface works end to end against a temp registry/runtime root.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.explore import result_log  # noqa: E402
from loopx.capabilities.explore.router_state import (  # noqa: E402
    advance_epoch,
    scope_family_key,
    initial_router_state,
    observe_epoch,
)
from loopx.capabilities.explore.todo_branch_plan import build_explore_todo_branch_plan  # noqa: E402
from loopx.capabilities.explore.worker_branch_plan import build_explore_worker_branch_plan  # noqa: E402
from loopx.presentation.sinks.lark import explore_results  # noqa: E402


ABS_PATH_RE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/](?![\\/])|file://|/Users/|/home/")


def build_sample_events(goal_id: str) -> list[dict[str, object]]:
    events = [
        result_log.build_explore_node_event(
            goal_id=goal_id,
            title="SCADE peer tool landscape",
            node_id="node_root",
            node_kind="area",
            status="exploring",
            recorded_at="2026-07-06T01:00:00Z",
        ),
        result_log.build_explore_node_event(
            goal_id=goal_id,
            title="KCG code generator licensing",
            node_id="node_kcg",
            node_kind="question",
            status="open",
            parent_id="node_root",
            recorded_at="2026-07-06T01:05:00Z",
        ),
        # Same node id again: latest event wins in the projection.
        result_log.build_explore_node_event(
            goal_id=goal_id,
            title="KCG code generator licensing",
            node_id="node_kcg",
            node_kind="question",
            status="blocked",
            blocked_reason="vendor licence terms unclear",
            parent_id="node_root",
            recorded_at="2026-07-06T02:00:00Z",
        ),
        result_log.build_explore_edge_event(
            goal_id=goal_id,
            from_node="node_kcg",
            to_node="node_root",
            edge_type="subtopic_of",
            recorded_at="2026-07-06T01:06:00Z",
        ),
        result_log.build_explore_finding_event(
            goal_id=goal_id,
            title="Two open-source Lustre toolchains cover the KCG core use case",
            node_id="node_kcg",
            status="confirmed",
            confidence=0.8,
            evidence_refs=["ov:doc:lustre-survey"],
            summary="See https://internal.example.invalid/wiki/abc for the private survey doc",
            recorded_at="2026-07-06T02:10:00Z",
        ),
    ]
    return events


def check_result_log_contract() -> dict[str, object]:
    goal_id = "explore-smoke-goal"
    with tempfile.TemporaryDirectory(prefix="loopx-explore-smoke-") as tmp:
        runtime_root = Path(tmp) / "runtime"
        log_path = result_log.explore_result_log_path(runtime_root, goal_id)
        for event in build_sample_events(goal_id):
            appended = result_log.append_explore_result_event(log_path, event)
            assert appended["ok"] is True, appended
        events = result_log.load_explore_result_events(log_path, goal_id=goal_id)
        assert len(events) == 5, events

        projection = result_log.build_explore_result_projection(events, goal_id=goal_id)
        assert projection["schema_version"] == "loopx_explore_result_projection_v0", projection
        counts = projection["counts"]
        assert counts["node_count"] == 2, counts
        assert counts["edge_count"] == 1, counts
        assert counts["finding_count"] == 1, counts
        assert counts["nodes_by_status"]["blocked"] == 1, counts

        # Latest node event wins and keeps update lineage.
        kcg = next(node for node in projection["nodes"] if node["node_id"] == "node_kcg")
        assert kcg["status"] == "blocked", kcg
        assert kcg["blocked_reason"] == "vendor licence terms unclear", kcg
        assert kcg["update_count"] == 2, kcg
        assert kcg["finding_count"] == 1, kcg

        stuck = projection["stuck"]
        assert [node["node_id"] for node in stuck] == ["node_kcg"], stuck

        tree = projection["tree"]
        assert len(tree) == 1 and tree[0]["node_id"] == "node_root", tree
        assert tree[0]["children"][0]["node_id"] == "node_kcg", tree

        mermaid = projection["mermaid"]
        assert mermaid.startswith("flowchart TD"), mermaid
        assert "node_kcg" in mermaid and ":::blocked" in mermaid, mermaid
        assert "-->|subtopic_of|" in mermaid, mermaid

    # Public-safety gates at record time.
    try:
        result_log.build_explore_finding_event(
            goal_id=goal_id,
            title="leaky finding",
            evidence_refs=["C:\\\\work\\\\private\\\\notes.md"],
        )
        raise AssertionError("absolute evidence ref must be rejected")
    except ValueError:
        pass
    try:
        result_log.build_explore_node_event(
            goal_id=goal_id,
            title="Review C:\\\\work\\\\private\\\\notes.md",
        )
        raise AssertionError("absolute path in public text must be rejected")
    except ValueError:
        pass
    try:
        result_log.build_explore_finding_event(
            goal_id=goal_id,
            title="leaky summary",
            summary="See file:///tmp/private-notes.md for details",
        )
        raise AssertionError("file URL in public text must be rejected")
    except ValueError:
        pass
    try:
        result_log.build_explore_node_event(goal_id=goal_id, title="stuck node", status="blocked")
        raise AssertionError("blocked node without blocked_reason must be rejected")
    except ValueError:
        pass
    return projection


def lark_list_fixture(records: list[tuple[str, str, str]]) -> dict[str, object]:
    fields = ["LoopX Goal ID", "LoopX Result ID", "Title"]
    return {
        "ok": True,
        "data": {
            "fields": fields,
            "data": [[goal, result, title] for goal, result, title in records],
            "record_id_list": [f"rec_fixture_{index}" for index in range(len(records))],
        },
    }


def check_lark_sync_contract() -> None:
    goal_id = "explore-smoke-goal"
    events = build_sample_events(goal_id)
    projection = result_log.build_explore_result_projection(events, goal_id=goal_id)
    config = explore_results.LarkExploreConfig(
        **{"base_" + "token": "SMOKE_BASE"},
        table_ids={"nodes": "tblN", "edges": "tblE", "findings": "tblF"},
    )

    with tempfile.TemporaryDirectory(prefix="loopx-explore-smoke-") as tmp:
        config_path = Path(tmp) / ".loopx" / "lark-explore.json"

        # Dry-run: plans upserts, runs nothing, and leaks no local paths.
        dry = explore_results.sync_explore_results_to_lark(
            config,
            projection=projection,
            config_path=config_path,
            execute=False,
        )
        assert dry["ok"] is True and dry["execute"] is False, dry
        assert dry["row_counts"] == {"nodes": 2, "edges": 1, "findings": 1}, dry
        assert all(not item["command"]["executed"] for item in dry["records"]), dry
        record_blob = json.dumps(dry["records"], ensure_ascii=False)
        assert str(REPO_ROOT) not in record_blob, record_blob
        assert tmp not in record_blob, record_blob
        assert not ABS_PATH_RE.search(record_blob), record_blob

        # Executed sync creates records and remembers record ids.
        upsert_calls: list[list[str]] = []

        def fake_runner(args: list[str], cwd: Path | None, timeout: float | None) -> dict[str, object]:
            if "+record-list" in args:
                return {
                    "returncode": 0,
                    "stdout": json.dumps(lark_list_fixture([])),
                    "stderr": "",
                    "timed_out": False,
                }
            if "+record-upsert" in args:
                upsert_calls.append(list(args))
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {"ok": True, "data": {"record_id_list": [f"rec_new_{len(upsert_calls)}"]}}
                    ),
                    "stderr": "",
                    "timed_out": False,
                }
            raise AssertionError(args)

        first = explore_results.sync_explore_results_to_lark(
            config,
            projection=projection,
            config_path=config_path,
            execute=True,
            runner=fake_runner,
        )
        assert first["ok"] is True, first
        assert len(upsert_calls) == 4, upsert_calls
        assert all("--record-id" not in call for call in upsert_calls), upsert_calls
        stored = json.loads(config_path.read_text(encoding="utf-8"))
        assert len(stored["result_records"]) == 4, stored

        # Second executed sync updates the same rows by remembered record id.
        upsert_calls.clear()
        second = explore_results.sync_explore_results_to_lark(
            config,
            projection=projection,
            config_path=config_path,
            execute=True,
            runner=fake_runner,
        )
        assert second["ok"] is True, second
        assert len(upsert_calls) == 4, upsert_calls
        assert all("--record-id" in call for call in upsert_calls), upsert_calls
        edge_record = next(item for item in second["records"] if item["table"] == "edges")
        assert edge_record["values"]["From Node Link"] == [{"id": "rec_new_2"}], edge_record
        assert edge_record["values"]["To Node Link"] == [{"id": "rec_new_1"}], edge_record

        # Shared visibility redacts private links in row values.
        shared = explore_results.sync_explore_results_to_lark(
            config,
            projection=projection,
            config_path=config_path,
            sink_visibility="shared",
            execute=False,
        )
        shared_blob = json.dumps(shared["records"], ensure_ascii=False)
        assert "internal.example.invalid" not in shared_blob, shared_blob
        assert "[private-link-redacted]" in shared_blob, shared_blob


def check_lark_setup_and_card() -> None:
    goal_id = "explore-smoke-goal"
    projection = result_log.build_explore_result_projection(
        build_sample_events(goal_id), goal_id=goal_id
    )

    schema = explore_results.lark_explore_schema_payload()
    assert schema["schema_version"] == "loopx_lark_explore_result_board_v0", schema
    assert set(schema["tables"]) == {"nodes", "edges", "findings"}, schema
    edge_fields = schema["tables"]["edges"]["fields"]
    assert any(
        field.get("name") == "From Node Link"
        and field.get("type") == "link"
        and field.get("link_table") == "Nodes"
        for field in edge_fields
    ), edge_fields
    assert any(
        field.get("name") == "To Node Link"
        and field.get("type") == "link"
        and field.get("link_table") == "Nodes"
        for field in edge_fields
    ), edge_fields

    with tempfile.TemporaryDirectory(prefix="loopx-explore-smoke-") as tmp:
        config_path = Path(tmp) / ".loopx" / "lark-explore.json"
        dry = explore_results.setup_lark_explore_board(config_path=config_path, execute=False)
        assert dry["ok"] is True and not config_path.exists(), dry
        assert len(dry["commands"]) == 4, dry

        def fake_runner(args: list[str], cwd: Path | None, timeout: float | None) -> dict[str, object]:
            if "+base-create" in args:
                payload = {
                    "ok": True,
                    "data": {
                        "app_token": "SMOKE_BASE",
                        "base": {
                            "base_token": "SMOKE_BASE",
                            "url": "https://example.invalid/base/SMOKE_BASE",
                        },
                    },
                }
            elif "+table-create" in args:
                name = args[args.index("--name") + 1]
                payload = {"ok": True, "data": {"table_id": f"tbl{name}"}}
            else:
                raise AssertionError(args)
            return {"returncode": 0, "stdout": json.dumps(payload), "stderr": "", "timed_out": False}

        executed = explore_results.setup_lark_explore_board(
            config_path=config_path, execute=True, runner=fake_runner
        )
        assert executed["ok"] is True, executed
        assert executed["tables"] == {
            "nodes": "tblNodes",
            "edges": "tblEdges",
            "findings": "tblFindings",
        }, executed
        assert executed["board"]["base_url"] == "https://example.invalid/base/SMOKE_BASE", executed
        stored = json.loads(config_path.read_text(encoding="utf-8"))
        assert stored["board"]["tables"]["nodes"] == "tblNodes", stored
        assert stored["board"]["base_url"] == "https://example.invalid/base/SMOKE_BASE", stored

        config_path.write_bytes(b"\xef\xbb\xbf" + config_path.read_bytes())
        bom_payload = explore_results.read_lark_explore_local_config(config_path)
        assert bom_payload["ok"] is True, bom_payload
        assert bom_payload["board"]["base_token"] == "SMOKE_BASE", bom_payload

    card_payload = explore_results.build_explore_result_card(projection)
    assert card_payload["ok"] is True, card_payload
    assert card_payload["schema_version"] == "loopx_lark_explore_card_v0", card_payload
    markdown = card_payload["card_markdown"]
    assert "**Exploration map**: 2 nodes" in markdown, markdown
    assert "**Blocked**" in markdown and "vendor licence terms unclear" in markdown, markdown
    assert "[confirmed] Two open-source Lustre toolchains" in markdown, markdown
    card = card_payload["card"]
    assert card["header"]["title"]["content"].startswith("Exploration map:"), card
    assert card["elements"][0]["text"]["tag"] == "lark_md", card


def check_todo_branch_prediction_contract() -> None:
    goal_id = "explore-smoke-goal"
    projection = result_log.build_explore_result_projection(
        [
            result_log.build_explore_node_event(
                goal_id=goal_id,
                title="MATLAB Simulink code generation frontier",
                node_id="matlab_codegen_frontier",
                status="exploring",
                tags=["matlab", "codegen"],
            )
        ],
        goal_id=goal_id,
    )
    todos = [
        {
            "todo_id": "todo_primary",
            "index": 1,
            "status": "open",
            "text": "[P0] Validate MATLAB codegen topology mapping",
            "task_class": "advancement_task",
            "claimed_by": "codex-main-control",
            "required_write_scopes": ["loopx/capabilities/explore/**"],
        },
        {
            "todo_id": "todo_parallel",
            "index": 2,
            "status": "open",
            "text": "[P1] Add Simulink finding projection smoke",
            "task_class": "advancement_task",
            "required_write_scopes": ["examples/**"],
        },
        {
            "todo_id": "todo_conflict",
            "index": 3,
            "status": "open",
            "text": "[P1] Edit alternate topology predictor",
            "task_class": "advancement_task",
            "required_write_scopes": ["loopx/capabilities/explore/result_log.py"],
        },
        {
            "todo_id": "todo_other",
            "index": 4,
            "status": "open",
            "text": "[P0] Other agent owned branch",
            "task_class": "advancement_task",
            "claimed_by": "codex-side-agent",
        },
    ]
    plan = build_explore_todo_branch_plan(
        goal_id=goal_id,
        todos=todos,
        projection=projection,
        agent_id="codex-main-control",
        width=3,
    )
    assert plan["ok"] is True and plan["dry_run"] is True, plan
    assert plan["schema_version"] == "loopx_explore_todo_branch_plan_v0", plan
    assert plan["boundary"]["starts_agents"] is False, plan
    assert plan["scheduler"]["schema_version"] == "loopx_explore_speculative_scheduler_v0", plan
    assert plan["scheduler"]["strategy"] == "dspark_confidence_scheduled_prefix", plan
    assert set(plan["scheduler"]["ab_comparison"]) == {"baseline_serial", "dspark_selected"}, plan
    assert plan["ab_result"]["schema_version"] == "loopx_explore_branch_plan_ab_result_v0", plan
    assert plan["ab_result"]["baseline_serial_theta"] > 0, plan
    assert plan["ab_result"]["estimated_speedup_vs_baseline"] > 0, plan
    selected_ids = [item["todo_id"] for item in plan["selected_branches"]]
    assert selected_ids[:2] == ["todo_primary", "todo_parallel"], plan
    assert all("expected_evidence_units" in item for item in plan["selected_branches"]), plan
    rejected = {item["todo_id"]: item for item in plan["rejected_candidates"]}
    assert rejected["todo_conflict"]["selection_status"] == "rejected_hazard", plan
    assert rejected["todo_other"]["selection_status"] == "blocked_claimed_by_other", plan
    assert any("task-lease acquire" in command for command in plan["selected_branches"][0]["suggested_commands"]), plan

    worker_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=todos,
        projection=projection,
        agent_id="codex-main-control",
        worker_width=2,
        max_todos_per_branch=3,
    )
    assert worker_plan["ok"] is True and worker_plan["dry_run"] is True, worker_plan
    assert worker_plan["schema_version"] == "loopx_explore_worker_branch_plan_v0", worker_plan
    assert worker_plan["harness_compatibility"]["replaces_loopx_runtime"] is False, worker_plan
    assert worker_plan["boundary"]["starts_agents"] is False, worker_plan
    assert worker_plan["selected_worker_branch_count"] >= 1, worker_plan
    first_worker = worker_plan["selected_worker_branches"][0]
    assert len(first_worker["todo_bundle"]) >= 1, worker_plan
    assert first_worker["execution_contract"]["must_enter_loopx_harness"] is True, worker_plan
    assert worker_plan["ab_result"]["schema_version"] == "loopx_explore_worker_branch_plan_ab_result_v0", worker_plan
    assert worker_plan["ab_result"]["estimated_speedup_vs_baseline"] > 0, worker_plan
    assert any(
        event["event_type"] == "predicted"
        for event in worker_plan["accept_reject_trace"]
    ), worker_plan

    adaptive_worker_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=todos,
        projection=projection,
        agent_id="codex-main-control",
        worker_width=6,
        harness_profile="adaptive-resilient",
    )
    assert adaptive_worker_plan["ok"] is True, adaptive_worker_plan
    assert adaptive_worker_plan["harness_profile"] == "adaptive-resilient", adaptive_worker_plan
    assert adaptive_worker_plan["branch_fill_policy"] == "value-first", adaptive_worker_plan
    assert adaptive_worker_plan["selected_worker_branch_count"] <= 6, adaptive_worker_plan
    assert adaptive_worker_plan["harness_compatibility"]["duration_guard_controlled_by_planner"] is False, adaptive_worker_plan
    assert adaptive_worker_plan["harness_compatibility"]["fixed_worker_count_controlled_by_planner"] is False, adaptive_worker_plan
    assert adaptive_worker_plan["harness_compatibility"]["forces_full_branch_fill"] is False, adaptive_worker_plan
    assert adaptive_worker_plan["max_todos_per_branch_explicit"] is False, adaptive_worker_plan
    assert adaptive_worker_plan["harness_compatibility"]["adaptive_todo_batching"] is True, adaptive_worker_plan
    profile = adaptive_worker_plan["worker_harness_profile"]
    assert profile["duration_guard"]["enabled"] is False, profile
    assert profile["concurrency_policy"]["fixed_worker_count"] is False, profile
    assert profile["concurrency_policy"]["does_not_force_requested_width"] is True, profile
    assert profile["retry_policy"]["enabled"] is True, profile
    assert profile["infra_cooldown"]["enabled"] is True, profile
    assert any(
        0 < len(branch["todo_bundle"]) < 8
        for branch in adaptive_worker_plan["selected_worker_branches"]
    ), adaptive_worker_plan


def _router_smoke_todo(index: int, *, family: str, priority: str = "P0") -> dict[str, object]:
    return {
        "todo_id": f"todo_router_{family}_{index}",
        "index": index,
        "status": "open",
        "text": f"[{priority}] Probe {family} facet {index}",
        "task_class": "advancement_task",
        "required_write_scopes": [f"artifacts/{family}/**"],
    }


def check_worker_lane_router_contract() -> None:
    goal_id = "explore-smoke-router"

    # 1. Width is no longer silently clamped to 8: 12 distinct-family todos at
    #    worker_width=10 under independent-lane admission saturate all 10 lanes.
    families = [f"fam{index:02d}" for index in range(12)]
    wide_todos = [
        _router_smoke_todo(index + 1, family=family) for index, family in enumerate(families)
    ]
    wide_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=wide_todos,
        agent_id="codex-main-control",
        worker_width=10,
        harness_profile="adaptive-resilient",
    )
    assert wide_plan["worker_width"] == 10, wide_plan["worker_width"]
    assert wide_plan["scheduler_model"] == "independent_lane_admission", wide_plan["scheduler_model"]
    assert wide_plan["selected_worker_branch_count"] == 10, wide_plan["selected_worker_branch_count"]
    assert wide_plan["admission_audit"]["queue_exhausted"] is False, wide_plan["admission_audit"]
    outside = [
        branch
        for branch in wide_plan["rejected_worker_branches"]
        if branch.get("selection_status") == "outside_verification_budget"
    ]
    assert len(outside) == 2, [branch.get("branch_id") for branch in outside]

    # 2. Fewer todos than width: every idle lane is a queue-exhaustion, not a cap.
    narrow_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=wide_todos[:5],
        agent_id="codex-main-control",
        worker_width=10,
        harness_profile="adaptive-resilient",
    )
    assert narrow_plan["selected_worker_branch_count"] == 5, narrow_plan["selected_worker_branch_count"]
    assert narrow_plan["admission_audit"]["queue_exhausted"] is True, narrow_plan["admission_audit"]

    # 3. moe-router without router state still plans (router disabled but supported).
    bare_moe_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=wide_todos[:4],
        agent_id="codex-main-control",
        worker_width=4,
        harness_profile="moe-router",
    )
    assert bare_moe_plan["router"]["supported_by_profile"] is True, bare_moe_plan["router"]
    assert bare_moe_plan["router"]["enabled"] is False, bare_moe_plan["router"]
    assert bare_moe_plan["strategy"] == "independent_lane_worker_prediction", bare_moe_plan["strategy"]

    # 4. Aux-loss-free invariant: bias reorders routing but leaves value
    #    bookkeeping untouched. Two equal-score families; biasing the
    #    alphabetically-later one moves it first without changing evidence.
    fam_first, fam_second = "family_alpha", "family_beta"
    pair_todos = [
        _router_smoke_todo(1, family=fam_first),
        _router_smoke_todo(2, family=fam_second),
    ]
    biased_state = initial_router_state()
    biased_state["families"][scope_family_key(fam_second)] = {"bias": 0.4, "runs": 0}
    unbiased_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=pair_todos,
        agent_id="codex-main-control",
        worker_width=2,
        harness_profile="moe-router",
        router_state=initial_router_state(),
    )
    biased_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=pair_todos,
        agent_id="codex-main-control",
        worker_width=2,
        harness_profile="moe-router",
        router_state=biased_state,
    )
    assert unbiased_plan["router"]["enabled"] is True, unbiased_plan["router"]
    unbiased_order = [branch["affinity_key"] for branch in unbiased_plan["selected_worker_branches"]]
    biased_order = [branch["affinity_key"] for branch in biased_plan["selected_worker_branches"]]
    assert unbiased_order[0].endswith(fam_first), unbiased_order
    assert biased_order[0].endswith(fam_second), biased_order
    evidence_by_family = lambda plan: {  # noqa: E731
        branch["affinity_key"]: branch["expected_evidence_units"]
        for branch in plan["selected_worker_branches"]
    }
    assert evidence_by_family(unbiased_plan) == evidence_by_family(biased_plan), (
        evidence_by_family(unbiased_plan),
        evidence_by_family(biased_plan),
    )
    routed_branch = biased_plan["selected_worker_branches"][0]
    assert "router" in routed_branch and "routing_score" in routed_branch, routed_branch

    # 5. DSpark confident-prefix bundles: P0+P1 clear the calibrated threshold,
    #    P2 truncates into its own lane; a family observed rejecting everything
    #    collapses to single-todo bundles.
    bundle_todos = [
        _router_smoke_todo(1, family="family_gamma", priority="P0"),
        _router_smoke_todo(2, family="family_gamma", priority="P1"),
        _router_smoke_todo(3, family="family_gamma", priority="P2"),
    ]
    def _bundle_sizes(plan: dict[str, object]) -> list[int]:
        # Same-family lanes share a write-scope root, so the selection loop
        # keeps only the first as parallel-safe; bundle FORMATION is what is
        # under test here, so collect selected and rejected branches alike.
        branches = list(plan["selected_worker_branches"]) + [
            branch
            for branch in plan["rejected_worker_branches"]
            if branch.get("todo_bundle")
        ]
        return sorted(len(branch["todo_bundle"]) for branch in branches)

    bundle_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=bundle_todos,
        agent_id="codex-main-control",
        worker_width=3,
        harness_profile="moe-router",
        router_state=initial_router_state(),
    )
    assert _bundle_sizes(bundle_plan) == [1, 2], _bundle_sizes(bundle_plan)

    rejected_family_state = observe_epoch(
        initial_router_state(),
        epoch=1,
        probes=[
            {
                "family": scope_family_key("family_gamma"),
                "duration_minutes": 1.0,
                "observation_keys": [],
                "accepted": False,
                "retryable_infra_error": False,
            }
        ],
    )
    rejected_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=bundle_todos,
        agent_id="codex-main-control",
        worker_width=3,
        harness_profile="moe-router",
        router_state=rejected_family_state,
    )
    assert _bundle_sizes(rejected_plan) == [1, 1, 1], _bundle_sizes(rejected_plan)

    # 6. Opportunistic expansion: low novelty should not collapse a proven router
    #    to two lanes when the next candidates still have positive lane value.
    #    The expansion is bounded by value floors, not a blind fill rule.
    expansion_families = [f"expand_fam_{index:02d}" for index in range(10)]
    expansion_todos = [
        _router_smoke_todo(index + 1, family=family, priority="P1")
        for index, family in enumerate(expansion_families)
    ]
    expansion_state = initial_router_state()
    expansion_state["updated_epoch"] = 3
    expansion_state["totals"]["dispatches"] = 80
    for family in expansion_families:
        expansion_state["families"][scope_family_key(family)] = {
            "runs": 5,
            "value_rate_ema": 8.0,
            "duration_ema": 0.8,
            "accept_rate_ema": 1.0,
            "infra_ema": 0.0,
            "novelty_rate": 0.05,
            "last_run_epoch": 2,
            "bias": 0.0,
        }
    expansion_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=expansion_todos,
        agent_id="codex-main-control",
        worker_width=10,
        harness_profile="moe-router",
        router_state=expansion_state,
        load_profile={
            "parallel_wall_minutes": 8.0,
            "max_branch_minutes": 1.0,
            "branch_count": 10,
            "source": "smoke_high_interference_profile",
        },
    )
    expansion_audit = expansion_plan["admission_audit"]
    assert expansion_plan["selected_worker_branch_count"] >= 6, expansion_audit
    assert expansion_audit["opportunistic_admitted_count"] > 0, expansion_audit
    assert expansion_audit["core_lane_count"] < expansion_audit["admitted_lane_count"], expansion_audit
    assert expansion_audit["opportunistic_utilization_floor"] == 0.65, expansion_audit

    # 7. Router state lifecycle: the novelty ledger dedupes across epochs and
    #    coverage debt accrues bias for eligible-but-unrun families.
    fam_key = scope_family_key("family_alpha")
    state = observe_epoch(
        initial_router_state(),
        epoch=1,
        probes=[
            {
                "family": fam_key,
                "duration_minutes": 0.6,
                "observation_keys": ["obs_a", "obs_b"],
                "weighted_flags": {"flag_probe_ok": 2.0},
                "accepted": True,
                "retryable_infra_error": False,
            }
        ],
    )
    assert state["families"][fam_key]["novelty_rate"] == 1.0, state["families"][fam_key]
    state = observe_epoch(
        state,
        epoch=2,
        probes=[
            {
                "family": fam_key,
                "duration_minutes": 0.6,
                "observation_keys": ["obs_a", "obs_b"],
                "weighted_flags": {"flag_probe_ok": 2.0},
                "accepted": True,
                "retryable_infra_error": False,
            }
        ],
    )
    assert state["families"][fam_key]["novelty_rate"] == 0.0, state["families"][fam_key]
    idle_key = scope_family_key("family_beta")
    for epoch in range(3, 9):
        state = advance_epoch(state, epoch=epoch, eligible_families=[fam_key, idle_key])
    assert state["families"][idle_key]["bias"] > 0.2, state["families"][idle_key]
    assert state["families"][fam_key]["bias"] <= 0.0, state["families"][fam_key]

    # 8. Observed load profile calibrates admission instead of the 0.2 prior.
    calibrated_plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=wide_todos[:4],
        agent_id="codex-main-control",
        worker_width=4,
        harness_profile="moe-router",
        load_profile={
            "parallel_wall_minutes": 1.0,
            "max_branch_minutes": 1.0,
            "branch_count": 5,
        },
    )
    calibration = calibrated_plan["load_calibration"]
    assert calibration is not None and calibration["measured_load_factor"] == 0.0, calibration
    assert calibrated_plan["scheduler"]["load_factor"] < 0.2, calibrated_plan["scheduler"]["load_factor"]


def check_harness_domain_purity() -> None:
    """The exploration harness stack must stay software-agnostic.

    Domain vocabulary (target-software names, domain flag names, provider
    error codes) belongs to adapters and agent-authored data files, never to
    these modules. This gate is what keeps the harness reusable beyond any
    single system under exploration.
    """

    banned = (
        "simulink", "matlab", "mathworks", "stateflow",
        "sim_ok", "codegen_ok", "build_ok", "error 5001",
    )
    modules = (
        "loopx/capabilities/explore/harness_runtime.py",
        "loopx/capabilities/explore/router_state.py",
        "loopx/capabilities/explore/speculative_scheduler.py",
        "loopx/capabilities/explore/todo_branch_plan.py",
        "loopx/capabilities/explore/worker_branch_plan.py",
        "loopx/cli_commands/explore.py",
    )
    for module in modules:
        lowered = (REPO_ROOT / module).read_text(encoding="utf-8").lower()
        hits = [token for token in banned if token in lowered]
        assert not hits, f"domain vocabulary leaked into {module}: {hits}"


def check_cli_surface() -> None:
    goal_id = "explore-smoke-cli"
    with tempfile.TemporaryDirectory(prefix="loopx-explore-smoke-") as tmp:
        registry = Path(tmp) / ".loopx" / "registry.json"
        runtime_root = Path(tmp) / "runtime"
        project = Path(tmp) / "project"
        state_file = f".codex/goals/{goal_id}/ACTIVE_GOAL_STATE.md"
        (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
        (project / state_file).write_text(
            "---\n"
            "status: active\n"
            "updated_at: 2026-07-06T00:00:00+00:00\n"
            "---\n\n"
            "# Explore CLI Fixture\n\n"
            "## Agent Todo\n\n"
            "- [ ] [P0] Continue CLI topology experiment.\n"
            "  <!-- loopx:todo todo_id=todo_cli_primary status=open task_class=advancement_task claimed_by=codex-main-control required_write_scopes=loopx/capabilities/explore/** -->\n"
            "- [ ] [P1] Add CLI branch prediction smoke.\n"
            "  <!-- loopx:todo todo_id=todo_cli_parallel status=open task_class=advancement_task required_write_scopes=examples/** -->\n",
            encoding="utf-8",
        )
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "updated_at": "2026-07-06T00:00:00+00:00",
                    "common_runtime_root": str(runtime_root),
                    "goals": [
                        {
                            "id": goal_id,
                            "domain": "explore-smoke",
                            "status": "active",
                            "state_file": state_file,
                            "repo": str(project),
                            "adapter": {
                                "kind": "explore_result_layer",
                                "status": "connected-read-only",
                            },
                            "quota": {"compute": 1.0, "window_hours": 24},
                            "coordination": {
                                "primary_agent": "codex-main-control",
                                "registered_agents": [
                                    {"agent_id": "codex-main-control", "role": "primary"}
                                ],
                            },
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        def run_cli(*extra_args: str) -> dict[str, object]:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "loopx.cli",
                    "--format",
                    "json",
                    "--registry",
                    str(registry),
                    "--runtime-root",
                    str(runtime_root),
                    *extra_args,
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return json.loads(result.stdout)

        node = run_cli(
            "explore",
            "node",
            "--goal-id",
            goal_id,
            "--title",
            "CLI topology root",
            "--node-id",
            "node_cli_root",
            "--status",
            "exploring",
        )
        assert node["ok"] is True and node["result_id"] == "node_cli_root", node
        finding = run_cli(
            "explore",
            "finding",
            "--goal-id",
            goal_id,
            "--title",
            "CLI-visible finding",
            "--node",
            "node_cli_root",
            "--status",
            "tentative",
        )
        assert finding["ok"] is True, finding
        summary = run_cli("explore", "summary", "--goal-id", goal_id)
        assert summary["counts"]["node_count"] == 1, summary
        assert summary["counts"]["finding_count"] == 1, summary
        graph = run_cli("explore", "graph", "--goal-id", goal_id)
        assert str(graph["mermaid"]).startswith("flowchart TD"), graph
        branch_plan = run_cli(
            "explore",
            "todo-branch-plan",
            "--goal-id",
            goal_id,
            "--agent-id",
            "codex-main-control",
            "--width",
            "2",
        )
        assert branch_plan["ok"] is True and branch_plan["selected_count"] == 2, branch_plan
        assert branch_plan["boundary"]["claims_todos"] is False, branch_plan
        assert branch_plan["selected_branches"][0]["todo_id"] == "todo_cli_primary", branch_plan
        assert set(branch_plan["scheduler"]["ab_comparison"]) == {"baseline_serial", "dspark_selected"}, branch_plan
        assert branch_plan["ab_result"]["estimated_speedup_vs_baseline"] > 0, branch_plan
        worker_branch_plan = run_cli(
            "explore",
            "worker-branch-plan",
            "--goal-id",
            goal_id,
            "--agent-id",
            "codex-main-control",
            "--worker-width",
            "2",
            "--max-todos-per-branch",
            "2",
        )
        assert worker_branch_plan["ok"] is True, worker_branch_plan
        assert worker_branch_plan["schema_version"] == "loopx_explore_worker_branch_plan_v0", worker_branch_plan
        assert worker_branch_plan["harness_compatibility"]["uses_loopx_todo_projection"] is True, worker_branch_plan
        assert worker_branch_plan["boundary"]["claims_todos"] is False, worker_branch_plan
        assert worker_branch_plan["selected_worker_branch_count"] >= 1, worker_branch_plan
        assert worker_branch_plan["selected_worker_branches"][0]["execution_contract"]["requires_quota_should_run"] is True, worker_branch_plan
        adaptive_worker_branch_plan = run_cli(
            "explore",
            "worker-branch-plan",
            "--goal-id",
            goal_id,
            "--agent-id",
            "codex-main-control",
            "--harness-profile",
            "adaptive-resilient",
            "--worker-width",
            "5",
        )
        assert adaptive_worker_branch_plan["ok"] is True, adaptive_worker_branch_plan
        assert adaptive_worker_branch_plan["harness_profile"] == "adaptive-resilient", adaptive_worker_branch_plan
        assert adaptive_worker_branch_plan["branch_fill_policy"] == "value-first", adaptive_worker_branch_plan
        assert adaptive_worker_branch_plan["worker_harness_profile"]["duration_guard"]["enabled"] is False, adaptive_worker_branch_plan
        assert adaptive_worker_branch_plan["harness_compatibility"]["fixed_worker_count_controlled_by_planner"] is False, adaptive_worker_branch_plan
        assert adaptive_worker_branch_plan["harness_compatibility"]["forces_full_branch_fill"] is False, adaptive_worker_branch_plan
        assert adaptive_worker_branch_plan["max_todos_per_branch_explicit"] is False, adaptive_worker_branch_plan
        assert adaptive_worker_branch_plan["harness_compatibility"]["adaptive_todo_batching"] is True, adaptive_worker_branch_plan
        router_state_path = Path(tmp) / "router_state.json"
        router_state_path.write_text(
            json.dumps(initial_router_state(), indent=2) + "\n",
            encoding="utf-8",
        )
        load_profile_path = Path(tmp) / "load_profile.json"
        load_profile_path.write_text(
            json.dumps(
                {
                    "parallel_wall_minutes": 0.8,
                    "max_branch_minutes": 0.75,
                    "branch_count": 5,
                    "source": "smoke_observed_profile",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        moe_worker_branch_plan = run_cli(
            "explore",
            "worker-branch-plan",
            "--goal-id",
            goal_id,
            "--agent-id",
            "codex-main-control",
            "--harness-profile",
            "moe-router",
            "--worker-width",
            "5",
            "--router-state",
            str(router_state_path),
            "--load-profile",
            str(load_profile_path),
        )
        assert moe_worker_branch_plan["ok"] is True, moe_worker_branch_plan
        assert moe_worker_branch_plan["harness_profile"] == "moe-router", moe_worker_branch_plan
        assert moe_worker_branch_plan["router"]["enabled"] is True, moe_worker_branch_plan["router"]
        assert moe_worker_branch_plan["scheduler_model"] == "independent_lane_admission", moe_worker_branch_plan
        assert moe_worker_branch_plan["load_calibration"]["source"] == "smoke_observed_profile", moe_worker_branch_plan
        assert moe_worker_branch_plan["admission_audit"] is not None, moe_worker_branch_plan
        assert (
            moe_worker_branch_plan["max_todos_per_branch_source"]
            == "confident_prefix_scheduler_safety_cap"
        ), moe_worker_branch_plan
        assert (
            moe_worker_branch_plan["harness_compatibility"]["confidence_prefix_todo_batching"]
            is True
        ), moe_worker_branch_plan
        sync = run_cli(
            "explore",
            "feishu-sync",
            "--goal-id",
            goal_id,
            "--config-path",
            str(Path(tmp) / ".loopx" / "lark-explore.json"),
            "--base-token",
            "SMOKE_BASE",
            "--table-id-nodes",
            "tblN",
            "--table-id-edges",
            "tblE",
            "--table-id-findings",
            "tblF",
        )
        assert sync["ok"] is True and sync["execute"] is False, sync
        assert tmp not in json.dumps(sync["records"], ensure_ascii=False), sync

        config_path = Path(tmp) / ".loopx" / "stored-lark-explore.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(
                {
                    "schema_version": "loopx_lark_explore_local_config_v0",
                    "board": {
                        "base_token": "SMOKE_BASE",
                        "tables": {"nodes": "tblN", "edges": "tblE", "findings": "tblF"},
                        "cli_bin": "stored-lark-cli",
                        "identity": "user",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        stored_cli_sync = run_cli(
            "explore",
            "feishu-sync",
            "--goal-id",
            goal_id,
            "--config-path",
            str(config_path),
        )
        assert stored_cli_sync["ok"] is True, stored_cli_sync
        assert stored_cli_sync["commands"][0]["command"].startswith("stored-lark-cli "), stored_cli_sync

        # Error contract: unknown target without config fails with exit 1.
        error = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime_root),
                "explore",
                "feishu-sync",
                "--goal-id",
                goal_id,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert error.returncode == 1, error.stdout
        error_payload = json.loads(error.stdout)
        assert error_payload["ok"] is False, error_payload
        assert "feishu-setup" in str(error_payload["error"]), error_payload


def main() -> int:
    check_result_log_contract()
    check_lark_sync_contract()
    check_lark_setup_and_card()
    check_todo_branch_prediction_contract()
    check_worker_lane_router_contract()
    check_harness_domain_purity()
    check_cli_surface()
    print("explore result layer smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
