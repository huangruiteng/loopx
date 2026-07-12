#!/usr/bin/env python3
"""Exercise the default-off supervisor inject host adapter seam."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.configure_goal import configure_goal  # noqa: E402
from loopx.control_plane.agents.supervisor_events import (  # noqa: E402
    SupervisorReceiptOutcome,
    SupervisorRollbackMode,
    record_supervisor_proposal,
    supervisor_event_log_path,
)
from loopx.control_plane.agents.supervisor_inject import (  # noqa: E402
    SupervisorInjectRequest,
    SupervisorInjectResult,
    execute_supervisor_inject,
)


GOAL_ID = "peer-supervisor-inject-adapter-fixture"
AGENTS = ["codex-alpha", "codex-beta"]


class FixtureInjectAdapter:
    adapter_id = "fixture-inject-host"
    capabilities = ("session_message_injection",)
    rollback_mode = SupervisorRollbackMode.COMPENSATING_ACTION
    rollback_ref = "policy:fixture-compensating-message"

    def __init__(self) -> None:
        self.requests: list[SupervisorInjectRequest] = []

    def inject(self, request: SupervisorInjectRequest) -> SupervisorInjectResult:
        self.requests.append(request)
        return SupervisorInjectResult(
            outcome=SupervisorReceiptOutcome.EXECUTED,
            evidence_refs=(f"host-effect:{request.execution_id}",),
            reason_codes=("adapter-success",),
        )


class MissingCapabilityAdapter(FixtureInjectAdapter):
    capabilities = ()


class MissingRollbackAdapter(FixtureInjectAdapter):
    rollback_ref = ""


def write_registry(root: Path) -> tuple[Path, dict]:
    state_file = root / "ACTIVE_GOAL_STATE.md"
    state_file.write_text("---\nstatus: active\n---\n", encoding="utf-8")
    registry_path = root / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "peer-supervisor-inject-adapter-smoke",
                        "repo": str(root),
                        "state_file": state_file.name,
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": AGENTS,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    configure_goal(
        registry_path=registry_path,
        goal_id=GOAL_ID,
        supervisor_agent=AGENTS[0],
        supervised_agents=[AGENTS[1]],
        execute=True,
    )
    goal = json.loads(registry_path.read_text(encoding="utf-8"))["goals"][0]
    return registry_path, goal["coordination"]["supervisor"]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-supervisor-inject-") as tmp:
        root = Path(tmp)
        _, supervisor = write_registry(root)
        log_path = supervisor_event_log_path(root / "runtime", GOAL_ID)
        record_supervisor_proposal(
            log_path=log_path,
            goal_id=GOAL_ID,
            supervisor=supervisor,
            decision={
                "decision_id": "inject-canary",
                "kind": "inject",
                "target_agent_id": AGENTS[1],
                "message": "Inspect the compact effect reference before continuing.",
                "reason_codes": ["evidence-gap"],
                "evidence_refs": ["effect:inject-canary"],
            },
            execute=True,
        )

        adapter = FixtureInjectAdapter()
        preview = execute_supervisor_inject(
            log_path=log_path,
            goal_id=GOAL_ID,
            decision_id="inject-canary",
            execution_id="inject-execution-1",
            authority_ref="owner-gate:inject-canary",
            adapter=adapter,
            execute=False,
        )
        assert preview["dry_run"] is True and preview["would_execute"] is True, preview
        assert preview["host_called"] is False and not adapter.requests, preview

        missing = MissingCapabilityAdapter()
        try:
            execute_supervisor_inject(
                log_path=log_path,
                goal_id=GOAL_ID,
                decision_id="inject-canary",
                execution_id="inject-execution-missing-capability",
                authority_ref="owner-gate:inject-canary",
                adapter=missing,
                execute=True,
            )
        except ValueError as exc:
            assert "missing declared capability" in str(exc), exc
        else:
            raise AssertionError("missing adapter capability must fail before host execution")
        assert not missing.requests

        missing_rollback = MissingRollbackAdapter()
        try:
            execute_supervisor_inject(
                log_path=log_path,
                goal_id=GOAL_ID,
                decision_id="inject-canary",
                execution_id="inject-execution-missing-rollback",
                authority_ref="owner-gate:inject-canary",
                adapter=missing_rollback,
                execute=True,
            )
        except ValueError as exc:
            assert "adapter rollback_ref" in str(exc), exc
        else:
            raise AssertionError("missing rollback policy must fail before host execution")
        assert not missing_rollback.requests

        executed = execute_supervisor_inject(
            log_path=log_path,
            goal_id=GOAL_ID,
            decision_id="inject-canary",
            execution_id="inject-execution-1",
            authority_ref="owner-gate:inject-canary",
            adapter=adapter,
            execute=True,
        )
        assert executed["host_called"] is True and len(adapter.requests) == 1, executed
        receipt = executed["receipt"]
        assert receipt["outcome"] == "executed", receipt
        assert receipt["capabilities"] == ["session_message_injection"], receipt
        assert receipt["rollback_boundary"] == {
            "mode": "compensating_action",
            "ref": "policy:fixture-compensating-message",
            "automatic": False,
            "requires_explicit_authority": True,
        }, receipt

        repeated = execute_supervisor_inject(
            log_path=log_path,
            goal_id=GOAL_ID,
            decision_id="inject-canary",
            execution_id="inject-execution-2",
            authority_ref="owner-gate:inject-canary",
            adapter=adapter,
            execute=True,
        )
        assert repeated["already_executed"] is True, repeated
        assert repeated["host_called"] is False and len(adapter.requests) == 1, repeated

    print("peer-supervisor-inject-adapter-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
