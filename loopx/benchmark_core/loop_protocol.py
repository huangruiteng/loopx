from __future__ import annotations

from dataclasses import dataclass
from typing import Any


BENCHMARK_LOOP_PROTOCOL_SCHEMA_VERSION = "benchmark_loop_protocol_v0"
BENCHMARK_LOOP_CONTROLLER_TRACE_SCHEMA_VERSION = (
    "benchmark_loop_controller_trace_v0"
)
BENCHMARK_PRODUCT_MODE_COMPARISON_SCHEMA_VERSION = (
    "benchmark_product_mode_comparison_v0"
)
MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID = "max5_blind_loop_no_feedback"
PRODUCT_MODE_MAX5_NO_FEEDBACK_PROTOCOL_ID = "product_mode_max5_no_feedback"
PACKET_ONLY_OBSERVATION_PROTOCOL_ID = "packet_only_observation"

BLIND_LOOP_DEFAULT_MAX_ROUNDS = 5
CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE = "codex-acp-blind-loop-baseline"
LOOPX_BLIND_LOOP_TREATMENT_ROUTE = "loopx-blind-loop-treatment"
LOOPX_PROMPT_POLLING_TEST_ROUTE = "loopx-prompt-polling-test"
AUTOMATION_LOOP_TREATMENT_ROUTE = "automation-loop-treatment"
RAW_CODEX_AUTONOMOUS_MAX5_ROUTE = "raw-codex-autonomous-max5"
LOOPX_PRODUCT_MODE_ROUTE = "loopx-product-mode"
CODEX_APP_SERVER_GOAL_BASELINE_ROUTE = "codex-app-server-goal-baseline"
LOOPX_PACKET_ONLY_OBSERVATION_ROUTE = (
    "loopx-packet-only-observation"
)

BLIND_LOOP_ROUTES = frozenset(
    {
        CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
        LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
        LOOPX_PROMPT_POLLING_TEST_ROUTE,
    }
)
NO_REWARD_FEEDBACK_ROUTES = frozenset(
    {
        CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
        LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
        LOOPX_PROMPT_POLLING_TEST_ROUTE,
        RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
        LOOPX_PRODUCT_MODE_ROUTE,
        CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
    }
)
PRODUCT_MODE_ROUTES = frozenset(
    {
        RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
        LOOPX_PRODUCT_MODE_ROUTE,
    }
)


@dataclass(frozen=True)
class BenchmarkLoopContract:
    route: str
    protocol_id: str
    max_rounds_budget: int
    official_feedback_forwarded: bool
    official_feedback_blinded: bool
    blind_loop: bool
    product_mode: bool
    strict_treatment_claim_allowed: bool
    claim_blocker: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BENCHMARK_LOOP_PROTOCOL_SCHEMA_VERSION,
            "route": self.route,
            "protocol_id": self.protocol_id,
            "max_rounds_budget": self.max_rounds_budget,
            "official_feedback_forwarded": self.official_feedback_forwarded,
            "official_feedback_blinded": self.official_feedback_blinded,
            "blind_loop": self.blind_loop,
            "product_mode": self.product_mode,
            "strict_treatment_claim_allowed": self.strict_treatment_claim_allowed,
            "claim_blocker": self.claim_blocker,
        }


