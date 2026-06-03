#!/usr/bin/env python3
"""Smoke-test the reusable heartbeat automation prompt contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.heartbeat_prompt import build_heartbeat_prompt  # noqa: E402

DOC = REPO_ROOT / "docs" / "heartbeat-automation-prompt.md"
README = REPO_ROOT / "README.md"
INTEGRATION_DOC = REPO_ROOT / "docs" / "integration.md"
PROJECT_SKILL = REPO_ROOT / "skills" / "goal-harness-project" / "SKILL.md"
GOAL_ID = "public-heartbeat-goal"
ACTIVE_STATE = Path("/tmp/public-heartbeat-goal/ACTIVE_GOAL_STATE.md")


def normalized(text: str) -> str:
    return " ".join(text.split())


def assert_ordered(text: str, phrases: tuple[str, ...]) -> None:
    compact = normalized(text)
    positions = []
    for phrase in phrases:
        assert phrase in compact, phrase
        positions.append(compact.index(phrase))
    assert positions == sorted(positions), positions


def main() -> int:
    payload = build_heartbeat_prompt(goal_id=GOAL_ID, active_state=ACTIVE_STATE)
    compact_payload = build_heartbeat_prompt(goal_id=GOAL_ID, active_state=ACTIVE_STATE, compact=True)
    assert payload["quota_guard_command"] == (
        'goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" '
        "quota should-run --goal-id public-heartbeat-goal"
    ), payload
    assert payload["quota_spend_command"] == (
        'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" '
        "quota spend-slot --goal-id public-heartbeat-goal --slots 1 --source heartbeat --execute"
    ), payload
    assert compact_payload["compact"] is True, compact_payload
    assert compact_payload["quota_guard_command"] == payload["quota_guard_command"], compact_payload
    assert compact_payload["quota_spend_command"] == payload["quota_spend_command"], compact_payload
    assert len(str(compact_payload["task_body"])) < len(str(payload["task_body"])) * 0.45, (
        len(str(compact_payload["task_body"])),
        len(str(payload["task_body"])),
    )
    compact_task = normalized(str(compact_payload["task_body"]))
    for phrase in (
        "compact Goal Harness heartbeat body",
        "Expanded lifecycle contract",
        "goal-harness heartbeat-prompt --goal-id public-heartbeat-goal --active-state /tmp/public-heartbeat-goal/ACTIVE_GOAL_STATE.md",
        'goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" quota should-run --goal-id public-heartbeat-goal',
        "state=operator_gate",
        "notify_user_on_open_todo=true",
        "safe_bypass_allowed=true",
        "heartbeat_recommendation",
        "run_first_read_only_map",
        "mapped_noop_if_unchanged",
        "steering audit",
        "product-bottleneck lens",
        "no-progress self-stop check",
        "Public-safe commit, push, and PR creation may proceed",
        "goal-harness todo add --goal-id public-heartbeat-goal --role user|agent",
        'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id public-heartbeat-goal --slots 1 --source heartbeat --execute',
        "Do not append spend for quiet skips",
    ):
        assert phrase in compact_task, phrase

    doc = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    integration_doc = INTEGRATION_DOC.read_text(encoding="utf-8")
    project_skill = PROJECT_SKILL.read_text(encoding="utf-8")
    generated = str(payload["task_body"])
    compact_generated = normalized(generated)

    must_have = (
        "<ACTIVE_GOAL_STATE_PATH>",
        "<GOAL_ID>",
        "This heartbeat body is the generic Goal Harness lifecycle",
        "Do not add project-specific branching to the automation prompt",
        "Put project-specific policy in the Goal Harness registry, active-state sections, adapter output",
        "update goal-harness heartbeat-prompt so all projects inherit it",
        'export PATH="$HOME/.local/bin:$PATH"',
        'install_script="$HOME/goal-harness/scripts/install-local.sh"',
        "goal-harness doctor >/dev/null",
        'goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" quota should-run --goal-id <GOAL_ID>',
        "If that preflight still fails",
        "should_run=false",
        "state=operator_gate",
        "gate_prompt",
        "operator_question",
        "user_todo_summary",
        "user_todo_summary.open_count > 0",
        "never summarize this case as \"no new user action\"",
        "NOTIFY",
        "notify_user_on_open_todo=true",
        "blocker-push opportunity",
        "state=focus_wait",
        "waiting_on=external_evidence",
        "listing at most three first_open_items",
        "open_todo_notify_reason",
        "done, defer/not now, or a new evidence link/date/conclusion",
        "quota spend for that blocker-push turn",
        "safe_bypass_allowed=true",
        "gate blocks only the gated delivery path",
        "one bounded safe-bypass step",
        "that report must include the existing open user todos",
        "DONT_NOTIFY",
        "should_run=true",
        "When you inspect current Goal Harness routing",
        "attention_queue.items",
        "project_asset are authoritative",
        "run_history.latest_runs as evidence and drill-down only",
        "do not decide whether a gate is pending or approved from latest runs alone",
        "If an open user/owner todo is the current blocker that can unlock a gate, focus_wait, or external-evidence wait",
        "no quota spend for that blocker-push turn",
        "heartbeat_recommendation",
        "recommended_mode=run_first_read_only_map",
        "real read-only map, not another dry-run",
        "read_only_project_map result",
        "recommended_mode=mapped_noop_if_unchanged",
        "stop_if_unchanged=true",
        "no new user instruction, owner evidence, agent todo, stale source, or safe handoff",
        "do not run another dry-run, do not edit files, and do not append quota spend",
        "Run a short steering audit before choosing work",
        "list at least three plausible next-action candidates across different P0/P1/P2 lanes",
        "apply a continuation check",
        "keep compute quota separate from focus quota",
        "Include a product bottleneck lens",
        "user experience, agent capability, evidence quality, adapter readiness, or priority-rule gaps",
        "promote one concrete bottleneck candidate when it should outrank the nearest local TODO",
        "Run the no-progress self-stop check before choosing delivery work",
        "5 consecutive eligible heartbeats are no-progress loops",
        "do not append a quota spend for that self-cancel turn",
        "automation was cancelled because it was spinning without progress",
        "Choose exactly one bounded, verifiable step from that audit",
        "Public-safe repo publication is not an operator gate by itself",
        "commit, push, and PR creation may proceed autonomously after validation",
        "clean public/private boundary scan",
        "private or company-internal material, credentials, destructive git operations, production actions",
        "Run the smallest useful validation",
        "Write back changed files, validation, critic, and next action",
        "If the step discovers a concrete user/owner action",
        "do not hide it in `Next Action`, a review doc, or chat",
        "goal-harness todo add --goal-id <GOAL_ID> --role user --text \"<public-safe user/owner action>\"",
        "Use `--role agent` for project-agent follow-up work",
        "docs/project-agent-todo-contract.md",
        "goal-harness refresh-state --goal-id <GOAL_ID>",
        'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id <GOAL_ID> --slots 1 --source heartbeat --execute',
        "append exactly one",
        "Do not append spend for quiet should_run=false skips, preflight failures, pure dry-run previews, or duplicate accounting attempts",
        "safe_bypass_allowed=true and you actually completed a bounded safe-bypass step",
        "Return a compact final report",
    )
    compact_doc = normalized(doc)
    for phrase in must_have:
        assert phrase in compact_doc, phrase
    for phrase in (
        'export PATH="$HOME/.local/bin:$PATH"',
        'install_script="$HOME/goal-harness/scripts/install-local.sh"',
        "This heartbeat body is the generic Goal Harness lifecycle",
        "Do not add project-specific branching to the automation prompt",
        "Put project-specific policy in the Goal Harness registry, active-state sections, adapter output",
        "goal-harness doctor >/dev/null",
        'goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" quota should-run --goal-id public-heartbeat-goal',
        "If that preflight still fails",
        "should_run=false",
        "state=operator_gate",
        "gate_prompt",
        "operator_question",
        "user_todo_summary",
        "user_todo_summary.open_count > 0",
        "never summarize this case as \"no new user action\"",
        "NOTIFY",
        "notify_user_on_open_todo=true",
        "blocker-push opportunity",
        "state=focus_wait",
        "waiting_on=external_evidence",
        "listing at most three `first_open_items`",
        "open_todo_notify_reason",
        "new evidence link/date/conclusion",
        "quota spend for that blocker-push turn",
        "safe_bypass_allowed=true",
        "gate blocks only the gated delivery path",
        "one bounded safe-bypass step",
        "that report must include the existing open user todos",
        "DONT_NOTIFY",
        "When you inspect current Goal Harness routing",
        "attention_queue.items",
        "project_asset` are authoritative",
        "run_history.latest_runs` as evidence and drill-down only",
        "do not decide whether a gate is pending or approved from latest runs alone",
        "current blocker that can unlock a gate, `focus_wait`, or external-evidence wait",
        "no quota spend for that blocker-push turn",
        "heartbeat_recommendation",
        "recommended_mode=run_first_read_only_map",
        "real read-only map, not another dry-run",
        "read_only_project_map` result",
        "recommended_mode=mapped_noop_if_unchanged",
        "stop_if_unchanged=true",
        "no new user instruction, owner evidence, agent todo, stale source, or safe handoff",
        "do not run another dry-run, do not edit files, and do not append quota spend",
        "Run a short steering audit before choosing work",
        "list at least three plausible next-action candidates across different P0/P1/P2 lanes",
        "apply a continuation check",
        "keep compute quota separate from focus quota",
        "Include a product bottleneck lens",
        "user experience, agent capability, evidence quality, adapter readiness, or priority-rule gaps",
        "promote one concrete bottleneck candidate when it should outrank the nearest local TODO",
        "Run the no-progress self-stop check before choosing delivery work",
        "5 consecutive eligible heartbeats are no-progress loops",
        "do not append a quota spend for that self-cancel turn",
        "automation was cancelled because it was spinning without progress",
        "Choose exactly one bounded, verifiable step from that audit",
        "Public-safe repo publication is not an operator gate by itself",
        "commit, push, and PR creation may proceed autonomously after validation",
        "clean public/private boundary scan",
        "If the step discovers a concrete user/owner action",
        "goal-harness todo add --goal-id public-heartbeat-goal --role user --text \"<public-safe user/owner action>\"",
        "docs/project-agent-todo-contract.md",
        "goal-harness refresh-state --goal-id public-heartbeat-goal",
        'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id public-heartbeat-goal --slots 1 --source heartbeat --execute',
        "Do not append spend for quiet `should_run=false` skips",
    ):
        assert phrase in compact_generated, phrase

    assert_ordered(
        doc,
        (
            "Before spending delivery compute, first make the Goal Harness CLI reachable",
            'export PATH="$HOME/.local/bin:$PATH"',
            "goal-harness doctor >/dev/null",
            'goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" quota should-run --goal-id <GOAL_ID>',
            "If that preflight still fails",
            "If the result says should_run=false",
            "state=operator_gate",
            "gate_prompt",
            "notify_user_on_open_todo=true",
            "blocker-push opportunity",
            "safe_bypass_allowed=true",
            "If the result says should_run=true",
            "When you inspect current Goal Harness routing",
            "attention_queue.items",
            "run_history.latest_runs",
            "same blocker-push opportunity",
            "heartbeat_recommendation",
            "recommended_mode=run_first_read_only_map",
            "recommended_mode=mapped_noop_if_unchanged",
            "Run a short steering audit before choosing work",
            "Include a product bottleneck lens",
            "Run the no-progress self-stop check before choosing delivery work",
            "Choose exactly one bounded, verifiable step from that audit",
            "Public-safe repo publication is not an operator gate by itself",
            "Run the smallest useful validation",
            "goal-harness refresh-state --goal-id <GOAL_ID>",
            'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id <GOAL_ID> --slots 1 --source heartbeat --execute',
            "Return a compact final report",
        ),
    )

    assert "docs/heartbeat-automation-prompt.md" in readme, readme
    assert "goal-harness heartbeat-prompt" in readme, readme
    assert "goal-harness heartbeat-prompt --compact" in readme, readme
    assert "heartbeat_recommendation" in readme, readme
    assert "do not hand-edit one-off automation prompt branches" in normalized(readme), readme
    assert "goal-harness heartbeat-prompt" in doc, doc
    assert "--compact" in doc, doc
    assert "Do not hand-edit per-project lifecycle branches" in doc, doc
    assert "goal-harness heartbeat-prompt" in integration_doc, integration_doc
    assert "goal-harness heartbeat-prompt --compact" in integration_doc, integration_doc
    assert "visible goal text can stay short" in integration_doc, integration_doc
    assert "shares the same quota, gate," in integration_doc, integration_doc
    assert "steering-audit, writeback, refresh, and spend lifecycle" in integration_doc, integration_doc
    assert "heartbeat_recommendation" in integration_doc, integration_doc
    assert "Do not hand-edit one-off automation prompt branches" in normalized(integration_doc), integration_doc
    assert "public commit, push, and PR creation as autonomous" in normalized(integration_doc), integration_doc
    assert "Two Prompt Layers" in doc, doc
    assert "Visible goal text" in doc, doc
    assert "Heartbeat automation task body" in doc, doc
    assert "commit, push, and PR creation can proceed autonomously" in normalized(readme), readme
    assert "goal-harness heartbeat-prompt" in project_skill, project_skill
    assert "--compact" in project_skill, project_skill
    assert "Set Up Recurring Heartbeats" in project_skill, project_skill
    assert "visible goal text short" in project_skill, project_skill
    assert "--source heartbeat --execute" in project_skill, project_skill
    assert "no-progress self-stop guard" in project_skill, project_skill
    assert "consecutive eligible heartbeat turns" in project_skill, project_skill
    assert "Routine public repo publication is a boundary decision" in project_skill, project_skill
    assert "Do not reintroduce a user gate for public-safe publication itself" in project_skill, project_skill
    assert "notify_user_on_open_todo=true" in project_skill, project_skill
    assert "blocker-push `NOTIFY`" in project_skill, project_skill
    assert "heartbeat_recommendation" in project_skill, project_skill
    assert "mapped_noop_if_unchanged" in project_skill, project_skill
    assert "reason to paste one-off control logic into the scheduler" in project_skill, project_skill

    cli_json = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "--format",
            "json",
            "heartbeat-prompt",
            "--goal-id",
            GOAL_ID,
            "--active-state",
            str(ACTIVE_STATE),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cli_payload = json.loads(cli_json.stdout)
    assert cli_payload["task_body"] == payload["task_body"], cli_payload
    assert cli_payload["compact"] is False, cli_payload

    cli_compact_json = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "--format",
            "json",
            "heartbeat-prompt",
            "--goal-id",
            GOAL_ID,
            "--active-state",
            str(ACTIVE_STATE),
            "--compact",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cli_compact_payload = json.loads(cli_compact_json.stdout)
    assert cli_compact_payload["task_body"] == compact_payload["task_body"], cli_compact_payload
    assert cli_compact_payload["compact"] is True, cli_compact_payload

    cli_markdown = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "heartbeat-prompt",
            "--goal-id",
            GOAL_ID,
            "--active-state",
            str(ACTIVE_STATE),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "# Heartbeat Automation Prompt" in cli_markdown, cli_markdown
    assert "Copy this task body into a Codex App heartbeat automation." in cli_markdown, cli_markdown
    assert str(ACTIVE_STATE) in cli_markdown, cli_markdown
    print("heartbeat-prompt-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
