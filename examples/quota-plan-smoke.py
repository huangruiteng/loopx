#!/usr/bin/env python3
"""Smoke-test multi-project quota plan ordering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.quota import (  # noqa: E402
    build_quota_plan,
    build_quota_should_run,
    build_quota_slot_preview,
    goal_quota_with_spend_ledger,
    goal_quota_config,
    render_quota_markdown,
    render_quota_slot_preview_markdown,
    render_quota_should_run_markdown,
)


def goal(
    goal_id: str,
    *,
    compute: float,
    spent_slots: int = 0,
    allowed_slots: int | None = None,
) -> dict:
    allowed_slots = round(24 * 60 * compute) if allowed_slots is None else allowed_slots
    return {
        "id": goal_id,
        "status": "active",
        "registry_member": True,
        "lifecycle_phase": "refreshed",
        "adapter_kind": "read_only_project_map_v0",
        "adapter_status": "connected-read-only",
        "quota": {
            "compute": compute,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": allowed_slots,
            "spent_slots": spent_slots,
        },
        "latest_runs": [
            {
                "generated_at": "2026-01-01T00:00:00+00:00",
                "classification": "state_refreshed",
                "recommended_action": f"continue {goal_id}",
            }
        ],
    }


def attention(
    goal_id: str,
    *,
    compute: float,
    state: str = "eligible",
    waiting_on: str = "codex",
    spent_slots: int = 0,
    allowed_slots: int | None = None,
) -> dict:
    allowed_slots = round(24 * 60 * compute) if allowed_slots is None else allowed_slots
    if state == "operator_gate":
        reason = "operator gate blocks gated delivery; safe non-gated steering may continue"
    elif state == "throttled":
        reason = f"{compute:g} compute quota spent {spent_slots}/{allowed_slots} slots in this window"
    else:
        reason = f"{compute:g} compute quota; eligible for the next automatic agent turn"
    return {
        "goal_id": goal_id,
        "status": "state_refreshed" if waiting_on == "codex" else "operator_gate_deferred",
        "waiting_on": waiting_on,
        "severity": "action",
        "recommended_action": f"continue {goal_id}",
        "source": "fixture",
        **(
            {
                "operator_question": f"是否同意 {goal_id} 继续 gated delivery？",
                "next_handoff_condition": "operator decision recorded",
                "user_todos": {
                    "source_section": "User Todo",
                    "total_count": 1,
                    "open_count": 1,
                    "done_count": 0,
                    "items": [
                        {
                            "index": 1,
                            "done": False,
                            "text": "Confirm the operator gate.",
                        }
                    ],
                },
                "agent_todos": {
                    "source_section": "Agent Todo",
                    "total_count": 1,
                    "open_count": 1,
                    "done_count": 0,
                    "items": [
                        {
                            "index": 1,
                            "done": False,
                            "text": "Run the safe follow-up after gate approval.",
                        }
                    ],
                },
            }
            if state == "operator_gate"
            else {}
        ),
        "quota": {
            "compute": compute,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": allowed_slots,
            "spent_slots": spent_slots,
            "state": state,
            "reason": reason,
            **(
                {
                    "blocked_action_scope": "gated_delivery",
                    "safe_bypass_allowed": True,
                    "safe_bypass_policy": "Do not execute agent_command; safe steering only.",
                }
                if state == "operator_gate"
                else {}
            ),
        },
    }


def build_status_fixture() -> dict:
    goals = [
        goal("half-speed", compute=0.5),
        goal("near-limit-half", compute=0.5, spent_slots=11, allowed_slots=12),
        goal("full-speed", compute=1.0),
        goal("low-speed", compute=0.3),
        goal("throttled-half", compute=0.5, spent_slots=12, allowed_slots=12),
        goal("needs-operator", compute=1.0),
    ]
    queue_items = [
        attention("half-speed", compute=0.5),
        attention("near-limit-half", compute=0.5, spent_slots=11, allowed_slots=12),
        attention("full-speed", compute=1.0),
        attention("low-speed", compute=0.3),
        attention(
            "throttled-half",
            compute=0.5,
            state="throttled",
            spent_slots=12,
            allowed_slots=12,
        ),
        attention(
            "needs-operator",
            compute=1.0,
            state="operator_gate",
            waiting_on="user_or_controller",
        ),
    ]
    return {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": len(goals),
        "run_count": len(goals),
        "attention_queue": {"items": queue_items},
        "run_history": {"goals": goals},
    }


def append_quota_slot_spend_fixture(
    run_dir: Path,
    *,
    goal_id: str,
    compute: float,
    slot_index: int,
    generated_at: str,
    allowed_slots: int,
) -> None:
    before_spent = slot_index
    after_spent = slot_index + 1
    after_state = "throttled" if after_spent >= allowed_slots else "eligible"
    after_should_run = after_state == "eligible"
    stem = generated_at.replace("-", "").replace(":", "").replace("+", "")
    json_path = run_dir / f"{stem}-quota-slot-{slot_index + 1}.json"
    markdown_path = run_dir / f"{stem}-quota-slot-{slot_index + 1}.md"
    record = {
        "generated_at": generated_at,
        "goal_id": goal_id,
        "classification": "quota_slot_spent",
        "recommended_action": f"continue {goal_id}",
        "health_check": "fixture quota slot spend event",
        "quota_event": {
            "event_type": "quota_slot_spent",
            "source": "heartbeat",
            "slots": 1,
            "reason_summary": "fixture automatic agent slot completed under an eligible quota guard",
            "before": {
                "should_run": True,
                "state": "eligible",
                "compute": compute,
                "window_hours": 24,
                "slot_minutes": 1,
                "spent_slots": before_spent,
                "allowed_slots": allowed_slots,
            },
            "after": {
                "should_run": after_should_run,
                "state": after_state,
                "compute": compute,
                "window_hours": 24,
                "slot_minutes": 1,
                "spent_slots": after_spent,
                "allowed_slots": allowed_slots,
            },
        },
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(f"# {goal_id} quota slot fixture\n", encoding="utf-8")
    with (run_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "generated_at": generated_at,
                    "goal_id": goal_id,
                    "classification": "quota_slot_spent",
                    "recommended_action": f"continue {goal_id}",
                    "health_check": "fixture quota slot spend event",
                    "json_path": str(json_path),
                    "markdown_path": str(markdown_path),
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def write_cli_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    registry_path = project / ".goal-harness" / "registry.json"
    base_time = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=30)
    goal_specs = [
        ("half-speed", 0.5, "state_refreshed", 0, None),
        ("near-limit-half", 0.5, "state_refreshed", 11, 12),
        ("full-speed", 1.0, "state_refreshed", 0, None),
        ("low-speed", 0.3, "state_refreshed", 0, None),
        ("throttled-half", 0.5, "state_refreshed", 12, 12),
        ("needs-operator", 1.0, "operator_gate_deferred", 0, None),
    ]
    registry_goals = []
    for goal_id, compute, classification, spent_slots, allowed_slots in goal_specs:
        state_file = f".codex/goals/{goal_id}/ACTIVE_GOAL_STATE.md"
        state_path = project / state_file
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            "---\n"
            "status: active\n"
            "updated_at: 2026-01-01T00:00:00+00:00\n"
            "---\n\n"
            f"# {goal_id}\n\n"
            "## Next Action\n\n"
            f"- continue {goal_id}\n",
            encoding="utf-8",
        )
        registry_goals.append(
            {
                "id": goal_id,
                "domain": "quota-fixture",
                "status": "active",
                "repo": str(project),
                "state_file": state_file,
                "adapter": {
                    "kind": "read_only_project_map_v0",
                    "status": "connected-read-only",
                },
                "authority_sources": [],
                "quota": {
                    key: value
                    for key, value in {
                        "compute": compute,
                        "window_hours": 24,
                        "allowed_slots": allowed_slots,
                    }.items()
                    if value is not None
                },
            }
        )
        runs_dir = runtime / "goals" / goal_id / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        json_path = runs_dir / "20260101T000000-run.json"
        markdown_path = runs_dir / "20260101T000000-run.md"
        generated_at = (base_time - timedelta(seconds=1)).isoformat()
        record = {
            "generated_at": generated_at,
            "goal_id": goal_id,
            "classification": classification,
            "recommended_action": f"continue {goal_id}",
            "health_check": "fixture 1/1",
        }
        if classification == "operator_gate_deferred":
            record["operator_gate"] = {
                "recorded_at": generated_at,
                "gate": "read_only_map_opt_in",
                "decision": "defer",
                "operator_question": f"是否同意 `{goal_id}` 先执行 read-only map opt-in？",
                "reason_summary": "need more fixture evidence",
            }
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(f"# {goal_id} fixture run\n", encoding="utf-8")
        with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        **record,
                        "json_path": str(json_path),
                        "markdown_path": str(markdown_path),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        effective_allowed_slots = round(24 * 60 * compute) if allowed_slots is None else allowed_slots
        for slot_index in range(spent_slots):
            append_quota_slot_spend_fixture(
                runs_dir,
                goal_id=goal_id,
                compute=compute,
                slot_index=slot_index,
                generated_at=(base_time + timedelta(seconds=slot_index)).isoformat(),
                allowed_slots=effective_allowed_slots,
            )

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": registry_goals,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, runtime, project


def run_cli_quota_plan(root: Path) -> tuple[dict, str]:
    registry_path, runtime, project = write_cli_fixture(root)
    base_args = [
        sys.executable,
        "-m",
        "goal_harness.cli",
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
    ]
    json_result = subprocess.run(
        [*base_args, "--format", "json", "quota", "plan", "--scan-path", str(project)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    markdown_result = subprocess.run(
        [*base_args, "quota", "plan", "--scan-path", str(project)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(json_result.stdout), markdown_result.stdout


def run_cli_throttled_should_run(root: Path) -> dict:
    registry_path, runtime, project = write_cli_fixture(root)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "quota",
            "should-run",
            "--goal-id",
            "throttled-half",
            "--scan-path",
            str(project),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def run_cli_slot_preview(root: Path) -> tuple[dict, dict]:
    registry_path, runtime, project = write_cli_fixture(root)
    base_args = [
        sys.executable,
        "-m",
        "goal_harness.cli",
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        "quota",
    ]
    preview_result = subprocess.run(
        [
            *base_args,
            "spend-slot",
            "--goal-id",
            "near-limit-half",
            "--slots",
            "1",
            "--scan-path",
            str(project),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    should_run_result = subprocess.run(
        [
            *base_args,
            "should-run",
            "--goal-id",
            "near-limit-half",
            "--scan-path",
            str(project),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(preview_result.stdout), json.loads(should_run_result.stdout)


def run_cli_slot_spend_execute(root: Path) -> tuple[dict, dict, str, str]:
    registry_path, runtime, project = write_cli_fixture(root)
    registry_before = registry_path.read_text(encoding="utf-8")
    base_args = [
        sys.executable,
        "-m",
        "goal_harness.cli",
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        "quota",
    ]
    result = subprocess.run(
        [
            *base_args,
            "spend-slot",
            "--goal-id",
            "near-limit-half",
            "--slots",
            "1",
            "--source",
            "heartbeat",
            "--execute",
            "--scan-path",
            str(project),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    should_run_result = subprocess.run(
        [
            *base_args,
            "should-run",
            "--goal-id",
            "near-limit-half",
            "--scan-path",
            str(project),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return (
        json.loads(result.stdout),
        json.loads(should_run_result.stdout),
        registry_before,
        registry_path.read_text(encoding="utf-8"),
    )


def assert_plan_shape(plan: dict, markdown: str | None = None) -> None:
    eligible_ids = [item["goal_id"] for item in plan["groups"]["eligible"]]
    operator_gate_ids = [item["goal_id"] for item in plan["groups"]["operator_gate"]]
    throttled_ids = [item["goal_id"] for item in plan["groups"]["throttled"]]

    assert plan["summary"]["next_automatic_turn"] == "full-speed", plan
    assert plan["next_automatic_turn"]["goal_id"] == "full-speed", plan
    assert eligible_ids == ["full-speed", "half-speed", "near-limit-half", "low-speed"], eligible_ids
    assert operator_gate_ids == ["needs-operator"], operator_gate_ids
    assert throttled_ids == ["throttled-half"], throttled_ids
    assert "needs-operator" not in eligible_ids, eligible_ids
    gated = plan["groups"]["operator_gate"][0]
    assert gated["quota"]["safe_bypass_allowed"] is True, gated
    assert gated["quota"]["blocked_action_scope"] == "gated_delivery", gated
    assert "operator_question" in gated, gated
    if "user_todos" in gated:
        assert gated["user_todos"]["open_count"] == 1, gated
    assert "throttled-half" not in eligible_ids, eligible_ids
    if markdown is not None:
        assert "next_automatic_turn=full-speed" in markdown, markdown
        assert "### operator_gate" in markdown, markdown
        assert "### throttled" in markdown, markdown
        assert "`throttled-half`" in markdown, markdown
        assert markdown.index("`full-speed`") < markdown.index("`half-speed`") < markdown.index("`near-limit-half`") < markdown.index("`low-speed`"), markdown


def assert_default_quota_is_duty_cycle() -> None:
    full = goal_quota_config({"quota": {"compute": 1.0, "window_hours": 24}})
    half = goal_quota_config({"quota": {"compute": 0.5, "window_hours": 24}})
    low = goal_quota_config({"quota": {"compute": 0.3, "window_hours": 24}})

    assert full["slot_minutes"] == 1, full
    assert full["allowed_slots"] == 1440, full
    assert half["allowed_slots"] == 720, half
    assert low["allowed_slots"] == 432, low


def assert_rolling_window_ledger_expires_old_spends() -> None:
    now = datetime.fromisoformat("2026-06-03T11:20:00+08:00")
    goal_payload = {
        "id": "rolling-window",
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
        },
    }
    runs = [
        {
            "goal_id": "rolling-window",
            "classification": "quota_slot_spent",
            "generated_at": "2026-06-02T11:19:22+08:00",
            "quota_event": {
                "event_type": "quota_slot_spent",
                "slots": 1,
            },
        },
        {
            "goal_id": "rolling-window",
            "classification": "quota_slot_spent",
            "generated_at": "2026-06-03T11:19:13+08:00",
            "quota_event": {
                "event_type": "quota_slot_spent",
                "slots": 1,
            },
        },
    ]

    quota = goal_quota_with_spend_ledger(goal_payload, runs, now=now)

    assert quota["spent_slots"] == 1, quota
    assert quota["spend_event_count"] == 1, quota
    assert quota["spend_source"] == "runtime_events", quota


def assert_throttled_should_run(status_payload: dict) -> None:
    payload = build_quota_should_run(status_payload, goal_id="throttled-half")
    quota = payload["quota"]

    assert payload["ok"] is True, payload
    assert payload["decision"] == "skip", payload
    assert payload["should_run"] is False, payload
    assert payload["state"] == "throttled", payload
    assert payload["plan_summary"]["next_automatic_turn"] == "full-speed", payload
    assert quota["spent_slots"] == 12, payload
    assert quota["allowed_slots"] == 12, payload
    assert "spent 12/12" in payload["reason"], payload


def assert_operator_gate_should_run(status_payload: dict) -> None:
    payload = build_quota_should_run(status_payload, goal_id="needs-operator")

    assert payload["ok"] is True, payload
    assert payload["decision"] == "skip", payload
    assert payload["should_run"] is False, payload
    assert payload["state"] == "operator_gate", payload
    assert payload["safe_bypass_allowed"] is True, payload
    assert payload["notify_user_on_gate"] is True, payload
    assert payload["operator_question"] == "是否同意 needs-operator 继续 gated delivery？", payload
    assert payload["user_todo_summary"]["open_count"] == 1, payload
    assert payload["agent_todo_summary"]["open_count"] == 1, payload
    assert payload["todo_write_hint"]["section"] == "User Todo / Owner Review Reading Queue", payload
    assert "goal-harness todo add --goal-id needs-operator --role user" in payload["todo_write_hint"][
        "user_todo_command_template"
    ], payload
    assert "goal-harness todo add --goal-id needs-operator --role agent" in payload["todo_write_hint"][
        "agent_todo_command_template"
    ], payload
    assert "Next Action" in payload["todo_write_hint"]["rule"], payload
    assert "请用户/控制器确认当前 gate" in payload["gate_prompt"], payload
    assert "Confirm the operator gate." in payload["gate_prompt"], payload
    markdown = render_quota_should_run_markdown(payload)
    assert "agent_todo_summary: open=1 total=1" in markdown, markdown
    assert "user_todo_next[1]: Confirm the operator gate." in markdown, markdown
    assert "agent_todo_next[1]: Run the safe follow-up after gate approval." in markdown, markdown
    assert "agent_todo_command_template" in markdown, markdown


def assert_attention_queue_overrides_stale_run_history() -> None:
    stale_goal = goal("queue-authority", compute=1.0)
    stale_goal["status"] = "operator_gate_deferred"
    stale_goal["lifecycle_phase"] = "controller_gated"
    stale_goal["quota"] = {
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "allowed_slots": 1440,
        "spent_slots": 0,
        "state": "operator_gate",
        "reason": "stale run-history gate should not block current queue authority",
        "blocked_action_scope": "gated_delivery",
        "safe_bypass_allowed": True,
    }
    stale_goal["latest_runs"][0]["classification"] = "operator_gate_deferred"
    stale_goal["latest_runs"][0]["recommended_action"] = "ask the old gate again"

    current_item = attention("queue-authority", compute=1.0)
    current_item.update(
        {
            "status": "operator_gate_approved",
            "waiting_on": "codex",
            "recommended_action": "run the approved dry-run",
            "agent_command": "goal-harness read-only-map --goal-id queue-authority --dry-run",
            "source": "latest_run",
        }
    )
    current_item["project_asset"] = {
        "owner": "codex",
        "gate": "none",
        "next_action": "run the approved dry-run",
        "stop_condition": "stop if the command needs write control",
    }

    payload = {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 1,
        "attention_queue": {"items": [current_item]},
        "run_history": {"goals": [stale_goal]},
    }
    decision = build_quota_should_run(payload, goal_id="queue-authority")

    assert decision["ok"] is True, decision
    assert decision["decision"] == "run", decision
    assert decision["should_run"] is True, decision
    assert decision["state"] == "eligible", decision
    assert decision["waiting_on"] == "codex", decision
    assert decision["status"] == "operator_gate_approved", decision
    assert decision["recommended_action"] == "run the approved dry-run", decision
    assert decision["agent_command"] == "goal-harness read-only-map --goal-id queue-authority --dry-run", decision
    assert "operator_question" not in decision, decision
    assert "gate_prompt" not in decision, decision


def assert_safe_bypass_slot_preview(status_payload: dict) -> None:
    payload = build_quota_slot_preview(status_payload, goal_id="needs-operator", slots=1)

    assert payload["ok"] is True, payload
    assert payload["safe_bypass_spend"] is True, payload
    assert payload["before"]["state"] == "operator_gate", payload
    assert payload["before"]["safe_bypass_allowed"] is True, payload
    assert payload["after"]["state"] == "operator_gate", payload
    assert payload["after"]["quota"]["spent_slots"] == payload["before"]["quota"]["spent_slots"] + 1, payload


def assert_throttled_cli_should_run(payload: dict) -> None:
    quota = payload["quota"]

    assert payload["ok"] is True, payload
    assert payload["goal_id"] == "throttled-half", payload
    assert payload["decision"] == "skip", payload
    assert payload["should_run"] is False, payload
    assert payload["state"] == "throttled", payload
    assert payload["waiting_on"] == "codex", payload
    assert payload["plan_summary"]["next_automatic_turn"] == "full-speed", payload
    assert quota["compute"] == 0.5, payload
    assert quota["spent_slots"] == 12, payload
    assert quota["allowed_slots"] == 12, payload
    assert "spent 12/12" in payload["reason"], payload
    assert "agent_command" not in payload, payload


def assert_slot_preview(payload: dict) -> None:
    before = payload["before"]
    after = payload["after"]
    markdown = render_quota_slot_preview_markdown(payload)

    assert payload["ok"] is True, payload
    assert payload["dry_run"] is True, payload
    assert payload["appended"] is False, payload
    assert payload["registry_mutated"] is False, payload
    assert payload["goal_id"] == "near-limit-half", payload
    assert payload["slots"] == 1, payload
    assert payload["would_throttle"] is True, payload
    assert before["state"] == "eligible", payload
    assert before["should_run"] is True, payload
    assert before["quota"]["spent_slots"] == 11, payload
    assert before["quota"]["allowed_slots"] == 12, payload
    assert after["state"] == "throttled", payload
    assert after["should_run"] is False, payload
    assert after["decision"] == "skip", payload
    assert after["quota"]["spent_slots"] == 12, payload
    assert after["quota"]["allowed_slots"] == 12, payload
    assert after["plan_summary"]["next_automatic_turn"] == "full-speed", payload
    assert "rolling_window_note" in payload, payload
    assert "same-status-payload projection" in payload["rolling_window_note"], payload
    assert "rolling_window_note" in markdown, markdown


def assert_dry_run_left_cli_fixture_unchanged(payload: dict) -> None:
    assert payload["goal_id"] == "near-limit-half", payload
    assert payload["state"] == "eligible", payload
    assert payload["should_run"] is True, payload
    assert payload["quota"]["spent_slots"] == 11, payload
    assert payload["quota"]["allowed_slots"] == 12, payload


def assert_slot_spend_execute(payload: dict, next_should_run: dict, registry_before: str, registry_after: str) -> None:
    quota_event = payload["quota_event"]
    before = quota_event["before"]
    after = quota_event["after"]
    json_path = Path(payload["json_path"])
    index_path = Path(payload["index_path"])

    assert payload["ok"] is True, payload
    assert payload["dry_run"] is False, payload
    assert payload["appended"] is True, payload
    assert payload["registry_mutated"] is False, payload
    assert payload["classification"] == "quota_slot_spent", payload
    assert payload["source"] == "heartbeat", payload
    assert registry_after == registry_before
    assert '"spent_slots"' not in registry_after
    assert json_path.exists(), payload
    assert index_path.exists(), payload
    assert quota_event["event_type"] == "quota_slot_spent", payload
    assert quota_event["slots"] == 1, payload
    assert before["should_run"] is True, payload
    assert before["state"] == "eligible", payload
    assert before["spent_slots"] == 11, payload
    assert after["spent_slots"] == 12, payload
    assert after["allowed_slots"] == 12, payload
    assert after["state"] == "throttled", payload
    assert after["should_run"] is False, payload

    record = json.loads(json_path.read_text(encoding="utf-8"))
    assert record["classification"] == "quota_slot_spent", record
    assert record["quota_event"] == quota_event, record
    forbidden = {"human_reward", "operator_gate", "write_control", "private_evidence", "agent_command"}
    assert forbidden.isdisjoint(record), record
    assert forbidden.isdisjoint(record["quota_event"]), record
    index_lines = index_path.read_text(encoding="utf-8").splitlines()
    assert any('"classification": "quota_slot_spent"' in line for line in index_lines), index_lines

    assert next_should_run["goal_id"] == "near-limit-half", next_should_run
    assert next_should_run["should_run"] is False, next_should_run
    assert next_should_run["state"] == "throttled", next_should_run
    assert next_should_run["quota"]["spent_slots"] == 12, next_should_run
    assert next_should_run["quota"]["allowed_slots"] == 12, next_should_run


def main() -> int:
    assert_default_quota_is_duty_cycle()
    assert_rolling_window_ledger_expires_old_spends()
    status_payload = build_status_fixture()
    plan = build_quota_plan(status_payload, mode="plan")
    markdown = render_quota_markdown(plan)
    assert_plan_shape(plan, markdown)
    assert_throttled_should_run(status_payload)
    assert_operator_gate_should_run(status_payload)
    assert_attention_queue_overrides_stale_run_history()
    assert_safe_bypass_slot_preview(status_payload)
    assert_slot_preview(build_quota_slot_preview(status_payload, goal_id="near-limit-half", slots=1))
    with tempfile.TemporaryDirectory(prefix="goal-harness-quota-plan-smoke-") as tmp:
        cli_plan, cli_markdown = run_cli_quota_plan(Path(tmp))
    assert_plan_shape(cli_plan, cli_markdown)
    with tempfile.TemporaryDirectory(prefix="goal-harness-quota-should-run-smoke-") as tmp:
        assert_throttled_cli_should_run(run_cli_throttled_should_run(Path(tmp)))
    with tempfile.TemporaryDirectory(prefix="goal-harness-quota-slot-smoke-") as tmp:
        slot_preview, should_run_after_preview = run_cli_slot_preview(Path(tmp))
    assert_slot_preview(slot_preview)
    assert_dry_run_left_cli_fixture_unchanged(should_run_after_preview)
    with tempfile.TemporaryDirectory(prefix="goal-harness-quota-slot-execute-smoke-") as tmp:
        assert_slot_spend_execute(*run_cli_slot_spend_execute(Path(tmp)))
    print("quota-plan-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