def build_benchmark_loop_contract(
    *,
    route: str,
    max_rounds: int | None = BLIND_LOOP_DEFAULT_MAX_ROUNDS,
    protocol_id: str | None = None,
) -> dict[str, Any]:
    budget = (
        max_rounds
        if isinstance(max_rounds, int) and not isinstance(max_rounds, bool) and max_rounds > 0
        else BLIND_LOOP_DEFAULT_MAX_ROUNDS
    )
    feedback_forwarded = route == AUTOMATION_LOOP_TREATMENT_ROUTE
    blind_loop = route in BLIND_LOOP_ROUTES
    product_mode = route in PRODUCT_MODE_ROUTES
    resolved_protocol = protocol_id or (
        MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID
        if blind_loop and not feedback_forwarded and budget == BLIND_LOOP_DEFAULT_MAX_ROUNDS
        else PRODUCT_MODE_MAX5_NO_FEEDBACK_PROTOCOL_ID
        if product_mode and not feedback_forwarded and budget == BLIND_LOOP_DEFAULT_MAX_ROUNDS
        else PACKET_ONLY_OBSERVATION_PROTOCOL_ID
        if route == LOOPX_PACKET_ONLY_OBSERVATION_ROUTE
        else "custom_or_legacy_loop"
    )
    claim_blocker = ""
    strict_allowed = bool(
        route
        in {
            LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
            LOOPX_PROMPT_POLLING_TEST_ROUTE,
        }
        and resolved_protocol == MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID
        and blind_loop
        and budget == BLIND_LOOP_DEFAULT_MAX_ROUNDS
        and not feedback_forwarded
    )
    if route == LOOPX_PACKET_ONLY_OBSERVATION_ROUTE:
        claim_blocker = "packet_only_no_max5_controller"
    elif route in {
        LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
        LOOPX_PROMPT_POLLING_TEST_ROUTE,
    } and not strict_allowed:
        claim_blocker = "not_strict_max5_no_feedback_treatment"

    return BenchmarkLoopContract(
        route=route,
        protocol_id=resolved_protocol,
        max_rounds_budget=budget,
        official_feedback_forwarded=feedback_forwarded,
        official_feedback_blinded=not feedback_forwarded,
        blind_loop=blind_loop,
        product_mode=product_mode,
        strict_treatment_claim_allowed=strict_allowed,
        claim_blocker=claim_blocker,
    ).as_dict()


def build_product_mode_main_table_comparison_contract(
    *,
    benchmark_id: str = "skillsbench@1.1",
    max_rounds: int | None = BLIND_LOOP_DEFAULT_MAX_ROUNDS,
    baseline_route: str = RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
    treatment_route: str = LOOPX_PRODUCT_MODE_ROUTE,
) -> dict[str, Any]:
    budget = (
        max_rounds
        if isinstance(max_rounds, int)
        and not isinstance(max_rounds, bool)
        and max_rounds > 0
        else BLIND_LOOP_DEFAULT_MAX_ROUNDS
    )
    baseline_contract = build_benchmark_loop_contract(
        route=baseline_route,
        max_rounds=budget,
        protocol_id=PRODUCT_MODE_MAX5_NO_FEEDBACK_PROTOCOL_ID
        if baseline_route == RAW_CODEX_AUTONOMOUS_MAX5_ROUTE
        else None,
    )
    treatment_contract = build_benchmark_loop_contract(
        route=treatment_route,
        max_rounds=budget,
        protocol_id=PRODUCT_MODE_MAX5_NO_FEEDBACK_PROTOCOL_ID
        if treatment_route == LOOPX_PRODUCT_MODE_ROUTE
        else None,
    )
    return {
        "schema_version": BENCHMARK_PRODUCT_MODE_COMPARISON_SCHEMA_VERSION,
        "comparison_id": "skillsbench_product_mode_main_table_v0",
        "benchmark_id": benchmark_id,
        "protocol_id": PRODUCT_MODE_MAX5_NO_FEEDBACK_PROTOCOL_ID,
        "max_rounds_budget": budget,
        "baseline_arm": {
            "route": baseline_route,
            "arm_id": "raw_codex_autonomous_max5",
            "contract": baseline_contract,
            "loopx_state_todo_replan_cli_required": False,
            "loopx_cli_allowed": False,
            "agent_surface": "raw_codex_autonomous",
        },
        "treatment_arm": {
            "route": treatment_route,
            "arm_id": "loopx_product_mode",
            "contract": treatment_contract,
            "loopx_state_todo_replan_cli_required": True,
            "case_local_loopx_state_required": True,
            "loopx_cli_required": True,
            "agent_surface": "loopx_state_todo_replan_cli",
        },
        "policy_gate": {
            "same_benchmark_and_case_required": True,
            "official_feedback_forwarded_to_agent": False,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
            "stop_on_reward_one": True,
            "stop_on_agent_declared_done_no_remaining_goals": True,
            "stop_on_max_rounds_budget": True,
            "headline_metrics": [
                "best_score",
                "final_score",
                "first_success_round",
                "declared_done_score",
            ],
            "main_table_claim_requires": [
                "paired_baseline_and_treatment_same_case",
                "raw_codex_autonomous_max5_baseline",
                "loopx_state_todo_replan_cli_treatment",
                "no_official_feedback_to_either_agent",
                "compact_round_reward_trace_or_equivalent_metrics",
            ],
        },
        "boundary": {
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
            "raw_logs_recorded": False,
            "local_paths_recorded": False,
        },
    }


