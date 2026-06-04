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
INTERFACE_BUDGET_CHARS = {
    "full": 10_000,
    "compact": 4_500,
    "brief": 2_500,
}
PROJECT_SPECIFIC_PROMPT_LEAKS = (
    "agent-harness-side-bypass",
    "agent-harness-main-control",
    "OpenViking",
    "managed Lark mirrors",
    "docs/TODO.md",
    "premium-ui",
    "tiger-team",
)


def normalized(text: str) -> str:
    return " ".join(text.split())


def prompt_budget_text(text: str) -> str:
    return text.replace(GOAL_ID, "<GOAL_ID>").replace(str(ACTIVE_STATE), "<ACTIVE_GOAL_STATE_PATH>")


def assert_prompt_budget(label: str, text: str) -> None:
    budget_text = prompt_budget_text(text)
    assert len(budget_text) <= INTERFACE_BUDGET_CHARS[label], (
        label,
        len(budget_text),
        INTERFACE_BUDGET_CHARS[label],
    )


def assert_no_project_specific_prompt_leaks(label: str, text: str) -> None:
    for phrase in PROJECT_SPECIFIC_PROMPT_LEAKS:
        assert phrase not in text, (label, phrase)


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
    brief_payload = build_heartbeat_prompt(goal_id=GOAL_ID, active_state=ACTIVE_STATE, brief=True)
    assert_prompt_budget("full", str(payload["task_body"]))
    assert_prompt_budget("compact", str(compact_payload["task_body"]))
    assert_prompt_budget("brief", str(brief_payload["task_body"]))
    assert_no_project_specific_prompt_leaks("full", str(payload["task_body"]))
    assert_no_project_specific_prompt_leaks("compact", str(compact_payload["task_body"]))
    assert_no_project_specific_prompt_leaks("brief", str(brief_payload["task_body"]))
    assert payload["quota_guard_command"] == (
        'goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" '
        "quota should-run --goal-id public-heartbeat-goal"
    ), payload
    assert payload["quota_spend_command"] == (
        'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" '
        "quota spend-slot --goal-id public-heartbeat-goal --slots 1 --source heartbeat --execute"
    ), payload
    assert compact_payload["compact"] is True, compact_payload
    assert compact_payload["brief"] is False, compact_payload
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
        "goal_boundary",
        "delivery_batch_scale",
        "Legacy/raw fallback is not owner/gate/stop authority",
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
    assert brief_payload["brief"] is True, brief_payload
    assert brief_payload["compact"] is False, brief_payload
    assert brief_payload["quota_guard_command"] == payload["quota_guard_command"], brief_payload
    assert brief_payload["quota_spend_command"] == payload["quota_spend_command"], brief_payload
    assert len(str(brief_payload["task_body"])) < len(str(compact_payload["task_body"])) * 0.55, (
        len(str(brief_payload["task_body"])),
        len(str(compact_payload["task_body"])),
    )
    brief_task = normalized(str(brief_payload["task_body"]))
    for phrase in (
        "Brief installed Goal Harness heartbeat",
        "goal-harness heartbeat-prompt --compact --goal-id public-heartbeat-goal --active-state /tmp/public-heartbeat-goal/ACTIVE_GOAL_STATE.md",
        "Preflight and quota guard",
        'goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" quota should-run --goal-id public-heartbeat-goal',
        "gate or open user todo",
        "heartbeat_recommendation",
        "goal_boundary",
        "project_asset source labels",
        "steering audit with product-bottleneck lens",
        "choose one bounded verifiable progress segment",
        "goal-harness todo add",
        'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id public-heartbeat-goal --slots 1 --source heartbeat --execute',
        "No spend for quiet skips",
    ):
        assert phrase in brief_task, phrase

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
        "quota should-run.goal_boundary",
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
        "raw queue fields are not owner/gate/stop authority",
        "run_history.latest_runs as evidence and drill-down only",
        "do not decide whether a gate is pending or approved from latest runs alone",
        "goal_boundary",
        "If an open user/owner todo is the current blocker that can unlock a gate, focus_wait, or external-evidence wait",
        "no quota spend for that blocker-push turn",
        "heartbeat_recommendation",
        "recommended_mode=run_first_read_only_map",
        "real read-only map, not another dry-run",
        "read_only_project_map result",
        "recommended_mode=mapped_noop_if_unchanged",
        "stop_if_unchanged=true",
        "no new user instruction, owner evidence, agent todo, stale source, or safe handoff",
        "return quiet `DONT_NOTIFY`: do not run, edit, or spend",
        "Check `delivery_batch_scale` before tightening project-agent handoffs",
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
        "Choose one bounded, verifiable progress segment from that audit",
        "coherent batch across related implementation, test, doc, and state-writeback",
        "not be forced into a tiny single-file step",
        "Stay inside goal_boundary when present",
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
        'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id <GOAL_ID> --slots 1 --source heartbeat --execute',
        "goal-harness refresh-state --goal-id <GOAL_ID>",
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
        "quota should-run.goal_boundary",
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
        "raw queue fields are not owner/gate/stop authority",
        "run_history.latest_runs` as evidence and drill-down only",
        "do not decide whether a gate is pending or approved from latest runs alone",
        "goal_boundary",
        "current blocker that can unlock a gate, `focus_wait`, or external-evidence wait",
        "no quota spend for that blocker-push turn",
        "heartbeat_recommendation",
        "recommended_mode=run_first_read_only_map",
        "real read-only map, not another dry-run",
        "read_only_project_map` result",
        "recommended_mode=mapped_noop_if_unchanged",
        "stop_if_unchanged=true",
        "no new user instruction, owner evidence, agent todo, stale source, or safe handoff",
        "return quiet `DONT_NOTIFY`: do not run, edit, or spend",
        "Check `delivery_batch_scale` before tightening project-agent handoffs",
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
        "Choose one bounded, verifiable progress segment from that audit",
        "coherent batch across related implementation, test, doc, and state-writeback",
        "Stay inside `goal_boundary` when present",
        "Public-safe repo publication is not an operator gate by itself",
        "commit, push, and PR creation may proceed autonomously after validation",
        "clean public/private boundary scan",
        "If the step discovers a concrete user/owner action",
        "goal-harness todo add --goal-id public-heartbeat-goal --role user --text \"<public-safe user/owner action>\"",
        "docs/project-agent-todo-contract.md",
        'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id public-heartbeat-goal --slots 1 --source heartbeat --execute',
        "goal-harness refresh-state --goal-id public-heartbeat-goal",
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
            "Also inspect goal_boundary",
            "same blocker-push opportunity",
            "heartbeat_recommendation",
            "recommended_mode=run_first_read_only_map",
            "recommended_mode=mapped_noop_if_unchanged",
            "Run a short steering audit before choosing work",
            "Include a product bottleneck lens",
            "Run the no-progress self-stop check before choosing delivery work",
            "Choose one bounded, verifiable progress segment from that audit",
            "Public-safe repo publication is not an operator gate by itself",
            "Run the smallest useful validation",
            'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id <GOAL_ID> --slots 1 --source heartbeat --execute',
            "goal-harness refresh-state --goal-id <GOAL_ID>",
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
    assert "--brief" in doc, doc
    assert "Do not hand-edit per-project lifecycle branches" in doc, doc
    assert "goal-harness heartbeat-prompt" in integration_doc, integration_doc
    assert "goal-harness heartbeat-prompt --compact" in integration_doc, integration_doc
    assert "goal-harness heartbeat-prompt --brief" in integration_doc, integration_doc
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
    assert "--brief" in project_skill, project_skill
    assert "goal_boundary" in project_skill, project_skill
    assert "smoke" in project_skill and "contract" in project_skill, project_skill
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
    assert "legacy/raw fallback" in project_skill, project_skill
    assert "do not infer" in project_skill, project_skill
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
    assert cli_payload["brief"] is False, cli_payload

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

    cli_brief_json = subprocess.run(
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
            "--brief",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cli_brief_payload = json.loads(cli_brief_json.stdout)
    assert cli_brief_payload["task_body"] == brief_payload["task_body"], cli_brief_payload
    assert cli_brief_payload["brief"] is True, cli_brief_payload

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
