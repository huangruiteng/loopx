#!/usr/bin/env python3
"""Smoke-test the public local_agent_launch_plan_v0 fixture and contract."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "local-agent-launch-plan.public.json"
CONTRACT_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "local-agent-launch-plan-v0.md"
PROTOCOL_INDEX_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"
DOCS_INDEX_PATH = REPO_ROOT / "docs" / "README.md"
STATUS_CONTRACT_PATH = REPO_ROOT / "docs" / "status-data-contract.md"
HOST_SURFACE_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "host-integration-surface-v0.md"

ALLOWED_AGENT_ROLES = {"primary", "side_agent", "reviewer", "observer", "blocked"}
ALLOWED_ASSIGNMENT_LANES = {
    "primary_control",
    "bounded_delivery",
    "review_handoff",
    "monitor_only",
    "blocked",
}
ALLOWED_WAITING_ON = {"agent", "primary", "user", "controller", "runtime", "none"}
ALLOWED_GATE_STATES = {"clear", "user_todo", "operator_gate", "blocked", "deferred"}
ALLOWED_QUOTA_STATES = {"eligible", "throttled", "operator_gate", "blocked"}
ALLOWED_LAUNCH_STATES = {"preview_only", "blocked", "future_gated"}
REQUIRED_SOURCES = {"registry", "quota_should_run", "todo_projection", "run_history"}
REQUIRED_FUTURE_GATES = {
    "server_daemon_launch",
    "external_agent_execution",
    "credentialed_host_actions",
    "state_write_from_preview",
}
REQUIRED_STATUS_FIELDS = {
    "waiting_on",
    "next_action",
    "user_action_required",
    "agent_can_continue",
    "first_agent_todo",
    "gate_state",
    "quota_state",
    "launch_state",
}
PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r'https?://[^\s"]*(?:corp-only|restricted-host)[^\s"]*'),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_public_safe(text: str, label: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"{label} matched private pattern {pattern.pattern!r}")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


def main() -> int:
    fixture_text = read(FIXTURE_PATH)
    contract = read(CONTRACT_PATH)
    protocol_index = read(PROTOCOL_INDEX_PATH)
    docs_index = read(DOCS_INDEX_PATH)
    status_contract = read(STATUS_CONTRACT_PATH)
    host_surface = read(HOST_SURFACE_PATH)

    for label, text in {
        "fixture": fixture_text,
        "contract": contract,
        "protocol index": protocol_index,
        "docs index": docs_index,
        "status contract": status_contract,
        "host surface": host_surface,
    }.items():
        assert_public_safe(text, label)

    for needle in [
        "local_agent_launch_plan_v0",
        "mode=dry_run",
        "configured_agents",
        "role_assignments",
        "launch_preview",
        "server_daemon_launch",
        "external_agent_execution",
        "credentialed_host_actions",
        "Status And Evidence Projection",
    ]:
        assert_contains(contract, needle, "contract")
    assert_contains(protocol_index, "local_agent_launch_plan_v0", "protocol index")
    assert_contains(docs_index, "Local agent launch plan v0", "docs index")
    assert_contains(status_contract, "local_agent_launch_plan_v0", "status contract")
    assert_contains(host_surface, "local_agent_launch_plan_v0", "host surface")

    payload = json.loads(fixture_text)
    item = payload["attention_queue"]["items"][0]
    plan = item["local_agent_launch_plan"]

    assert plan["schema_version"] == "local_agent_launch_plan_v0", plan
    assert plan["mode"] == "dry_run", plan
    assert plan["goal_id"] == item["goal_id"], plan
    assert plan["primary_agent_id"] == "codex-main-control", plan

    configured_agents = plan["configured_agents"]
    agent_ids = {agent["agent_id"] for agent in configured_agents}
    assert "codex-main-control" in agent_ids, configured_agents
    assert "codex-side-bypass" in agent_ids, configured_agents
    assert len(agent_ids) == len(configured_agents), configured_agents
    for agent in configured_agents:
        assert agent["role"] in ALLOWED_AGENT_ROLES, agent
        assert agent["source"] == "registry.coordination.registered_agents", agent
        assert isinstance(agent["scope_summary"], str) and agent["scope_summary"], agent
        assert isinstance(agent["can_receive_work"], bool), agent
        assert isinstance(agent["blocked_by"], list), agent

    assignments = plan["role_assignments"]
    assignment_ids = {assignment["agent_id"] for assignment in assignments}
    assert agent_ids <= assignment_ids, assignments
    for assignment in assignments:
        assert assignment["lane"] in ALLOWED_ASSIGNMENT_LANES, assignment
        assert isinstance(assignment["responsibility"], str) and assignment["responsibility"], assignment
        assert isinstance(assignment["claim_policy"], str) and assignment["claim_policy"], assignment

    previews = plan["launch_preview"]
    assert len(previews) >= 2, previews
    for preview in previews:
        assert preview["agent_id"] in agent_ids, preview
        assert isinstance(preview["next_step_label"], str) and preview["next_step_label"], preview
        assert preview["worktree_policy"], preview
        host_execution = preview["host_execution"]
        assert host_execution["will_start_process"] is False, preview
        assert host_execution["tool_call_allowed"] is False, preview
        assert host_execution["shell_command"] is None, preview
        assert host_execution["daemon_required"] is False, preview
        assert host_execution["external_service_call"] is False, preview

    status = plan["status_projection"]
    assert REQUIRED_STATUS_FIELDS <= set(status), status
    assert status["waiting_on"] in ALLOWED_WAITING_ON, status
    assert status["gate_state"] in ALLOWED_GATE_STATES, status
    assert status["quota_state"] in ALLOWED_QUOTA_STATES, status
    assert status["launch_state"] in ALLOWED_LAUNCH_STATES, status
    assert status["user_action_required"] is False, status
    assert status["agent_can_continue"] is True, status

    evidence = plan["evidence_projection"]
    assert evidence["source_refs"], evidence
    assert evidence["validation_refs"], evidence
    for flag in [
        "raw_logs_copied",
        "raw_transcripts_copied",
        "credentials_copied",
        "private_paths_copied",
    ]:
        assert evidence[flag] is False, (flag, evidence)
    assert isinstance(evidence["public_safe_summary"], str) and evidence["public_safe_summary"], evidence

    future_gates = {gate["capability"]: gate for gate in plan["future_gates"]}
    assert REQUIRED_FUTURE_GATES <= set(future_gates), future_gates
    for gate in future_gates.values():
        assert gate["state"] in {"future_gated", "blocked_without_authority"}, gate
        assert gate["required_contract"].endswith("_v0"), gate

    truth = plan["truth_contract"]
    assert set(truth["source_of_truth"]) == REQUIRED_SOURCES, truth
    assert truth["plan_is_authoritative"] is False, truth
    assert truth["plan_is_executable"] is False, truth
    assert truth["write_api"] is False, truth
    assert truth["launch_command_allowed"] is False, truth

    boundary = plan["boundary"]
    assert boundary["public_fixture"] is True, boundary
    assert boundary["runtime_launcher_enabled"] is False, boundary
    assert boundary["raw_logs_allowed"] is False, boundary
    assert boundary["raw_transcripts_allowed"] is False, boundary
    assert boundary["credentials_allowed"] is False, boundary
    assert boundary["private_paths_allowed"] is False, boundary

    forbidden_keys = {
        "agent_command",
        "process_id",
        "access_token",
        "credential",
        "raw_log",
        "raw_transcript",
    }
    fixture_keys = set(json.dumps(payload, sort_keys=True).split('"'))
    assert not (fixture_keys & forbidden_keys), fixture_keys & forbidden_keys

    print("local-agent-launch-plan-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