def _compact_run_text(value: Any) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ""
    return str(value).strip()[:200]


def _run_route_tokens(run: dict[str, Any]) -> set[str]:
    contract = run.get("benchmark_loop_contract")
    if not isinstance(contract, dict):
        contract = {}
    values = {
        contract.get("route"),
        run.get("route"),
        run.get("mode"),
        run.get("arm_id"),
    }
    tokens = {_compact_run_text(value) for value in values}
    return {token for token in tokens if token}


def _route_matches(run: dict[str, Any], *needles: str) -> bool:
    tokens = _run_route_tokens(run)
    lower_tokens = {token.lower() for token in tokens}
    for needle in needles:
        lower_needle = needle.lower()
        if lower_needle in lower_tokens:
            return True
        if any(lower_needle in token for token in lower_tokens):
            return True
    return False


def _run_case_id(run: dict[str, Any]) -> str:
    case_id = _compact_run_text(run.get("case_id"))
    if case_id:
        return case_id
    case_ids = run.get("case_ids")
    if isinstance(case_ids, list):
        for item in case_ids:
            case_id = _compact_run_text(item)
            if case_id:
                return case_id
    return ""


def _run_benchmark_id(run: dict[str, Any]) -> str:
    return _compact_run_text(run.get("benchmark_id"))


def _run_max_rounds_budget(run: dict[str, Any]) -> int | None:
    contract = run.get("benchmark_loop_contract")
    if not isinstance(contract, dict):
        contract = {}
    for value in (contract.get("max_rounds_budget"), run.get("max_rounds_budget")):
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    round_trace = run.get("round_reward_trace")
    if isinstance(round_trace, dict):
        value = round_trace.get("max_rounds_budget")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    return None


def _run_feedback_blinded(run: dict[str, Any]) -> bool:
    if run.get("official_feedback_blinded") is True:
        return True
    round_trace = run.get("round_reward_trace")
    if isinstance(round_trace, dict):
        return round_trace.get("official_feedback_blinded") is True
    contract = run.get("benchmark_loop_contract")
    if isinstance(contract, dict):
        return contract.get("official_feedback_blinded") is True
    return False


def _run_reward_feedback_forwarded(run: dict[str, Any]) -> bool | None:
    if isinstance(run.get("reward_feedback_forwarded"), bool):
        return run["reward_feedback_forwarded"]
    round_trace = run.get("round_reward_trace")
    if isinstance(round_trace, dict) and isinstance(
        round_trace.get("reward_feedback_forwarded"), bool
    ):
        return round_trace["reward_feedback_forwarded"]
    contract = run.get("benchmark_loop_contract")
    if isinstance(contract, dict) and isinstance(
        contract.get("official_feedback_forwarded"), bool
    ):
        return contract["official_feedback_forwarded"]
    return None


