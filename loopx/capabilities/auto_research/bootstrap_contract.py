from __future__ import annotations

import shlex


AUTO_RESEARCH_LIVE_WORKER_PROOF_SCHEMA_VERSION = "auto_research_visible_worker_proof_v0"


def auto_research_contract_command_text(*, cli_bin: str, objective: str) -> str:
    return f"{shlex.quote(cli_bin)} auto-research {shlex.quote(str(objective).strip())}"


def auto_research_start_command_text(
    *,
    cli_bin: str,
    objective: str,
    preset_id: str | None = None,
    execute: bool = False,
    headless: bool = False,
    no_attach: bool = False,
    wake_visible_after_launch: bool = False,
    output_language: str = "en",
) -> str:
    parts = [
        shlex.quote(cli_bin),
        "auto-research",
        "start",
        shlex.quote(str(objective).strip()),
    ]
    if preset_id:
        parts.extend(["--preset", shlex.quote(str(preset_id).strip())])
    if output_language and output_language != "en":
        parts.extend(["--language", shlex.quote(output_language)])
    if execute:
        parts.append("--execute")
    if headless:
        parts.append("--headless")
    if no_attach:
        parts.append("--no-attach")
    if wake_visible_after_launch:
        parts.append("--wake-visible-after-launch")
    return " ".join(parts)


def build_auto_research_contract_acceptance(
    user_contract: dict[str, object],
) -> dict[str, object]:
    command = (
        user_contract.get("command_contract")
        if isinstance(user_contract.get("command_contract"), dict)
        else {}
    )
    required_outputs = (
        command.get("auto_research_required_outputs")
        if isinstance(command.get("auto_research_required_outputs"), list)
        else []
    )
    output_field_map = {
        "research_brief": "research_brief",
        "action_plan": "action_plan",
        "evidence_refs": "evidence_refs",
        "next_executable_step": "next_executable_step",
        "gate": "gate",
    }
    present_outputs = [
        output
        for output in required_outputs
        if user_contract.get(output_field_map.get(str(output), "")) is not None
    ]
    action_plan = user_contract.get("action_plan")
    gate = user_contract.get("gate") if isinstance(user_contract.get("gate"), dict) else {}
    next_step = (
        user_contract.get("next_executable_step")
        if isinstance(user_contract.get("next_executable_step"), dict)
        else {}
    )
    one_click_start = (
        user_contract.get("one_click_start")
        if isinstance(user_contract.get("one_click_start"), dict)
        else {}
    )
    preset_context = (
        user_contract.get("preset_context")
        if isinstance(user_contract.get("preset_context"), dict)
        else {}
    )
    preset_id = str(preset_context.get("preset_id") or "").strip()
    expected_start_template = (
        f'loopx auto-research start "<open question>" --preset {preset_id} --execute'
        if preset_id
        else 'loopx auto-research start "<open question>" --execute'
    )
    checks = {
        "one_question_input": user_contract.get("open_question") not in (None, ""),
        "required_outputs_present": len(present_outputs) == len(required_outputs),
        "action_plan_bounded": isinstance(action_plan, list) and 0 < len(action_plan) <= 5,
        "next_step_automatic_by_default": next_step.get("can_run_automatically") is True,
        "gate_present": bool(gate.get("user_judgment_needed")),
        "canonical_invocation_short": (
            command.get("canonical_invocation") == 'loopx auto-research "<open question>"'
        ),
        "one_click_start_present": (
            one_click_start.get("command_template") == expected_start_template
        ),
        "one_click_start_uses_generic_kernel": (
            one_click_start.get("uses_generic_kernel") is True
            and one_click_start.get("coordination_model") == "decentralized_state_a2a"
        ),
    }
    accepted = all(checks.values())
    return {
        "schema_version": "auto_research_user_contract_acceptance_v0",
        "accepted": accepted,
        "canonical_invocation": command.get("canonical_invocation"),
        "required_outputs": required_outputs,
        "present_outputs": present_outputs,
        "checks": checks,
        "missing_outputs": [
            output for output in required_outputs if output not in present_outputs
        ],
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
        },
    }


def build_auto_research_live_worker_proof(*, launch_visible: bool) -> dict[str, object]:
    return {
        "schema_version": AUTO_RESEARCH_LIVE_WORKER_PROOF_SCHEMA_VERSION,
        "lane_authored_evidence_loaded": False,
        "pane_local_a2a_rounds_loaded": False,
        "pane_local_a2a_round_count": 0,
        "decentralized_a2a_rounds_verified": False,
        "cadence_wake_loaded": False,
        "cadence_wake_verified": False,
        "visible_lanes_launched": bool(launch_visible),
        "visible_lanes_accepted": False,
        "evidence_source": "not_loaded",
        "reason": (
            "start and demo-e2e share one kernel live-bootstrap contract for visible "
            "Codex worker panes; presentation-specific reporting stays outside the "
            "auto-research preset."
        ),
        "next_step": [
            "let each visible pane run its LoopX frontier tick",
            "append public-safe lane evidence into LoopX state",
            "load compact evidence from the pane artifact directory",
        ],
        "owner_layer": "generic_multi_agent_kernel",
        "user_facing_by_default": False,
    }
