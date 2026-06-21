#!/usr/bin/env python3
"""Smoke-test the public task_graph_projection_v0 fixture and contract."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "examples/fixtures/task-graph-projection-status.public.json"
CONTRACT_PATH = REPO_ROOT / "docs/reference/protocols/task-graph-projection-v0.md"
STATUS_CONTRACT_PATH = REPO_ROOT / "docs/status-data-contract.md"
PROTOCOL_INDEX_PATH = REPO_ROOT / "docs/reference/protocols/README.md"
STATE_MODEL_PATH = REPO_ROOT / "docs/state-interaction-model.md"

ALLOWED_NODE_KINDS = {
    "deliverable",
    "gate",
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
    "hands_off_to",
    "supersedes",
}
ALLOWED_REF_KEYS = {
    "todo_ids",
    "gate_ids",
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
    ]:
        assert_contains(contract, needle, "contract")

    assert_contains(status_contract, "task_graph_projection_v0", "status contract")
    assert_contains(protocol_index, "task_graph_projection_v0", "protocol index")
    assert_contains(state_model, "task-graph-projection-v0.md", "state model")

    payload = json.loads(fixture_text)
    item = payload["attention_queue"]["items"][0]
    projection = item["task_graph_projection"]

    assert projection["schema_version"] == "task_graph_projection_v0", projection
    assert projection["mode"] == "read_only", projection
    assert projection["goal_id"] == item["goal_id"], projection
    assert set(projection["derived_from"]["source_of_truth"]) == SOURCE_OF_TRUTH, projection
    truth = projection["truth_contract"]
    assert truth["event_ledger_is_source_of_truth"] is True, truth
    assert truth["projection_is_writable"] is False, truth
    assert truth["write_api"] is False, truth

    nodes = projection["nodes"]
    edges = projection["edges"]
    assert isinstance(nodes, list) and len(nodes) >= 4, nodes
    assert isinstance(edges, list) and len(edges) >= 3, edges
    node_ids = [node["node_id"] for node in nodes]
    assert len(node_ids) == len(set(node_ids)), node_ids
    node_id_set = set(node_ids)

    for node in nodes:
        assert node["kind"] in ALLOWED_NODE_KINDS, node
        assert node["state"] in ALLOWED_NODE_STATES, node
        assert isinstance(node["title"], str) and node["title"], node
        assert_refs(node.get("refs"), f"node {node['node_id']}")

    for edge in edges:
        assert edge["relation"] in ALLOWED_EDGE_RELATIONS, edge
        assert edge["from_node_id"] in node_id_set, edge
        assert edge["to_node_id"] in node_id_set, edge
        assert edge["from_node_id"] != edge["to_node_id"], edge
        assert isinstance(edge["reason"], str) and edge["reason"], edge
        if "refs" in edge:
            assert_refs(edge["refs"], f"edge {edge['edge_id']}")

    forbidden_keys = {"write_command", "agent_command", "raw_log", "raw_transcript"}
    fixture_keys = set(json.dumps(payload, sort_keys=True).split('"'))
    assert not (fixture_keys & forbidden_keys), fixture_keys & forbidden_keys

    print("task-graph-projection-fixture-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