def _run_has_headline_metrics(run: dict[str, Any]) -> bool:
    for key in ("best_round_reward", "final_round_reward"):
        if isinstance(run.get(key), (int, float)) and not isinstance(
            run.get(key), bool
        ):
            return True
    rewards = run.get("round_rewards")
    if isinstance(rewards, list) and rewards:
        return True
    round_trace = run.get("round_reward_trace")
    if isinstance(round_trace, dict):
        records = round_trace.get("records")
        return isinstance(records, list) and bool(records)
    return False


def _loopx_product_lifecycle_observed(run: dict[str, Any]) -> bool:
    if run.get("loopx_prompt_driven_lifecycle_observed") is True:
        return True
    for key in (
        "worker_loopx_cli_call_total",
        "loopx_cli_command_count",
        "loopx_prompt_driven_command_count",
    ):
        value = run.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return True
    counters = run.get("solution_phase_counters")
    if isinstance(counters, dict):
        value = counters.get("loopx_cli_command_count")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return True
    trace = run.get("loopx_prompt_driven_trace")
    if isinstance(trace, dict):
        return trace.get("lifecycle_observed") is True
    return False


def classify_product_mode_main_table_pair(
    *,
    baseline_run: dict[str, Any],
    treatment_run: dict[str, Any],
    benchmark_id: str = "skillsbench@1.1",
    max_rounds: int = BLIND_LOOP_DEFAULT_MAX_ROUNDS,
) -> dict[str, Any]:
    """Classify whether two compact runs satisfy the main-table pair contract."""

    contract = build_product_mode_main_table_comparison_contract(
        benchmark_id=benchmark_id,
        max_rounds=max_rounds,
    )
    blockers: list[str] = []
    baseline_case = _run_case_id(baseline_run)
    treatment_case = _run_case_id(treatment_run)
    if not baseline_case or not treatment_case or baseline_case != treatment_case:
        blockers.append("case_id_mismatch_or_missing")
    baseline_benchmark = _run_benchmark_id(baseline_run) or benchmark_id
    treatment_benchmark = _run_benchmark_id(treatment_run) or benchmark_id
    if baseline_benchmark != treatment_benchmark:
        blockers.append("benchmark_id_mismatch")
    if baseline_benchmark != benchmark_id:
        blockers.append("unexpected_benchmark_id")
    if not _route_matches(
        baseline_run,
        RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
        "raw_codex_autonomous_max5",
        "skillsbench_raw_codex_autonomous_max5",
    ):
        blockers.append("baseline_not_raw_codex_autonomous_max5")
    if not _route_matches(
        treatment_run,
        LOOPX_PRODUCT_MODE_ROUTE,
        "loopx_product_mode",
        "skillsbench_loopx_product_mode",
    ):
        blockers.append("treatment_not_loopx_product_mode")
    for label, run in (("baseline", baseline_run), ("treatment", treatment_run)):
        observed_budget = _run_max_rounds_budget(run)
        if observed_budget is not None and observed_budget != max_rounds:
            blockers.append(f"{label}_max_rounds_not_{max_rounds}")
        if not _run_feedback_blinded(run):
            blockers.append(f"{label}_official_feedback_not_blinded")
        if _run_reward_feedback_forwarded(run) is not False:
            blockers.append(f"{label}_reward_feedback_forwarding_not_disabled")
        if not _run_has_headline_metrics(run):
            blockers.append(f"{label}_compact_metrics_missing")
    if treatment_run.get("loopx_inside_case") is not True:
        blockers.append("treatment_loopx_inside_case_not_confirmed")
    if not _loopx_product_lifecycle_observed(treatment_run):
        blockers.append("treatment_loopx_lifecycle_not_observed")

    allowed = not blockers
    return {
        "schema_version": BENCHMARK_PRODUCT_MODE_COMPARISON_SCHEMA_VERSION,
        "comparison_id": contract["comparison_id"],
        "main_table_claim_allowed": allowed,
        "product_mode_pair_complete": allowed,
        "claim_blocker": "none" if allowed else ",".join(blockers),
        "benchmark_id": baseline_benchmark,
        "case_id": baseline_case or treatment_case,
        "baseline_route_valid": "baseline_not_raw_codex_autonomous_max5"
        not in blockers,
        "treatment_route_valid": "treatment_not_loopx_product_mode" not in blockers,
        "treatment_loopx_lifecycle_observed": _loopx_product_lifecycle_observed(
            treatment_run
        ),
        "official_feedback_blinded": (
            _run_feedback_blinded(baseline_run)
            and _run_feedback_blinded(treatment_run)
        ),
        "headline_metrics": contract["policy_gate"]["headline_metrics"],
        "contract": contract,
    }


