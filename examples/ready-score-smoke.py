#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.ready_score import build_ready_score_report, render_ready_score_markdown


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )


def fixture_payload() -> dict[str, object]:
    doctor = {
        "ok": True,
        "skills": {
            "loopx-project": {"exists": True, "required_phrases": True},
            "loopx-self-repair": {"exists": True, "required_phrases": True},
        },
        "install_freshness": {
            "status": "fresh",
            "reason": "default release snapshot timestamp is within the freshness window",
        },
    }
    status = {
        "ok": True,
        "goal_filter": "demo-goal",
        "goal_count": 1,
        "run_count": 12,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 8}},
        "contract_summary": {"errors": 0, "warnings": 0, "checks": 8},
        "attention_queue": {
            "items": [
                {
                    "goal_id": "demo-goal",
                    "active_state_next_action": "continue the next bounded validated segment",
                    "agent_todos": {
                        "open_count": 2,
                        "first_executable_items": [{"todo_id": "todo_demo", "claimed_by": "codex-demo"}],
                    },
                    "user_todos": {"open_count": 0},
                }
            ]
        },
        "usage_summary": {"totals": {"progress_signal_run_count_24h": 4}},
        "event_ledger_summary": {"totals": {"events_24h": 5}},
        "promotion_readiness_summary": {"is_fresh": True},
        "global_registry": {"ok": True, "summary": {"high": 0, "action": 0}},
    }
    quota = {
        "should_run": True,
        "effective_action": "normal_run",
        "normal_delivery_allowed": True,
        "recommended_action": "continue demo todo",
        "quota": {"state": "eligible"},
        "scheduler_hint": {"codex_app": {"stateful_backoff": {"apply_needed": False}}},
    }
    return build_ready_score_report(
        doctor_payload=doctor,
        status_payload=status,
        quota_payload=quota,
        goal_id="demo-goal",
        agent_id="codex-demo",
    )


def assert_fixture_score() -> None:
    payload = fixture_payload()
    assert payload["schema_version"] == "loopx_ready_score_report_v0", payload
    assert payload["score"] == 100, payload
    assert payload["grade"] == "ready", payload
    assert payload["mutation_policy"].startswith("read_only"), payload
    assert payload["badge"]["writeback_policy"].startswith("preview_only"), payload
    markdown = render_ready_score_markdown(payload)
    assert "LoopX Ready score" in markdown, markdown
    assert "100/100" in markdown, markdown
    assert "does not edit README" in markdown, markdown


def assert_warn_score() -> None:
    payload = fixture_payload()
    checks = payload["checks"]
    assert all(check["status"] == "pass" for check in checks), checks
    doctor = {"ok": False, "skills": {}, "install_freshness": {"status": "missing"}}
    status = {
        "ok": True,
        "attention_queue": {"items": [{"goal_id": "demo-goal", "user_todos": {"open_count": 1}}]},
        "contract": {"ok": True, "summary": {"errors": 0}},
        "global_registry": {"ok": True, "summary": {"high": 0, "action": 3}},
    }
    report = build_ready_score_report(
        doctor_payload=doctor,
        status_payload=status,
        quota_payload={"should_run": False, "quota": {"state": "waiting"}},
        goal_id="demo-goal",
        agent_id="codex-demo",
    )
    assert report["score"] < 60, report
    assert report["grade"] in {"needs_setup", "not_ready"}, report
    assert report["recommendations"], report


def assert_cli_surfaces() -> None:
    help_result = run_cli("ready-score", "--help")
    assert help_result.returncode == 0, (help_result.returncode, help_result.stdout, help_result.stderr)
    assert "doctor/status/quota" in help_result.stdout, help_result.stdout

    commands = run_cli("commands", "--format", "json")
    assert commands.returncode == 0, (commands.returncode, commands.stdout, commands.stderr)
    payload = json.loads(commands.stdout)
    rendered = json.dumps(payload)
    assert "ready-score" in rendered, rendered
    assert "without writing badges" in rendered, rendered


def main() -> int:
    assert_fixture_score()
    assert_warn_score()
    assert_cli_surfaces()
    print("ready-score-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
