#!/usr/bin/env python3
"""Exercise the atomic legacy-hierarchy to peer-agent registry migration."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.configure_goal import configure_goal  # noqa: E402
from loopx.heartbeat_prompt import build_heartbeat_prompt  # noqa: E402


GOAL_ID = "peer-agent-migration-fixture"
AGENTS = ["codex-alpha", "codex-beta"]


def write_legacy_registry(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "goals": [
                    {
                        "id": GOAL_ID,
                        "coordination": {
                            "registered_agents": AGENTS,
                            "primary_agent": AGENTS[0],
                            "side_agent_handoff_agent": AGENTS[0],
                            "write_scope": ["loopx/**"],
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-peer-agent-migration-") as tmp:
        registry_path = Path(tmp) / "registry.json"
        write_legacy_registry(registry_path)
        original = registry_path.read_text(encoding="utf-8")

        preview = configure_goal(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            agent_model="peer_v1",
        )
        assert preview["dry_run"] is True, preview
        assert preview["after"]["agent_model"] == "peer_v1", preview
        assert "primary_agent" not in preview["after"], preview
        assert preview["backup_path"] is None, preview
        assert registry_path.read_text(encoding="utf-8") == original
        migration = preview["heartbeat_prompt_migration"]
        assert migration["agent_model"] == "peer_v1", migration
        assert all("role" not in command for command in migration["commands"]), migration
        assert all(
            "peer task claims" in command["command"]
            for command in migration["commands"]
        ), migration

        applied = configure_goal(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            agent_model="peer_v1",
            execute=True,
        )
        assert applied["written"] is True, applied
        backup_path = Path(applied["backup_path"])
        assert backup_path.exists(), applied
        assert backup_path.read_text(encoding="utf-8") == original
        goal = json.loads(registry_path.read_text(encoding="utf-8"))["goals"][0]
        coordination = goal["coordination"]
        assert coordination["agent_model"] == "peer_v1", coordination
        assert coordination["registered_agents"] == AGENTS, coordination
        assert coordination["write_scope"] == ["loopx/**"], coordination
        assert "primary_agent" not in coordination, coordination
        assert "side_agent_handoff_agent" not in coordination, coordination

        repeated = configure_goal(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            agent_model="peer_v1",
            execute=True,
        )
        assert repeated["changed"] is False, repeated
        assert repeated["backup_path"] is None, repeated

        fresh_registry = Path(tmp) / "fresh-registry.json"
        fresh_registry.write_text(
            json.dumps({"goals": [{"id": GOAL_ID}]}) + "\n",
            encoding="utf-8",
        )
        fresh = configure_goal(
            registry_path=fresh_registry,
            goal_id=GOAL_ID,
            registered_agents=AGENTS,
            execute=True,
        )
        assert fresh["after"]["agent_model"] == "peer_v1", fresh
        fresh_goal = json.loads(fresh_registry.read_text(encoding="utf-8"))["goals"][0]
        assert fresh_goal["coordination"] == {
            "registered_agents": AGENTS,
            "agent_model": "peer_v1",
        }, fresh_goal

        heartbeat = build_heartbeat_prompt(
            goal_id=GOAL_ID,
            thin=True,
            agent_id=AGENTS[0],
            agent_scopes=["peer task claims and leases"],
            registered_agents=AGENTS,
            agent_model="peer_v1",
        )
        assert heartbeat["agent_model"] == "peer_v1", heartbeat
        assert heartbeat["agent_role"] == "peer-agent", heartbeat
        assert "primary_agent" not in heartbeat, heartbeat
        assert "side_agent_handoff_agent" not in heartbeat, heartbeat
        assert "single primary" not in heartbeat["task_body"].lower(), heartbeat
        assert "side-agent" not in heartbeat["task_body"].lower(), heartbeat
        assert "equal peer agent" in heartbeat["task_body"].lower(), heartbeat

    print("peer-agent-migration-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