def build_benchmark_loop_controller_trace(
    *,
    route: str,
    max_rounds: int | None = BLIND_LOOP_DEFAULT_MAX_ROUNDS,
    schema_version: str = BENCHMARK_LOOP_CONTROLLER_TRACE_SCHEMA_VERSION,
) -> dict[str, Any]:
    contract = build_benchmark_loop_contract(route=route, max_rounds=max_rounds)
    return {
        "schema_version": schema_version,
        "loop_contract_schema_version": BENCHMARK_LOOP_PROTOCOL_SCHEMA_VERSION,
        "loop_protocol_id": contract["protocol_id"],
        "route": route,
        "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
        "heartbeat_count": 0,
        "controller_action_decisions": 0,
        "initial_prompt_count": 0,
        "followup_prompt_count": 0,
        "stop_decision_count": 0,
        "reward_observation_count": 0,
        "verifier_feedback_observation_count": 0,
        "round_rewards": [],
        "official_success_observed": False,
        "official_success_observation_count": 0,
        "first_success_round": None,
        "official_feedback_forwarded": contract["official_feedback_forwarded"],
        "official_feedback_blinded_count": 0,
        "blind_loop": contract["blind_loop"],
        "product_mode": contract["product_mode"],
        "max_rounds_budget": contract["max_rounds_budget"],
        "max_round_observed": -1,
        "last_decision": "not_started",
        "raw_task_text_recorded": False,
        "raw_verifier_output_recorded": False,
        "raw_agent_trajectory_recorded": False,
    }


def build_blind_loop_initial_prompt(
    *,
    route: str,
    instruction: str,
    treatment_prompt_style: str = "structured",
    benchmark_surface: str = "official benchmark sandbox",
) -> str:
    treatment = route in {
        LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
        LOOPX_PROMPT_POLLING_TEST_ROUTE,
    }
    if treatment and treatment_prompt_style == "baseline-safe":
        prefix = "Codex blind-loop baseline-compatible round 1. "
        control_clause = "Use ordinary Codex CLI behavior without goal mode. "
    else:
        prefix = (
            "Structured prompt-polling test round 1. "
            if route == LOOPX_PROMPT_POLLING_TEST_ROUTE
            else "Structured blind-loop treatment round 1. "
            if route == LOOPX_BLIND_LOOP_TREATMENT_ROUTE
            else "Codex blind-loop baseline round 1. "
        )
        control_clause = (
            "Use a disciplined execution style: keep the scope narrow, "
            "track your own plan, inspect evidence before editing, and "
            "validate locally before finishing. "
            if treatment
            else "Use ordinary Codex CLI behavior without goal mode. "
        )
    return (
        prefix
        + f"You are running inside the {benchmark_surface}. "
        + control_clause
        + "Do not invoke /goal mode, external LoopX CLI, upload, "
        "submit, or ask the human for routine execution choices. "
        "No official reward, pass/fail status, verifier error, or "
        "verifier output will be provided during this loop.\n\n"
        "--- TASK INSTRUCTION ---\n"
        f"{instruction}"
    )


