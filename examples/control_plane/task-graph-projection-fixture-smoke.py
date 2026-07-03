#!/usr/bin/env python3
"""Smoke-test the public task_graph_projection_v0 fixture and contract."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.cli_commands.status import review_packet_handoff_only_payload  # noqa: E402
from loopx.review_packet import build_review_packet  # noqa: E402
from loopx.status import build_task_graph_projection  # noqa: E402

FIXTURE_PATH = REPO_ROOT / "examples/fixtures/task-graph-projection-status.public.json"
CONTRACT_PATH = REPO_ROOT / "docs/reference/protocols/task-graph-projection-v0.md"
STATUS_CONTRACT_PATH = REPO_ROOT / "docs/status-data-contract.md"
PROTOCOL_INDEX_PATH = REPO_ROOT / "docs/reference/protocols/README.md"
STATE_MODEL_PATH = REPO_ROOT / "docs/state-interaction-model.md"

ALLOWED_NODE_KINDS = {
    "deliverable",
    "gate",
    "gate_summary",
    "lease",
    "validation",
    "repair",
    "handoff",
    "evidence",
}
ALLOWED_NODE_STATES = {"open", "ready", "blocked", "done", "waiting", "unknown"}
ALLOWED_EDGE_RELATIONS = {
    "depends_on",
    "blocks",
    "validates",
    "repairs",
    "audits",
    "continues",
    "hands_off_to",
    "supersedes",
}
ALLOWED_REF_KEYS = {
    "todo_ids",
    "gate_ids",
    "goal_ids",
    "lease_ids",
    "run_ids",
    "review_packet_ids",
}
SOURCE_OF_TRUTH = {
    "event_ledger",
    "active_goal_state",
    "todos",
    "gates",
    "leases",
    "run_history",
}
PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


def assert_public_safe(text: str, label: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"{label} matched private pattern {pattern.pattern!r}")


def assert_refs(refs: object, label: str) -> None:
    assert isinstance(refs, dict) and refs, (label, refs)
    unknown = set(refs) - ALLOWED_REF_KEYS
    assert not unknown, (label, unknown)
    for key, values in refs.items():
        assert isinstance(values, list) and values, (label, key, values)
        for value in values:
            assert isinstance(value, str) and value, (label, key, value)
            assert not value.startswith("/"), (label, key, value)


def assert_projection_shape(
    projection: dict[str, object],
    *,
    goal_id: str,
    label: str,
    min_nodes: int = 4,
    min_edges: int = 3,
) -> None:
    assert projection["schema_version"] == "task_graph_projection_v0", (label, projection)
    assert projection["mode"] == "read_only", (label, projection)
    assert projection["goal_id"] == goal_id, (label, projection)
    assert set(projection["derived_from"]["source_of_truth"]) == SOURCE_OF_TRUTH, (label, projection)
    truth = projection["truth_contract"]
    assert truth["event_ledger_is_source_of_truth"] is True, (label, truth)
    assert truth["projection_is_writable"] is False, (label, truth)
    assert truth["write_api"] is False, (label, truth)
    limits = projection["limits"]
    assert limits["user_gate_node_limit"] == 2, (label, limits)
    assert limits["user_gate_open_count"] >= 0, (label, limits)
    assert limits["user_gate_truncated_count"] >= 0, (label, limits)

    nodes = projection["nodes"]
    edges = projection["edges"]
    assert isinstance(nodes, list) and len(nodes) >= min_nodes, (label, nodes)
    assert isinstance(edges, list) and len(edges) >= min_edges, (label, edges)
    node_ids = [node["node_id"] for node in nodes]
    assert len(node_ids) == len(set(node_ids)), (label, node_ids)
    node_id_set = set(node_ids)

    for node in nodes:
        assert node["kind"] in ALLOWED_NODE_KINDS, (label, node)
        assert node["state"] in ALLOWED_NODE_STATES, (label, node)
        assert isinstance(node["title"], str) and node["title"], (label, node)
        assert_refs(node.get("refs"), f"{label} node {node['node_id']}")

    for edge in edges:
        assert edge["relation"] in ALLOWED_EDGE_RELATIONS, (label, edge)
        assert edge["from_node_id"] in node_id_set, (label, edge)
        assert edge["to_node_id"] in node_id_set, (label, edge)
        assert edge["from_node_id"] != edge["to_node_id"], (label, edge)
        assert isinstance(edge["reason"], str) and edge["reason"], (label, edge)
        if "refs" in edge:
            assert_refs(edge["refs"], f"{label} edge {edge['edge_id']}")


def assert_runtime_projection_builder() -> None:
    goal_id = "runtime-task-graph"
    item = {
        "goal_id": goal_id,
        "status": "operator_gate",
        "waiting_on": "controller",
        "recommended_action": "Implement the task graph projection runtime seam.",
        "user_todos": {
            "open_count": 5,
            "items": [
                {
                    "todo_id": "todo_review_gate",
                    "text": "[P1] Review runtime projection before merge.",
                    "status": "open",
                    "task_class": "user_gate",
                },
                {
                    "todo_id": "todo_policy_gate",
                    "text": "[P1] Confirm task graph cap and truncation policy.",
                    "status": "open",
                    "task_class": "user_gate",
                },
                {
                    "todo_id": "todo_dashboard_gate",
                    "text": "[P2] Decide whether dashboard should expand graph details.",
                    "status": "open",
                    "task_class": "user_gate",
                },
                {
                    "todo_id": "todo_packet_gate",
                    "text": "[P2] Confirm review packet detail path for full gate list.",
                    "status": "open",
                    "task_class": "user_gate",
                },
                {
                    "todo_id": "todo_cold_path_gate",
                    "text": "[P2] Confirm cold path remains the full user todo list.",
                    "status": "open",
                    "task_class": "user_gate",
                },
            ]
        },
        "agent_todos": {
            "items": [
                {
                    "todo_id": "todo_runtime_projection",
                    "text": "[P1] Implement task graph projection.",
                    "title": "Implement task graph projection.",
                    "status": "open",
                    "claimed_by": "codex-main-control",
                }
            ]
        },
        "autonomous_replan_obligation": {
            "schema_version": "autonomous_replan_obligation_v0",
            "recommended_action": "Recover selected work if it stalls.",
        },
    }
    goal = {"id": goal_id}
    latest_runs = [
        {
            "generated_at": "2026-06-21T13:00:00Z",
            "classification": "task_graph_projection_audit_continuation_smoke",
            "recommended_action": "Continue the selected projection lane after audit evidence is recorded.",
        }
    ]
    projection = build_task_graph_projection(item, goal=goal, goal_latest_runs=latest_runs)
    assert isinstance(projection, dict), projection
    assert_projection_shape(projection, goal_id=goal_id, label="runtime projection", min_nodes=5, min_edges=6)
    kinds = {node["kind"] for node in projection["nodes"]}
    assert {"deliverable", "gate", "lease", "validation", "repair"} <= kinds, projection
    assert "gate_summary" in kinds, projection
    gate_nodes = [node for node in projection["nodes"] if node["kind"] == "gate"]
    summary_nodes = [node for node in projection["nodes"] if node["kind"] == "gate_summary"]
    assert len(gate_nodes) == 2, projection
    assert len(summary_nodes) == 1, projection
    assert summary_nodes[0]["title"] == "3 more open user gates not expanded", summary_nodes
    assert projection["limits"] == {
        "user_gate_node_limit": 2,
        "user_gate_open_count": 5,
        "user_gate_truncated_count": 3,
    }, projection["limits"]
    relations = {edge["relation"] for edge in projection["edges"]}
    assert {"blocks", "depends_on", "validates", "repairs", "audits", "continues"} <= relations, projection
    forbidden_keys = {"write_command", "agent_command", "raw_log", "raw_transcript"}
    projection_keys = set(json.dumps(projection, sort_keys=True).split('"'))
    assert not (projection_keys & forbidden_keys), projection_keys & forbidden_keys

    status_payload = {
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "attention_queue": {
            "items": [
                {
                    **item,
                    "task_graph_projection": projection,
                    "project_asset": {
                        "next_action": "Implement the task graph projection runtime seam.",
                        "stop_condition": "stop before write authority or raw evidence export",
                    },
                }
            ]
        },
        "run_history": {"goals": [goal]},
    }
    packet = build_review_packet(status_payload, goal_id=goal_id)
    assert packet["ok"] is True, packet
    assert packet["task_graph_projection"] == projection, packet
    handoff_only = review_packet_handoff_only_payload(packet)
    assert "task_graph_projection" not in handoff_only, handoff_only
    assert_public_safe(json.dumps(packet, sort_keys=True), "runtime review packet")


def main() -> int:
    fixture_text = read(FIXTURE_PATH)
    contract = read(CONTRACT_PATH)
    status_contract = read(STATUS_CONTRACT_PATH)
    protocol_index = read(PROTOCOL_INDEX_PATH)
    state_model = read(STATE_MODEL_PATH)

    for label, text in {
        "fixture": fixture_text,
        "contract": contract,
        "status contract": status_contract,
    }.items():
        assert_public_safe(text, label)

    for needle in [
        "attention_queue.items[].task_graph_projection",
        "loopx --format json review-packet --goal-id <goal-id>",
        "event ledger",
        "active goal state",
        "projection_is_writable=false",
        "write_api=false",
        "todo_ids",
        "gate_ids",
        "lease_ids",
        "run_ids",
        "audits",
        "continues",
        "repair, audit, and continuation relations",
    ]:
        assert_contains(contract, needle, "contract")

    assert_contains(status_contract, "task_graph_projection_v0", "status contract")
    assert_contains(protocol_index, "task_graph_projection_v0", "protocol index")
    assert_contains(state_model, "task-graph-projection-v0.md", "state model")

    payload = json.loads(fixture_text)
    item = payload["attention_queue"]["items"][0]
    projection = item["task_graph_projection"]

    assert_projection_shape(projection, goal_id=item["goal_id"], label="fixture projection")

    forbidden_keys = {"write_command", "agent_command", "raw_log", "raw_transcript"}
    fixture_keys = set(json.dumps(payload, sort_keys=True).split('"'))
    assert not (fixture_keys & forbidden_keys), fixture_keys & forbidden_keys
    assert_runtime_projection_builder()

    print("task-graph-projection-fixture-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
