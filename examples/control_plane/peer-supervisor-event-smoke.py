#!/usr/bin/env python3
"""Exercise durable supervisor proposals and capability-matched host receipts."""

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
from loopx.control_plane.agents.supervisor_events import (  # noqa: E402
    load_supervisor_event_projection,
    record_supervisor_proposal,
    record_supervisor_receipt,
    supervisor_event_log_path,
)


GOAL_ID = "peer-supervisor-event-fixture"
AGENTS = ["codex-alpha", "codex-beta"]


def write_registry(root: Path) -> Path:
    state_file = root / "ACTIVE_GOAL_STATE.md"
    state_file.write_text(
        "---\nstatus: active\n---\n\n# Active Goal State\n\n"
        "## Objective\n\nExercise supervisor event durability.\n",
        encoding="utf-8",
    )
    registry_path = root / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "peer-supervisor-event-smoke",
                        "repo": str(root),
                        "state_file": state_file.name,
                        "adapter": {
                            "kind": "generic_project_goal_v0",
                            "status": "connected",
                        },
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
    configure_goal(
        registry_path=registry_path,
        goal_id=GOAL_ID,
        supervisor_agent=AGENTS[0],
        supervised_agents=[AGENTS[1]],
        execute=True,
    )
    return registry_path


def inject_decision(decision_id: str = "inject-1") -> dict:
    return {
        "decision_id": decision_id,
        "kind": "inject",
        "target_agent_id": AGENTS[1],
        "message": "Compare the latest focused validation evidence.",
        "reason_codes": ["evidence-gap"],
        "evidence_refs": [f"effect:{decision_id}"],
    }


def executed_receipt(receipt_id: str = "receipt-inject-1") -> dict:
    return {
        "receipt_id": receipt_id,
        "decision_id": "inject-1",
        "adapter_id": "fixture-host",
        "outcome": "executed",
        "authority_ref": "owner-gate:inject-1",
        "evidence_refs": ["host-effect:inject-1"],
        "reason_codes": ["adapter-success"],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-peer-supervisor-events-") as tmp:
        root = Path(tmp)
        registry_path = write_registry(root)
        supervisor = json.loads(registry_path.read_text(encoding="utf-8"))["goals"][0][
            "coordination"
        ]["supervisor"]
        event_log = supervisor_event_log_path(root / "runtime", GOAL_ID)

        preview = record_supervisor_proposal(
            log_path=event_log,
            goal_id=GOAL_ID,
            supervisor=supervisor,
            decision=inject_decision(),
            execute=False,
        )
        assert preview["dry_run"] is True and preview["would_append"] is True, preview
        assert not event_log.exists(), preview
        assert preview["projection"]["items"][0]["execution_status"] == "proposal_only"

        proposal = record_supervisor_proposal(
            log_path=event_log,
            goal_id=GOAL_ID,
            supervisor=supervisor,
            decision=inject_decision(),
            execute=True,
        )
        assert proposal["appended"] is True, proposal
        repeated = record_supervisor_proposal(
            log_path=event_log,
            goal_id=GOAL_ID,
            supervisor=supervisor,
            decision=inject_decision(),
            execute=True,
        )
        assert repeated["appended"] is False, repeated

        try:
            record_supervisor_proposal(
                log_path=event_log,
                goal_id=GOAL_ID,
                supervisor=supervisor,
                decision={
                    **inject_decision("inject-secret"),
                    "message": "ak=must-not-be-recorded",
                },
                execute=True,
            )
        except ValueError as exc:
            assert "inline credential" in str(exc), exc
        else:
            raise AssertionError("proposal ledger must reject inline credentials")

        try:
            record_supervisor_receipt(
                log_path=event_log,
                goal_id=GOAL_ID,
                receipt=executed_receipt("receipt-missing-capability"),
                execute=True,
            )
        except ValueError as exc:
            assert "missing required host capabilities" in str(exc), exc
        else:
            raise AssertionError("executed receipt must prove required capabilities")

        receipt = record_supervisor_receipt(
            log_path=event_log,
            goal_id=GOAL_ID,
            receipt=executed_receipt(),
            host_capabilities=["session_message_injection"],
            execute=True,
        )
        assert receipt["appended"] is True, receipt
        repeated_receipt = record_supervisor_receipt(
            log_path=event_log,
            goal_id=GOAL_ID,
            receipt=executed_receipt(),
            host_capabilities=["session_message_injection"],
            execute=True,
        )
        assert repeated_receipt["appended"] is False, repeated_receipt
        projection = load_supervisor_event_projection(event_log, goal_id=GOAL_ID)
        assert projection["proposal_count"] == 1, projection
        assert projection["receipt_count"] == 1, projection
        assert projection["items"][0]["execution_status"] == "executed", projection
        assert projection["boundary"]["proposal_is_execution_evidence"] is False

        decision_path = root / "decision.json"
        decision_path.write_text(json.dumps(inject_decision("inject-cli")), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "--registry",
                    str(registry_path),
                    "--runtime-root",
                    str(root / "runtime"),
                    "supervisor-event",
                    "propose",
                    "--format",
                    "json",
                    "--goal-id",
                    GOAL_ID,
                    "--agent-id",
                    AGENTS[0],
                    "--decision-json",
                    str(decision_path),
                    "--execute",
                ]
            )
        assert exit_code == 0, stdout.getvalue()
        cli_payload = json.loads(stdout.getvalue())
        assert cli_payload["appended"] is True, cli_payload
        assert cli_payload["projection"]["proposal_count"] == 2, cli_payload

        cli_receipt_path = root / "receipt.json"
        cli_receipt_path.write_text(
            json.dumps(
                {
                    **executed_receipt("receipt-cli"),
                    "decision_id": "inject-cli",
                    "evidence_refs": ["host-effect:inject-cli"],
                }
            ),
            encoding="utf-8",
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "--registry",
                    str(registry_path),
                    "--runtime-root",
                    str(root / "runtime"),
                    "supervisor-event",
                    "receipt",
                    "--format",
                    "json",
                    "--goal-id",
                    GOAL_ID,
                    "--agent-id",
                    AGENTS[0],
                    "--receipt-json",
                    str(cli_receipt_path),
                    "--execute",
                ]
            )
        assert exit_code == 1, stdout.getvalue()
        cli_receipt = json.loads(stdout.getvalue())
        assert "missing required host capabilities" in cli_receipt["error"], cli_receipt

    print("peer-supervisor-event-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
