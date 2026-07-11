#!/usr/bin/env python3
"""Exercise the default-off peer supervisor configuration and prompt contract."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.cli import main as cli_main  # noqa: E402
from loopx.configure_goal import configure_goal  # noqa: E402
from loopx.control_plane.agents.supervisor import (  # noqa: E402
    HOST_CAPABILITIES_BY_DECISION,
    SupervisorDecisionKind,
    build_supervisor_prompt,
    normalize_supervisor_decision,
    peer_supervisor_for_goal,
)


GOAL_ID = "peer-supervisor-fixture"
AGENTS = ["codex-alpha", "codex-beta", "codex-gamma"]


def read_goal(registry_path: Path) -> dict:
    return json.loads(registry_path.read_text(encoding="utf-8"))["goals"][0]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-peer-supervisor-") as tmp:
        root = Path(tmp)
        state_file = root / "ACTIVE_GOAL_STATE.md"
        state_file.write_text("# Active Goal State\n", encoding="utf-8")
        registry_path = root / "registry.json"
        registry_path.write_text(
            json.dumps(
                {
                    "goals": [
                        {
                            "id": GOAL_ID,
                            "repo": str(root),
                            "state_file": state_file.name,
                            "coordination": {
                                "agent_model": "peer_v1",
                                "registered_agents": AGENTS,
                            },
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        assert peer_supervisor_for_goal(read_goal(registry_path)) is None

        preview = configure_goal(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            supervisor_agent=AGENTS[0],
        )
        supervisor = preview["after"]["supervisor"]
        assert preview["dry_run"] is True, preview
        assert supervisor == {
            "schema_version": "peer_supervisor_v0",
            "enabled": True,
            "agent_id": AGENTS[0],
            "supervised_agents": AGENTS[1:],
            "execution_mode": "proposal_only",
        }, supervisor
        assert read_goal(registry_path)["coordination"].get("supervisor") is None

        applied = configure_goal(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            supervisor_agent=AGENTS[0],
            supervised_agents=[AGENTS[2]],
            execute=True,
        )
        assert applied["written"] is True, applied
        assert applied["supervisor_prompt"]["status"] == "ready", applied
        assert "supervisor-prompt" in applied["supervisor_prompt"]["command"], applied
        goal = read_goal(registry_path)
        assert "primary_agent" not in goal["coordination"], goal
        configured = peer_supervisor_for_goal(goal)
        assert configured["supervised_agents"] == [AGENTS[2]], configured

        prompt = build_supervisor_prompt(
            goal_id=GOAL_ID,
            active_state=str(state_file),
            supervisor=configured,
        )
        contract = prompt["supervisor_contract"]
        assert contract["peer_authority"] == "equal_identity_authority", contract
        assert contract["supervisor_authority"] == "proposal_only", contract
        assert contract["user_interaction"]["user_may_interact_with_any_peer"] is True
        assert contract["decision_contract"]["kinds"] == [
            kind.value for kind in SupervisorDecisionKind
        ]
        assert HOST_CAPABILITIES_BY_DECISION["inject"] == [
            "session_message_injection"
        ]
        assert HOST_CAPABILITIES_BY_DECISION["discard"] == ["session_termination"]
        task_body = prompt["task_body"]
        assert "not a durable leader" in task_body, task_body
        assert "proposal-only" in task_body, task_body
        assert "evidence-log" in task_body and "quota should-run" in task_body, task_body
        assert f"status --goal-id {GOAL_ID} --agent-id {AGENTS[2]}" in task_body
        assert f"quota should-run --goal-id {GOAL_ID} --agent-id {AGENTS[2]}" not in task_body

        decision = normalize_supervisor_decision(
            {
                "decision_id": "handoff-1",
                "kind": "handoff",
                "source_agent_id": AGENTS[2],
                "target_agent_id": AGENTS[1],
                "state_ref": "runtime-state:42",
                "reason_codes": ["scope-overlap"],
                "evidence_refs": ["effect:42"],
            },
            supervisor={**configured, "supervised_agents": AGENTS[1:]},
        )
        assert decision["execution_status"] == "proposal_only", decision
        assert decision["required_host_capabilities"] == [
            "session_state_fork",
            "workspace_state_transfer",
        ], decision

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "--registry",
                    str(registry_path),
                    "supervisor-prompt",
                    "--format",
                    "json",
                    "--goal-id",
                    GOAL_ID,
                    "--agent-id",
                    AGENTS[0],
                ]
            )
        assert exit_code == 0, stdout.getvalue()
        cli_payload = json.loads(stdout.getvalue())
        assert cli_payload["agent_id"] == AGENTS[0], cli_payload
        assert cli_payload["supervisor_contract"]["supervised_agents"] == [
            AGENTS[2]
        ], cli_payload

        try:
            configure_goal(
                registry_path=registry_path,
                goal_id=GOAL_ID,
                supervisor_agent=AGENTS[0],
                supervised_agents=[AGENTS[0]],
            )
        except ValueError as exc:
            assert "cannot supervise its own" in str(exc), exc
        else:
            raise AssertionError("self-supervision must fail closed")

        try:
            normalize_supervisor_decision(
                {
                    "decision_id": "bad-handoff",
                    "kind": "handoff",
                    "source_agent_id": AGENTS[1],
                    "target_agent_id": AGENTS[1],
                    "state_ref": "runtime-state:43",
                    "reason_codes": ["scope-overlap"],
                    "evidence_refs": ["effect:43"],
                },
                supervisor={**configured, "supervised_agents": AGENTS[1:]},
            )
        except ValueError as exc:
            assert "must differ" in str(exc), exc
        else:
            raise AssertionError("same-session handoff must fail closed")

        cleared = configure_goal(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            clear_supervisor=True,
            execute=True,
        )
        assert cleared["after"]["supervisor"] is None, cleared
        assert cleared["supervisor_prompt"]["status"] == "disabled", cleared

    print("peer-supervisor-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
