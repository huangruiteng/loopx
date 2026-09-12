from __future__ import annotations

import json
from typing import Any


def render_codex_cli_session_probe_markdown(payload: dict[str, Any]) -> str:
    capabilities = payload.get("capabilities") or {}
    boundary = payload.get("boundary") or {}
    warnings = payload.get("warnings") or []
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Session Probe

- source: `{payload.get("source")}`
- recommended_mode: `{payload.get("recommended_mode")}`
- automation_action: `{payload.get("automation_action")}`

## Capabilities

- exec_supported: `{capabilities.get("exec_supported")}`
- resume_supported: `{capabilities.get("resume_supported")}`
- session_handle_detected: `{capabilities.get("session_handle_detected")}`
- visible_resume_supported: `{capabilities.get("visible_resume_supported")}`
- remote_control_surface_detected: `{capabilities.get("remote_control_surface_detected")}`
- same_tui_injection_detected: `{capabilities.get("same_tui_injection_detected")}`
- safe_injection_supported: `{capabilities.get("safe_injection_supported")}`

## Boundary

- help_only_probe: `{boundary.get("help_only_probe")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_credentials: `{boundary.get("reads_credentials")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`

## Warnings

{warning_lines}
"""



def render_codex_cli_visible_driver_plan_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    steps = payload.get("driver_steps") if isinstance(payload.get("driver_steps"), list) else []
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    headless_line = commands.get("explicit_headless_fallback") or (
        f"# {commands.get('headless_fallback_disabled') or 'headless fallback disabled'}"
    )
    return f"""# Codex CLI Visible Driver Plan

- driver_mode: `{payload.get("driver_mode")}`
- automation_action: `{payload.get("automation_action")}`
- probe_recommended_mode: `{payload.get("probe_recommended_mode")}`
- next_step: {payload.get("next_step")}

## Commands

```bash
{commands.get("probe")}
{commands.get("quota_guard")}
{commands.get("tui_bootstrap_message")}
{headless_line}
```

## Driver Steps

{step_lines}

## Boundary

- dry_run_plan_only: `{boundary.get("dry_run_plan_only")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- requires_idle_guard_before_visible_prompt: `{boundary.get("requires_idle_guard_before_visible_prompt")}`
- requires_user_gate_stop: `{boundary.get("requires_user_gate_stop")}`

## Warnings

{warning_lines}
"""



def render_codex_cli_local_driver_plan_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    steps = payload.get("driver_steps") if isinstance(payload.get("driver_steps"), list) else []
    idle_guard = payload.get("idle_guard") if isinstance(payload.get("idle_guard"), dict) else {}
    policy = payload.get("execution_policy") if isinstance(payload.get("execution_policy"), dict) else {}
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    headless_line = commands.get("explicit_headless_fallback") or (
        f"# {commands.get('headless_fallback_disabled') or 'headless fallback disabled'}"
    )
    return f"""# Codex CLI Local Driver Plan

- driver_phase: `{payload.get("driver_phase")}`
- driver_mode: `{payload.get("driver_mode")}`
- decision: `{payload.get("decision")}`
- operator_instruction: {payload.get("operator_instruction")}

## Commands

```bash
{commands.get("quota_guard")}
{commands.get("visible_driver_plan")}
{commands.get("tui_bootstrap_message")}
{headless_line}
```

## Driver Steps

{step_lines}

## Idle Guard

- required: `{idle_guard.get("required")}`
- implemented: `{idle_guard.get("implemented")}`
- placeholder: {idle_guard.get("placeholder")}

## Execution Policy

- tui_bootstrap_primary: `{policy.get("tui_bootstrap_primary")}`
- headless_execution_disabled: `{policy.get("headless_execution_disabled")}`
- same_session_attachment_requires_visible_proof: `{policy.get("same_session_attachment_requires_visible_proof")}`
- quota_guard_required: `{policy.get("quota_guard_required")}`
- spend_after_validated_writeback_only: `{policy.get("spend_after_validated_writeback_only")}`

## Boundary

- dry_run_plan_only: `{boundary.get("dry_run_plan_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`

## Warnings

{warning_lines}
"""



def render_codex_cli_visible_driver_run_packet_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    steps = payload.get("driver_steps") if isinstance(payload.get("driver_steps"), list) else []
    proof = payload.get("visible_session_proof") if isinstance(payload.get("visible_session_proof"), dict) else {}
    policy = payload.get("execution_policy") if isinstance(payload.get("execution_policy"), dict) else {}
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    headless_line = commands.get("explicit_headless_fallback") or (
        f"# {commands.get('headless_fallback_disabled') or 'headless fallback disabled'}"
    )
    return f"""# Codex CLI Visible Driver Run Packet

- driver_phase: `{payload.get("driver_phase")}`
- driver_mode: `{payload.get("driver_mode")}`
- decision: `{payload.get("decision")}`
- next_driver_action: `{payload.get("next_driver_action")}`
- allow_headless_fallback: `{payload.get("allow_headless_fallback")}`

## Recommended Command

```bash
{payload.get("recommended_command")}
```

## Commands

```bash
{commands.get("quota_guard")}
{commands.get("tui_bootstrap_message")}
{commands.get("visible_session_proof")}
{headless_line}
```

## Visible Session Proof

- supplied: `{proof.get("supplied")}`
- approved: `{proof.get("approved")}`
- decision: `{proof.get("decision")}`
- failures: `{proof.get("failures")}`

## Driver Steps

{step_lines}

## Execution Policy

- tui_bootstrap_primary: `{policy.get("tui_bootstrap_primary")}`
- same_session_attachment_requires_visible_proof: `{policy.get("same_session_attachment_requires_visible_proof")}`
- headless_execution_disabled: `{policy.get("headless_execution_disabled")}`
- quota_guard_required: `{policy.get("quota_guard_required")}`
- idle_guard_required_before_visible_prompt: `{policy.get("idle_guard_required_before_visible_prompt")}`
- spend_after_validated_writeback_only: `{policy.get("spend_after_validated_writeback_only")}`

## Boundary

- run_packet_only: `{boundary.get("run_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- headless_execution_disabled: `{boundary.get("headless_execution_disabled")}`

## Warnings

{warning_lines}
"""



def render_codex_cli_local_scheduler_tick_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    launchd = payload.get("launchd") if isinstance(payload.get("launchd"), dict) else {}
    scheduler_hint = (
        payload.get("scheduler_hint")
        if isinstance(payload.get("scheduler_hint"), dict)
        else {}
    )
    local_scheduler = (
        scheduler_hint.get("local_scheduler")
        if isinstance(scheduler_hint.get("local_scheduler"), dict)
        else {}
    )
    codex_app = (
        scheduler_hint.get("app_automation")
        if isinstance(scheduler_hint.get("app_automation"), dict)
        else scheduler_hint.get("codex_app")
        if isinstance(scheduler_hint.get("codex_app"), dict)
        else {}
    )
    unchanged_poll = (
        scheduler_hint.get("unchanged_poll")
        if isinstance(scheduler_hint.get("unchanged_poll"), dict)
        else {}
    )
    limits = unchanged_poll.get("limits") if isinstance(unchanged_poll.get("limits"), dict) else {}
    after_limits = (
        unchanged_poll.get("after_limits")
        if isinstance(unchanged_poll.get("after_limits"), dict)
        else {}
    )
    local_interval = (
        local_scheduler.get("recommended_interval_minutes")
        or codex_app.get("recommended_interval_minutes")
    )
    local_progression = (
        local_scheduler.get("example_progression_minutes")
        or codex_app.get("example_progression_minutes")
    )
    local_unchanged_limit = (
        local_scheduler.get("unchanged_poll_limit")
        if "unchanged_poll_limit" in local_scheduler
        else limits.get("local_scheduler")
    )
    local_after_limit = (
        local_scheduler.get("after_limit")
        or after_limits.get("local_scheduler")
    )
    final_replan_check = (
        local_scheduler.get("final_quota_replan_check")
        or {
            "enabled": unchanged_poll.get("final_quota_replan_check_enabled"),
            "action": unchanged_poll.get("final_quota_replan_check_action"),
        }
    )
    blocker = payload.get("precise_blocker") if isinstance(payload.get("precise_blocker"), dict) else None
    runtime_idle = (
        payload.get("runtime_idle_detector")
        if isinstance(payload.get("runtime_idle_detector"), dict)
        else {}
    )
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    blocker_lines = "- none"
    if blocker:
        blocker_lines = f"- reason: `{blocker.get('reason')}`\n- message: {blocker.get('message')}"
    return f"""# Codex CLI Local Scheduler Tick

- scheduler_phase: `{payload.get("scheduler_phase")}`
- scheduler_action: `{payload.get("scheduler_action")}`
- decision: `{payload.get("decision")}`
- next_safe_step: {payload.get("next_safe_step")}

## Commands

```bash
{commands.get("visible_driver_run")}
{commands.get("runtime_idle_detector")}
{commands.get("runtime_idle_detector_fixture")}
{commands.get("scheduler_tick")}
{commands.get("candidate_codex_command") or "# no Codex command candidate"}
{commands.get("blocker_writeback") or "# no blocker writeback command"}
```

## Precise Blocker

{blocker_lines}

## Runtime Idle Detector

- supplied: `{runtime_idle.get("supplied")}`
- approved: `{runtime_idle.get("approved")}`
- decision: `{runtime_idle.get("decision")}`
- failures: `{runtime_idle.get("failures")}`

## Launchd Shape

- label: `{launchd.get("label")}`
- keep_alive: `{launchd.get("keep_alive")}`
- recommended_interval_seconds: `{launchd.get("recommended_interval_seconds")}`
- one_shot_command: `{launchd.get("one_shot_command")}`

## Scheduler Hint

- action: `{scheduler_hint.get("action")}`
- cadence_class: `{scheduler_hint.get("cadence_class")}`
- local_interval_minutes: `{local_interval}`
- local_progression_minutes: `{local_progression}`
- local_unchanged_poll_limit: `{local_unchanged_limit}`
- local_after_limit: `{local_after_limit}`
- final_quota_replan_check: `{final_replan_check}`

## Boundary

- tick_packet_only: `{boundary.get("tick_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`
- visible_candidate_requires_runtime_idle_detector: `{boundary.get("visible_candidate_requires_runtime_idle_detector")}`
- headless_execution_disabled: `{boundary.get("headless_execution_disabled")}`

## Warnings

{warning_lines}
"""



def render_codex_cli_local_scheduler_executor_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    request = payload.get("execution_request") if isinstance(payload.get("execution_request"), dict) else {}
    scheduler_tick = payload.get("scheduler_tick") if isinstance(payload.get("scheduler_tick"), dict) else {}
    runtime_idle = (
        scheduler_tick.get("runtime_idle_detector")
        if isinstance(scheduler_tick.get("runtime_idle_detector"), dict)
        else {}
    )
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Local Scheduler Executor

- executor_phase: `{payload.get("executor_phase")}`
- scheduler_action: `{payload.get("scheduler_action")}`
- decision: `{payload.get("decision")}`
- next_safe_step: {payload.get("next_safe_step")}

## Execution Request

- execute_candidate: `{request.get("execute_candidate")}`
- execute_blocker_writeback: `{request.get("execute_blocker_writeback")}`
- guard_checked: `{request.get("guard_checked")}`
- candidate_command_prefixes: `{request.get("candidate_command_prefixes")}`
- executor_timeout_seconds: `{request.get("executor_timeout_seconds")}`
- runtime_idle_detector_required_for_visible_candidate: `{request.get("runtime_idle_detector_required_for_visible_candidate")}`

## Execution Result

- attempted: `{execution.get("attempted")}`
- executed: `{execution.get("executed")}`
- kind: `{execution.get("kind")}`
- reason: `{execution.get("reason")}`
- returncode: `{execution.get("returncode")}`
- timed_out: `{execution.get("timed_out")}`
- output_captured: `{execution.get("output_captured")}`
- candidate_prefix_matched: `{execution.get("candidate_prefix_matched")}`

## Runtime Idle Detector

- supplied: `{runtime_idle.get("supplied")}`
- approved: `{runtime_idle.get("approved")}`
- decision: `{runtime_idle.get("decision")}`
- failures: `{runtime_idle.get("failures")}`

## Commands

```bash
{commands.get("scheduler_tick")}
{commands.get("candidate_command") or "# no candidate command"}
{commands.get("blocker_writeback") or "# no blocker writeback command"}
```

## Boundary

- executor_wrapper: `{boundary.get("executor_wrapper")}`
- requires_explicit_execute_flag: `{boundary.get("requires_explicit_execute_flag")}`
- requires_fresh_quota_guard_confirmation: `{boundary.get("requires_fresh_quota_guard_confirmation")}`
- candidate_prefix_required: `{boundary.get("candidate_prefix_required")}`
- runtime_idle_detector_required_for_visible_candidate: `{boundary.get("runtime_idle_detector_required_for_visible_candidate")}`
- runs_external_candidate: `{boundary.get("runs_external_candidate")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- candidate_output_captured: `{boundary.get("candidate_output_captured")}`
- blocker_output_captured: `{boundary.get("blocker_output_captured")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`

## Warnings

{warning_lines}
"""



def render_codex_cli_one_message_loop_pilot_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    first_turn = payload.get("first_turn") if isinstance(payload.get("first_turn"), dict) else {}
    bridge = payload.get("automation_bridge") if isinstance(payload.get("automation_bridge"), dict) else {}
    snapshot_required = first_turn.get("snapshot_required") if isinstance(first_turn.get("snapshot_required"), list) else []
    snapshot_lines = "\n".join(f"- {item}" for item in snapshot_required)
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI One-Message Loop Pilot

- start_surface: `{payload.get("start_surface")}`
- pilot_decision: `{payload.get("pilot_decision")}`
- followup_mode: {payload.get("followup_mode")}

## First TUI Turn

- user_action: `{first_turn.get("user_action")}`
- preserve_tui: `{first_turn.get("preserve_tui")}`

The first response should show:

{snapshot_lines}

````text
{first_turn.get("message") or ""}
````

## Automation Bridge

- command: `{bridge.get("command")}`
- default_executes: `{bridge.get("default_executes")}`
- scheduler_action: `{bridge.get("scheduler_action")}`
- executor_reason: `{bridge.get("executor_reason")}`
- followup_mode: {bridge.get("followup_mode")}

## Commands

```bash
{commands.get("bootstrap_message")}
{commands.get("scheduler_exec_dry_run")}
{commands.get("scheduler_exec_candidate_template")}
{commands.get("scheduler_exec_blocker_template")}
```

## Boundary

- pilot_packet_only: `{boundary.get("pilot_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- runs_scheduler_result: `{boundary.get("runs_scheduler_result")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- requires_user_visible_start: `{boundary.get("requires_user_visible_start")}`
- headless_execution_disabled: `{boundary.get("headless_execution_disabled")}`
- candidate_execution_requires_guard_and_prefix: `{boundary.get("candidate_execution_requires_guard_and_prefix")}`

## Warnings

{warning_lines}
"""



def render_codex_cli_visible_local_driver_pilot_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    proof = payload.get("visible_session_proof") if isinstance(payload.get("visible_session_proof"), dict) else {}
    runtime_idle = (
        payload.get("runtime_idle_detector")
        if isinstance(payload.get("runtime_idle_detector"), dict)
        else {}
    )
    idle_guard = payload.get("idle_guard_contract") if isinstance(payload.get("idle_guard_contract"), dict) else {}
    scheduler = payload.get("scheduler_executor") if isinstance(payload.get("scheduler_executor"), dict) else {}
    policy = payload.get("execution_policy") if isinstance(payload.get("execution_policy"), dict) else {}
    steps = payload.get("visible_loop_steps") if isinstance(payload.get("visible_loop_steps"), list) else []
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    fixture_keys = idle_guard.get("fixture_keys") if isinstance(idle_guard.get("fixture_keys"), list) else []
    fixture_key_lines = "\n".join(f"- {key}" for key in fixture_keys)
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Visible Local Driver Pilot

- pilot_phase: `{payload.get("pilot_phase")}`
- start_surface: `{payload.get("start_surface")}`
- loop_decision: `{payload.get("loop_decision")}`
- next_driver_action: `{payload.get("next_driver_action")}`

## Scheduler Executor

- scheduler_action: `{scheduler.get("scheduler_action")}`
- decision: `{scheduler.get("decision")}`
- executor_reason: `{scheduler.get("executor_reason")}`
- executed: `{scheduler.get("executed")}`

## Visible Session Proof

- supplied: `{proof.get("supplied")}`
- approved: `{proof.get("approved")}`
- decision: `{proof.get("decision")}`
- failures: `{proof.get("failures")}`

## Runtime Idle Detector

- supplied: `{runtime_idle.get("supplied")}`
- approved: `{runtime_idle.get("approved")}`
- decision: `{runtime_idle.get("decision")}`
- failures: `{runtime_idle.get("failures")}`

## Idle Guard Contract

- required_before_visible_prompt: `{idle_guard.get("required_before_visible_prompt")}`
- current_pilot_implements_runtime_idle_detection: `{idle_guard.get("current_pilot_implements_runtime_idle_detection")}`
- fixture_backed_runtime_idle_detector: `{idle_guard.get("fixture_backed_runtime_idle_detector")}`
- runtime_sensor_implemented: `{idle_guard.get("runtime_sensor_implemented")}`
- public_safe_fixture_supported: `{idle_guard.get("public_safe_fixture_supported")}`
- local_observation_adapter_supported: `{idle_guard.get("local_observation_adapter_supported")}`
- no_private_state_observation: `{idle_guard.get("no_private_state_observation")}`

{fixture_key_lines}

## Visible Loop Steps

{step_lines}

## Commands

```bash
{commands.get("bootstrap_message")}
{commands.get("scheduler_exec_dry_run")}
{commands.get("scheduler_exec_candidate_template")}
{commands.get("scheduler_exec_blocker_template")}
{commands.get("runtime_idle_detector")}
{commands.get("runtime_idle_detector_fixture")}
```

## Execution Policy

- tui_bootstrap_primary: `{policy.get("tui_bootstrap_primary")}`
- later_turns_visible_to_user: `{policy.get("later_turns_visible_to_user")}`
- user_can_interrupt_or_take_over: `{policy.get("user_can_interrupt_or_take_over")}`
- same_session_attachment_requires_visible_proof: `{policy.get("same_session_attachment_requires_visible_proof")}`
- headless_execution_disabled: `{policy.get("headless_execution_disabled")}`
- quota_guard_required_each_tick: `{policy.get("quota_guard_required_each_tick")}`
- spend_after_validated_writeback_only: `{policy.get("spend_after_validated_writeback_only")}`

## Boundary

- pilot_packet_only: `{boundary.get("pilot_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- runs_scheduler_result: `{boundary.get("runs_scheduler_result")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_stdout_stderr: `{boundary.get("reads_stdout_stderr")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- candidate_execution_requires_guard_and_prefix: `{boundary.get("candidate_execution_requires_guard_and_prefix")}`
- blocker_writeback_requires_guard_checked: `{boundary.get("blocker_writeback_requires_guard_checked")}`
- headless_execution_disabled: `{boundary.get("headless_execution_disabled")}`

## Warnings

{warning_lines}
"""



def render_codex_cli_bounded_visible_pilot_adapter_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    first_response = (
        payload.get("first_response")
        if isinstance(payload.get("first_response"), dict)
        else {}
    )
    runtime_idle = (
        payload.get("runtime_idle_detector")
        if isinstance(payload.get("runtime_idle_detector"), dict)
        else {}
    )
    blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
    blocker_lines = "\n".join(f"- {blocker}" for blocker in blockers) if blockers else "- none"
    checks = first_response.get("checks") if isinstance(first_response.get("checks"), list) else []
    check_lines = "\n".join(
        f"- [{'x' if check.get('passed') else ' '}] {check.get('key')}: {check.get('description')}"
        for check in checks
        if isinstance(check, dict)
    )
    if not check_lines:
        check_lines = "- no first-response fixture supplied"
    required_first_response_shape = payload.get("required_first_response_shape")
    required_runtime_idle_shape = payload.get("required_runtime_idle_shape")
    required_shapes = ""
    if isinstance(required_first_response_shape, dict):
        required_shapes += f"""
## Required First-Response Fixture

```json
{json.dumps(required_first_response_shape, indent=2, ensure_ascii=False)}
```
"""
    if isinstance(required_runtime_idle_shape, dict):
        required_shapes += f"""
## Required Runtime Idle Fixture

```json
{json.dumps(required_runtime_idle_shape, indent=2, ensure_ascii=False)}
```
"""
    return f"""# Codex CLI Bounded Visible Pilot Adapter

- decision: `{payload.get("decision")}`
- approved_for_live_tui_success_claim: `{payload.get("approved_for_live_tui_success_claim")}`
- observed_surface: `{payload.get("observed_surface")}`
- next_safe_step: {payload.get("next_safe_step")}

## First Response

- supplied: `{first_response.get("supplied")}`
- approved: `{first_response.get("approved")}`

{check_lines}

## Runtime Idle Detector

- supplied: `{runtime_idle.get("supplied")}`
- approved: `{runtime_idle.get("approved")}`
- decision: `{runtime_idle.get("decision")}`
- failures: `{runtime_idle.get("failures")}`

## Blockers

{blocker_lines}

## Commands

```bash
{commands.get("bootstrap_message")}
{commands.get("bounded_visible_pilot_adapter")}
{commands.get("runtime_idle_detector")}
{commands.get("blocker_writeback")}
{commands.get("success_writeback")}
```

## Boundary

- adapter_packet_only: `{boundary.get("adapter_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_stdout_stderr: `{boundary.get("reads_stdout_stderr")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- requires_visible_delivery: `{boundary.get("requires_visible_delivery")}`
- argv_prompt_rejected: `{boundary.get("argv_prompt_rejected")}`
- success_claim_requires_first_response_and_idle: `{boundary.get("success_claim_requires_first_response_and_idle")}`
{required_shapes}
"""



def render_codex_cli_visible_first_response_capture_plan_markdown(
    payload: dict[str, Any],
) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    artifacts = (
        payload.get("output_artifacts")
        if isinstance(payload.get("output_artifacts"), dict)
        else {}
    )
    steps = payload.get("capture_steps") if isinstance(payload.get("capture_steps"), list) else []
    stops = payload.get("stop_conditions") if isinstance(payload.get("stop_conditions"), list) else []
    first_response_fixture = payload.get("sample_first_response_fixture")
    runtime_idle_fixture = payload.get("sample_runtime_idle_fixture")
    step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    stop_lines = "\n".join(f"- {stop}" for stop in stops) if stops else "- none"
    return f"""# Codex CLI Visible First-Response Capture Plan

- decision: `{payload.get("decision")}`
- start_surface: `{payload.get("start_surface")}`
- first_response_fixture: `{artifacts.get("first_response_fixture")}`
- runtime_idle_fixture: `{artifacts.get("runtime_idle_fixture")}`
- next_safe_step: {payload.get("next_safe_step")}

## Commands

```bash
{commands.get("quota_guard")}
{commands.get("bootstrap_message")}
{commands.get("bounded_visible_pilot_adapter")}
{commands.get("runtime_idle_detector")}
```

## Capture Steps

{step_lines}

## Stop Conditions

{stop_lines}

## Sample First-Response Fixture

```json
{json.dumps(first_response_fixture, indent=2, ensure_ascii=False)}
```

## Sample Runtime Idle Fixture

```json
{json.dumps(runtime_idle_fixture, indent=2, ensure_ascii=False)}
```

## Boundary

- capture_plan_only: `{boundary.get("capture_plan_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_stdout_stderr: `{boundary.get("reads_stdout_stderr")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- manual_paste_primary: `{boundary.get("manual_paste_primary")}`
- argv_prompt_rejected: `{boundary.get("argv_prompt_rejected")}`
- success_claim_requires_bounded_adapter: `{boundary.get("success_claim_requires_bounded_adapter")}`
"""



def render_codex_cli_runtime_idle_detector_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    failures = payload.get("failures") if isinstance(payload.get("failures"), list) else []
    required_shape = payload.get("required_fixture_shape")
    check_lines = "\n".join(
        f"- [{'x' if check.get('passed') else ' '}] {check.get('key')}: {check.get('description')}"
        for check in checks
        if isinstance(check, dict)
    )
    if not check_lines:
        check_lines = "- no runtime idle evidence supplied"
    failure_lines = "\n".join(f"- {failure}" for failure in failures) if failures else "- none"
    required_shape_block = ""
    if isinstance(required_shape, dict):
        required_shape_block = f"""
## Required Evidence Shape

```json
{json.dumps(required_shape, indent=2, ensure_ascii=False)}
```
"""
    return f"""# Codex CLI Runtime Idle Detector

- decision: `{payload.get("decision")}`
- approved_for_visible_later_turn: `{payload.get("approved_for_visible_later_turn")}`
- source: `{payload.get("source")}`
- observed_surface: `{payload.get("observed_surface")}`
- recommended_action: {payload.get("recommended_action")}

## Checks

{check_lines}

## Failures

{failure_lines}

## Boundary

- fixture_only: `{boundary.get("fixture_only")}`
- public_safe_fixture_supported: `{boundary.get("public_safe_fixture_supported")}`
- local_observation_adapter_supported: `{boundary.get("local_observation_adapter_supported")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_stdout_stderr: `{boundary.get("reads_stdout_stderr")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
{required_shape_block}
"""



def render_codex_cli_visible_session_proof_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    failures = payload.get("failures") if isinstance(payload.get("failures"), list) else []
    required_shape = payload.get("required_fixture_shape")
    check_lines = "\n".join(
        f"- [{'x' if check.get('passed') else ' '}] {check.get('key')}: {check.get('description')}"
        for check in checks
        if isinstance(check, dict)
    )
    if not check_lines:
        check_lines = "- no proof fixture supplied"
    failure_lines = "\n".join(f"- {failure}" for failure in failures) if failures else "- none"
    required_shape_block = ""
    if isinstance(required_shape, dict):
        required_shape_block = f"""
## Required Fixture Shape

```json
{json.dumps(required_shape, indent=2, ensure_ascii=False)}
```
"""
    return f"""# Codex CLI Visible Session Proof

- decision: `{payload.get("decision")}`
- approved_for_same_session_automation: `{payload.get("approved_for_same_session_automation")}`
- observed_surface: `{payload.get("observed_surface")}`
- recommended_action: {payload.get("recommended_action")}

## Checks

{check_lines}

## Failures

{failure_lines}

## Boundary

- fixture_only: `{boundary.get("fixture_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
{required_shape_block}
"""



def render_codex_cli_visible_attach_acceptance_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    proof = (
        payload.get("visible_session_proof")
        if isinstance(payload.get("visible_session_proof"), dict)
        else {}
    )
    runtime_idle = (
        payload.get("runtime_idle_detector")
        if isinstance(payload.get("runtime_idle_detector"), dict)
        else {}
    )
    blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
    blocker_lines = "\n".join(f"- {blocker}" for blocker in blockers) if blockers else "- none"
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Visible Attach Acceptance

- decision: `{payload.get("decision")}`
- accepted_for_same_tui_automation: `{payload.get("accepted_for_same_tui_automation")}`
- accepted_for_visible_later_turn: `{payload.get("accepted_for_visible_later_turn")}`
- observed_surface: `{payload.get("observed_surface")}`
- driver_mode: `{payload.get("driver_mode")}`
- next_safe_step: {payload.get("next_safe_step")}

## Proof And Idle

- proof_supplied: `{proof.get("supplied")}`
- proof_approved: `{proof.get("approved")}`
- proof_decision: `{proof.get("decision")}`
- idle_supplied: `{runtime_idle.get("supplied")}`
- idle_approved: `{runtime_idle.get("approved")}`
- idle_decision: `{runtime_idle.get("decision")}`

## Blockers

{blocker_lines}

## Commands

```bash
{commands.get("session_probe")}
{commands.get("visible_attach_acceptance")}
{commands.get("visible_session_proof")}
{commands.get("runtime_idle_detector_fixture")}
{commands.get("tui_bootstrap_message")}
```

## Boundary

- acceptance_packet_only: `{boundary.get("acceptance_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_stdout_stderr: `{boundary.get("reads_stdout_stderr")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`

## Warnings

{warning_lines}
"""