def build_blind_loop_continuation_prompt(
    *,
    scheduled_round: int,
    max_rounds: int,
    persistent_constraint_clause: str = "",
) -> str:
    return (
        f"Scheduled blind-loop continuation round {scheduled_round} of "
        f"{max_rounds}. This continuation is part of the pre-set loop "
        "budget and is not evidence that the official verifier passed "
        "or failed. You are not being shown official reward, pass/fail "
        "status, verifier error, or verifier output."
        f"{persistent_constraint_clause} Continue from the "
        "same workspace using only the task instruction, your own edits, "
        "and local validation signals. Keep scope narrow, reinspect for "
        "mistakes, make the smallest safe correction if needed, and "
        "otherwise keep the solution stable."
    )


def render_loop_contract_packet_lines(contract: dict[str, Any]) -> list[str]:
    fields = (
        "protocol_id",
        "route",
        "max_rounds_budget",
        "official_feedback_forwarded",
        "official_feedback_blinded",
        "blind_loop",
        "product_mode",
        "strict_treatment_claim_allowed",
        "claim_blocker",
    )
    lines = ["benchmark_loop_contract:"]
    for field in fields:
        value = contract.get(field)
        if value == "":
            continue
        lines.append(f"  {field}: {str(value).lower() if isinstance(value, bool) else value}")
    return lines


def classify_loopx_treatment_claim(run: dict[str, Any]) -> dict[str, Any]:
    """Classify whether a compact run is strict treatment evidence.

    This is intentionally conservative. A LoopX access packet alone is a
    route-safety observation; the original treatment claim requires a public-safe
    controller trace for the max-5 no-feedback loop.
    """

    contract = run.get("benchmark_loop_contract")
    if not isinstance(contract, dict):
        contract = {}
    protocol_id = str(contract.get("protocol_id") or "")
    max_rounds = contract.get("max_rounds_budget") or run.get("max_rounds_budget")
    feedback_forwarded = contract.get("official_feedback_forwarded")
    blind_loop = contract.get("blind_loop")
    route = str(contract.get("route") or run.get("route") or run.get("mode") or "")
    round_count = run.get("round_reward_count")
    if not isinstance(round_count, int) or isinstance(round_count, bool):
        rewards = run.get("round_rewards")
        round_count = len(rewards) if isinstance(rewards, list) else 0
    controller_trace_present = bool(
        run.get("loopx_controller_trace_present")
        or run.get("controller_trace_present")
        or round_count > 0
    )
    prompt_driven_required = bool(
        run.get("loopx_prompt_driven_loop_required")
    ) or str(run.get("loopx_product_path_primary_route") or "") == (
        "prompt_driven_case_local_loopx_cli"
    )
    prompt_driven_lifecycle_observed = bool(
        run.get("loopx_prompt_driven_lifecycle_observed")
    )

    blockers: list[str] = []
    if protocol_id != MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID:
        blockers.append("missing_max5_blind_loop_protocol")
    if max_rounds != BLIND_LOOP_DEFAULT_MAX_ROUNDS:
        blockers.append("max_rounds_not_5")
    if feedback_forwarded is not False:
        blockers.append("official_feedback_not_confirmed_blinded")
    if blind_loop is not True:
        blockers.append("blind_loop_not_confirmed")
    if not controller_trace_present:
        blockers.append("controller_trace_absent")
    if prompt_driven_required and not prompt_driven_lifecycle_observed:
        blockers.append("prompt_driven_loopx_lifecycle_absent")
    if route not in {
        LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
        LOOPX_PROMPT_POLLING_TEST_ROUTE,
        "skillsbench_loopx_blind_loop_treatment",
        "skillsbench_loopx_prompt_polling_test",
        "loopx_prompt_polling_test",
    }:
        blockers.append("route_not_prompt_polling_test")

    allowed = not blockers
    return {
        "schema_version": "loopx_treatment_claim_classification_v0",
        "strict_loopx_treatment_claim_allowed": allowed,
        "loopx_treatment_evidence_tier": (
            "strict_max5_prompt_polling_test" if allowed else "packet_or_incomplete"
        ),
        "loopx_treatment_claim_blocker": (
            "none" if allowed else ",".join(blockers)
        ),
        "controller_trace_present": controller_trace_present,
        "round_reward_count": round_count,
    }
