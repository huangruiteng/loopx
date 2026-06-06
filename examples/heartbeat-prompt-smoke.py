#!/usr/bin/env python3
"""Smoke-test the reusable heartbeat automation prompt contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.heartbeat_prompt import INTERFACE_BUDGET_CHARS, build_heartbeat_prompt  # noqa: E402

DOC = REPO_ROOT / "docs" / "heartbeat-automation-prompt.md"
README = REPO_ROOT / "README.md"
INTEGRATION_DOC = REPO_ROOT / "docs" / "integration.md"
PROJECT_SKILL = REPO_ROOT / "skills" / "goal-harness-project" / "SKILL.md"
GOAL_ID = "public-heartbeat-goal"
ACTIVE_STATE = Path("/tmp/public-heartbeat-goal/ACTIVE_GOAL_STATE.md")
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


def assert_interface_budget_payload(label: str, payload: dict) -> None:
    task_body = str(payload["task_body"])
    budget = payload.get("interface_budget")
    assert isinstance(budget, dict), (label, payload)
    assert budget["mode"] == label, budget
    assert budget["char_count"] == len(task_body), budget
    assert budget["line_count"] == len(task_body.splitlines()), budget
    assert budget["budget_char_count"] == len(prompt_budget_text(task_body)), budget
    assert budget["max_chars"] == INTERFACE_BUDGET_CHARS[label], budget
    assert budget["within_budget"] is True, budget


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
    thin_payload = build_heartbeat_prompt(goal_id=GOAL_ID, active_state=ACTIVE_STATE, thin=True)
    registry_default_payload = build_heartbeat_prompt(goal_id=GOAL_ID, compact=True)
    assert_prompt_budget("full", str(payload["task_body"]))
    assert_prompt_budget("compact", str(compact_payload["task_body"]))
    assert_prompt_budget("brief", str(brief_payload["task_body"]))
    assert_prompt_budget("thin", str(thin_payload["task_body"]))
    assert_interface_budget_payload("full", payload)
    assert_interface_budget_payload("compact", compact_payload)
    assert_interface_budget_payload("brief", brief_payload)
    assert_interface_budget_payload("thin", thin_payload)
    assert_no_project_specific_prompt_leaks("full", str(payload["task_body"]))
    assert_no_project_specific_prompt_leaks("compact", str(compact_payload["task_body"]))
    assert_no_project_specific_prompt_leaks("brief", str(brief_payload["task_body"]))
    assert_no_project_specific_prompt_leaks("thin", str(thin_payload["task_body"]))
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
    assert compact_payload["thin"] is False, compact_payload
    assert payload["active_state_source"] == "explicit", payload
    assert payload["resolved_active_state"] == str(ACTIVE_STATE), payload
    assert compact_payload["quota_guard_command"] == payload["quota_guard_command"], compact_payload
    assert compact_payload["quota_spend_command"] == payload["quota_spend_command"], compact_payload
    assert len(str(compact_payload["task_body"])) < len(str(payload["task_body"])) * 0.47, (
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
        "safe_bypass_kind=outcome_floor_recovery",
        "ranker/cross-domain evidence artifact",
        "status/log/metric/marker poll",
        "heartbeat_recommendation",
        "goal_boundary",
        "delivery_batch_scale",
        "delivery_outcome",
        "post_handoff_outcome_gap_streak",
        "handoff_delivery_contract",
        "Legacy/raw fallback is not owner/gate/stop authority",
        "run_first_read_only_map",
        "mapped_noop_if_unchanged",
        "steering audit",
        "bottleneck lens",
        "no-progress self-stop check",
        "Public-safe commit/push/PR may proceed",
        "goal-harness todo add --goal-id public-heartbeat-goal --role user|agent",
        'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id public-heartbeat-goal --slots 1 --source heartbeat --execute',
        "validated progress artifacts pass explicit `--delivery-batch-scale` and `--delivery-outcome`",
        "Do not append spend for quiet skips",
    ):
        assert phrase in compact_task, phrase
    registry_default_task = normalized(str(registry_default_payload["task_body"]))
    assert registry_default_payload["active_state"] == "the registry-declared active state", registry_default_payload
    assert registry_default_payload["active_state_source"] == "registry", registry_default_payload
    assert registry_default_payload["expanded_prompt_command"] == (
        "goal-harness heartbeat-prompt --goal-id public-heartbeat-goal"
    ), registry_default_payload
    assert registry_default_payload["compact_prompt_command"] == (
        "goal-harness heartbeat-prompt --compact --goal-id public-heartbeat-goal"
    ), registry_default_payload
    assert "using `the registry-declared active state`" in registry_default_task, registry_default_task
    assert "--active-state" not in registry_default_payload["expanded_prompt_command"], registry_default_payload
    assert brief_payload["brief"] is True, brief_payload
    assert brief_payload["compact"] is False, brief_payload
    assert brief_payload["thin"] is False, brief_payload
    assert brief_payload["quota_guard_command"] == payload["quota_guard_command"], brief_payload
    assert brief_payload["quota_spend_command"] == payload["quota_spend_command"], brief_payload
    assert len(str(brief_payload["task_body"])) < len(str(compact_payload["task_body"])) * 0.55, (
        len(str(brief_payload["task_body"])),
        len(str(compact_payload["task_body"])),
    )
    brief_task = normalized(str(brief_payload["task_body"]))
    for phrase in (
        "Brief installed Goal Harness heartbeat",
        "Thin dispatcher",
        "pull details on demand",
        "goal-harness heartbeat-prompt --compact --goal-id public-heartbeat-goal --active-state /tmp/public-heartbeat-goal/ACTIVE_GOAL_STATE.md",
        "Preflight and quota guard",
        'goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" quota should-run --goal-id public-heartbeat-goal',
        "Gate/open todo ->",
        "status/log/metric/marker poll",
        "safe_bypass_kind=outcome_floor_recovery",
        "ranker/cross-domain evidence recovery",
        "state priority slice",
        "guard payload",
        "status --limit 3",
        "review-packet --handoff-only",
        "heartbeat_recommendation",
        "goal_boundary",
        "bounded segment/batch",
        "validate/writeback/todos",
        "explicit delivery scale/outcome for progress artifacts",
        'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id public-heartbeat-goal --slots 1 --source heartbeat --execute',
        "No spend for quiet skips",
    ):
        assert phrase in brief_task, phrase
    assert thin_payload["thin"] is True, thin_payload
    assert thin_payload["brief"] is False, thin_payload
    assert thin_payload["compact"] is False, thin_payload
    assert thin_payload["thin_prompt_command"] == (
        "goal-harness heartbeat-prompt --thin --goal-id public-heartbeat-goal "
        "--active-state /tmp/public-heartbeat-goal/ACTIVE_GOAL_STATE.md"
    ), thin_payload
    assert len(str(thin_payload["task_body"])) < len(str(brief_payload["task_body"])) * 0.45, (
        len(str(thin_payload["task_body"])),
        len(str(brief_payload["task_body"])),
    )
    thin_task = normalized(str(thin_payload["task_body"]))
    for phrase in (
        "Advance `public-heartbeat-goal` from /tmp/public-heartbeat-goal/ACTIVE_GOAL_STATE.md",
        "use your normal Codex abilities",
        "registry/global quota truth",
        "active state, status/run history, repo state",
        "decide one bounded useful action or a quiet no-op",
        "observe connected controllers",
        "identify the current bottleneck",
        "repair bounded Goal Harness control-plane/product issues",
        "write back durable state/events",
        "spend quota exactly once only after validated delivery",
        "If there is no new evidence or useful bounded work, stay quiet and do not spend",
        "Keep the heartbeat thin",
        "Do not encode project-specific branches here",
        "Do not consume the learning material queue unless explicitly asked",
        "Stop for private material, credentials, destructive git, or unauthorized production actions",
    ):
        assert phrase in thin_task, phrase

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
        "do not append quota spend",
        "safe_bypass_allowed=true",
        "gate blocks only the gated delivery path",
        "one bounded safe-bypass step",
        "that report must include the existing open user todos",
        "safe_bypass_kind=outcome_floor_recovery",
        "ranker/cross-domain evidence artifact",
        "explicitly a monitor",
        "status/log/metric/marker surfaces",
        "New eval/fail/complete/blocker",
        "state/board/ledger",
        "Still do not launch/stop/restart/sync/design code",
        "DONT_NOTIFY",
        "should_run=true",
        "When you inspect current Goal Harness routing",
        "attention_queue.items",
        "project_asset are authoritative",
        "raw queue fields are not owner/gate/stop authority",
        "run_history.latest_runs as evidence and drill-down only",
        "do not decide whether a gate is pending or approved from latest runs alone",
        "goal_boundary",
        "Stop for an open user/owner todo only when it belongs to this goal's guard payload or current project asset",
        "Dependency or sibling-goal todos found in `attention_queue.items` should be recorded as dependency blockers",
        "must not consume the whole eligible turn",
        "choose a gate-independent P0/P1/P2 candidate for this goal when one exists",
        "then use the blocker-push pattern above",
        "do not append quota spend",
        "heartbeat_recommendation",
        "recommended_mode=run_first_read_only_map",
        "real read-only map, not another dry-run",
        "read_only_project_map result",
        "recommended_mode=mapped_noop_if_unchanged",
        "stop_if_unchanged=true",
        "no new user instruction, owner evidence, agent todo, stale source, or safe handoff",
        "return quiet `DONT_NOTIFY`: do not run, edit, or spend",
        "Check `delivery_batch_scale`, `delivery_outcome`,",
        "repeated-small or surface-only loops",
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
        "--classification <PUBLIC_SAFE_PROGRESS_CLASSIFICATION>",
        "--delivery-batch-scale multi_surface",
        "--delivery-outcome outcome_progress",
        "append exactly one",
        "Do not append spend for quiet should_run=false skips, preflight failures, pure dry-run previews, or duplicate accounting attempts",
        "safe_bypass_allowed=true and you actually completed a bounded safe-bypass step",
        "safe_bypass_kind=outcome_floor_recovery",
        "ranker/cross-domain evidence artifact",
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
        "do not append quota spend",
        "safe_bypass_allowed=true",
        "gate blocks only the gated delivery path",
        "one bounded safe-bypass step",
        "that report must include the existing open user todos",
        "explicitly a monitor",
        "status/log/metric/marker surfaces",
        "New eval/fail/complete/blocker",
        "state/board/ledger",
        "Still do not launch/stop/restart/sync/design code",
        "DONT_NOTIFY",
        "When you inspect current Goal Harness routing",
        "attention_queue.items",
        "project_asset` are authoritative",
        "raw queue fields are not owner/gate/stop authority",
        "run_history.latest_runs` as evidence and drill-down only",
        "do not decide whether a gate is pending or approved from latest runs alone",
        "goal_boundary",
        "then use the blocker-push pattern above",
        "do not append quota spend",
        "heartbeat_recommendation",
        "recommended_mode=run_first_read_only_map",
        "real read-only map, not another dry-run",
        "read_only_project_map` result",
        "recommended_mode=mapped_noop_if_unchanged",
        "stop_if_unchanged=true",
        "no new user instruction, owner evidence, agent todo, stale source, or safe handoff",
        "return quiet `DONT_NOTIFY`: do not run, edit, or spend",
        "Check `delivery_batch_scale`, `delivery_outcome`,",
        "repeated-small or surface-only loops",
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
        "--classification <PUBLIC_SAFE_PROGRESS_CLASSIFICATION>",
        "--delivery-batch-scale multi_surface",
        "--delivery-outcome outcome_progress",
        "readiness does not infer from classification names",
        "Do not append spend for quiet `should_run=false` skips",
        "safe_bypass_kind=outcome_floor_recovery",
        "ranker/cross-domain evidence artifact",
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
            "explicitly a monitor",
            "status/log/metric/marker surfaces",
            "New eval/fail/complete/blocker",
            "If the result says should_run=true",
            "When you inspect current Goal Harness routing",
            "attention_queue.items",
            "run_history.latest_runs",
            "Also inspect goal_boundary",
            "then use the blocker-push pattern above",
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
    assert "goal-harness-canary" in readme, readme
    assert "release snapshot" in readme, readme
    assert "heartbeat_recommendation" in readme, readme
    assert "do not hand-edit one-off automation prompt branches" in normalized(readme), readme
    assert "goal-harness heartbeat-prompt" in doc, doc
    assert "--compact" in doc, doc
    assert "--brief" in doc, doc
    assert "--thin" in doc, doc
    assert "--cli-bin goal-harness-canary" in doc, doc
    assert "Do not hand-edit per-project lifecycle branches" in doc, doc
    assert "goal-harness heartbeat-prompt" in integration_doc, integration_doc
    assert "goal-harness heartbeat-prompt --compact" in integration_doc, integration_doc
    assert "goal-harness heartbeat-prompt --brief" in integration_doc, integration_doc
    assert "goal-harness heartbeat-prompt --thin" in integration_doc, integration_doc
    assert "goal-harness-canary heartbeat-prompt" in integration_doc, integration_doc
    assert "--cli-bin goal-harness-canary" in integration_doc, integration_doc
    assert "local release snapshot" in integration_doc, integration_doc
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
    assert "--thin" in project_skill, project_skill
    assert "goal_boundary" in project_skill, project_skill
    assert "smoke" in project_skill and "contract" in project_skill, project_skill
    assert "Set Up Recurring Heartbeats" in project_skill, project_skill
    assert "visible goal text short" in project_skill, project_skill
    assert "--source heartbeat --execute" in project_skill, project_skill
    assert "--classification <PUBLIC_SAFE_PROGRESS_CLASSIFICATION>" in project_skill, project_skill
    assert "--delivery-batch-scale multi_surface" in project_skill, project_skill
    assert "--delivery-outcome outcome_progress" in project_skill, project_skill
    assert "do not infer scale/outcome from the classification name" in normalized(project_skill), project_skill
    assert "no-progress self-stop guard" in project_skill, project_skill
    assert "consecutive eligible heartbeat turns" in project_skill, project_skill
    assert "Routine public repo publication is a boundary decision" in project_skill, project_skill
    assert "Do not reintroduce a user gate for public-safe publication itself" in project_skill, project_skill
    assert "notify_user_on_open_todo=true" in project_skill, project_skill
    assert "blocker-push `NOTIFY`" in project_skill, project_skill
    assert "sibling-goal todos" in project_skill, project_skill
    assert "must not consume the whole eligible turn" in project_skill, project_skill
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
    assert cli_payload["cli_bin"] == "goal-harness", cli_payload
    assert cli_payload["active_state_source"] == "explicit", cli_payload

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
    assert cli_brief_payload["cli_bin"] == "goal-harness", cli_brief_payload

    cli_thin_json = subprocess.run(
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
            "--thin",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cli_thin_payload = json.loads(cli_thin_json.stdout)
    assert cli_thin_payload["task_body"] == thin_payload["task_body"], cli_thin_payload
    assert cli_thin_payload["thin"] is True, cli_thin_payload
    assert cli_thin_payload["cli_bin"] == "goal-harness", cli_thin_payload

    cli_canary_json = subprocess.run(
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
            "--cli-bin",
            "goal-harness-canary",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cli_canary_payload = json.loads(cli_canary_json.stdout)
    assert cli_canary_payload["cli_bin"] == "goal-harness-canary", cli_canary_payload
    assert "goal-harness-canary doctor" in cli_canary_payload["cli_preflight"], cli_canary_payload
    assert "goal-harness-canary --format json" in cli_canary_payload["quota_guard_command"], cli_canary_payload
    assert "goal-harness-canary heartbeat-prompt --compact" in cli_canary_payload["task_body"], cli_canary_payload

    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        project = root / "project"
        state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
        registry_path = project / ".goal-harness" / "registry.json"
        state_file.parent.mkdir(parents=True)
        registry_path.parent.mkdir(parents=True)
        state_file.write_text("# Active State\n", encoding="utf-8")
        registry_path.write_text(
            json.dumps(
                {
                    "goals": [
                        {
                            "id": GOAL_ID,
                            "domain": "smoke",
                            "status": "active",
                            "repo": str(project),
                            "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                            "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        cli_registry_default_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "goal_harness.cli",
                "--format",
                "json",
                "--registry",
                str(registry_path),
                "heartbeat-prompt",
                "--goal-id",
                GOAL_ID,
                "--brief",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cli_registry_default_payload = json.loads(cli_registry_default_json.stdout)
        assert cli_registry_default_payload["brief"] is True, cli_registry_default_payload
        assert cli_registry_default_payload["active_state"] == "the registry-declared active state", (
            cli_registry_default_payload
        )
        assert cli_registry_default_payload["active_state_source"].startswith("registry:"), cli_registry_default_payload
        assert cli_registry_default_payload["resolved_active_state"] == str(state_file), cli_registry_default_payload
        assert cli_registry_default_payload["expanded_prompt_command"] == (
            "goal-harness heartbeat-prompt --goal-id public-heartbeat-goal"
        ), cli_registry_default_payload
        assert "goal-harness heartbeat-prompt --compact --goal-id public-heartbeat-goal" in (
            cli_registry_default_payload["task_body"]
        ), cli_registry_default_payload
        assert "--active-state" not in cli_registry_default_payload["task_body"], cli_registry_default_payload
        cli_registry_thin_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "goal_harness.cli",
                "--format",
                "json",
                "--registry",
                str(registry_path),
                "heartbeat-prompt",
                "--goal-id",
                GOAL_ID,
                "--thin",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cli_registry_thin_payload = json.loads(cli_registry_thin_json.stdout)
        assert cli_registry_thin_payload["thin"] is True, cli_registry_thin_payload
        assert cli_registry_thin_payload["active_state"] == "the registry-declared active state", (
            cli_registry_thin_payload
        )
        assert cli_registry_thin_payload["resolved_active_state"] == str(state_file), cli_registry_thin_payload
        assert "Advance `public-heartbeat-goal` from the registry-declared active state." in (
            cli_registry_thin_payload["task_body"]
        ), cli_registry_thin_payload
        assert "--active-state" not in cli_registry_thin_payload["task_body"], cli_registry_thin_payload

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
