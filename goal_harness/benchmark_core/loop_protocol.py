from __future__ import annotations

from dataclasses import dataclass
from typing import Any


BENCHMARK_LOOP_PROTOCOL_SCHEMA_VERSION = "benchmark_loop_protocol_v0"
BENCHMARK_LOOP_CONTROLLER_TRACE_SCHEMA_VERSION = (
    "benchmark_loop_controller_trace_v0"
)
MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID = "max5_blind_loop_no_feedback"
PACKET_ONLY_OBSERVATION_PROTOCOL_ID = "packet_only_observation"

BLIND_LOOP_DEFAULT_MAX_ROUNDS = 5
CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE = "codex-acp-blind-loop-baseline"
GOAL_HARNESS_BLIND_LOOP_TREATMENT_ROUTE = "goal-harness-blind-loop-treatment"
GOAL_HARNESS_PROMPT_POLLING_TEST_ROUTE = "goal-harness-prompt-polling-test"
AUTOMATION_LOOP_TREATMENT_ROUTE = "automation-loop-treatment"
RAW_CODEX_AUTONOMOUS_MAX5_ROUTE = "raw-codex-autonomous-max5"
GOAL_HARNESS_PRODUCT_MODE_ROUTE = "goal-harness-product-mode"
CODEX_APP_SERVER_GOAL_BASELINE_ROUTE = "codex-app-server-goal-baseline"
GOAL_HARNESS_PACKET_ONLY_OBSERVATION_ROUTE = (
    "goal-harness-packet-only-observation"
)

BLIND_LOOP_ROUTES = frozenset(
    {
        CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
        GOAL_HARNESS_BLIND_LOOP_TREATMENT_ROUTE,
        GOAL_HARNESS_PROMPT_POLLING_TEST_ROUTE,
    }
)
NO_REWARD_FEEDBACK_ROUTES = frozenset(
    {
        CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
        GOAL_HARNESS_BLIND_LOOP_TREATMENT_ROUTE,
        GOAL_HARNESS_PROMPT_POLLING_TEST_ROUTE,
        RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
        GOAL_HARNESS_PRODUCT_MODE_ROUTE,
        CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
    }
)
PRODUCT_MODE_ROUTES = frozenset(
    {
        RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
        GOAL_HARNESS_PRODUCT_MODE_ROUTE,
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
        else PACKET_ONLY_OBSERVATION_PROTOCOL_ID
        if route == GOAL_HARNESS_PACKET_ONLY_OBSERVATION_ROUTE
        else "custom_or_legacy_loop"
    )
    claim_blocker = ""
    strict_allowed = bool(
        route
        in {
            GOAL_HARNESS_BLIND_LOOP_TREATMENT_ROUTE,
            GOAL_HARNESS_PROMPT_POLLING_TEST_ROUTE,
        }
        and resolved_protocol == MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID
        and blind_loop
        and budget == BLIND_LOOP_DEFAULT_MAX_ROUNDS
        and not feedback_forwarded
    )
    if route == GOAL_HARNESS_PACKET_ONLY_OBSERVATION_ROUTE:
        claim_blocker = "packet_only_no_max5_controller"
    elif route in {
        GOAL_HARNESS_BLIND_LOOP_TREATMENT_ROUTE,
        GOAL_HARNESS_PROMPT_POLLING_TEST_ROUTE,
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
        GOAL_HARNESS_BLIND_LOOP_TREATMENT_ROUTE,
        GOAL_HARNESS_PROMPT_POLLING_TEST_ROUTE,
    }
    if treatment and treatment_prompt_style == "baseline-safe":
        prefix = "Codex blind-loop baseline-compatible round 1. "
        control_clause = "Use ordinary Codex CLI behavior without goal mode. "
    else:
        prefix = (
            "Structured prompt-polling test round 1. "
            if route == GOAL_HARNESS_PROMPT_POLLING_TEST_ROUTE
            else "Structured blind-loop treatment round 1. "
            if route == GOAL_HARNESS_BLIND_LOOP_TREATMENT_ROUTE
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
        + "Do not invoke /goal mode, external Goal Harness CLI, upload, "
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


def classify_goal_harness_treatment_claim(run: dict[str, Any]) -> dict[str, Any]:
    """Classify whether a compact run is strict treatment evidence.

    This is intentionally conservative. A Goal Harness access packet alone is a
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
        run.get("goal_harness_controller_trace_present")
        or run.get("controller_trace_present")
        or round_count > 0
    )
    prompt_driven_required = bool(
        run.get("goal_harness_prompt_driven_loop_required")
    ) or str(run.get("goal_harness_product_path_primary_route") or "") == (
        "prompt_driven_case_local_goal_harness_cli"
    )
    prompt_driven_lifecycle_observed = bool(
        run.get("goal_harness_prompt_driven_lifecycle_observed")
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
        blockers.append("prompt_driven_goal_harness_lifecycle_absent")
    if route not in {
        GOAL_HARNESS_BLIND_LOOP_TREATMENT_ROUTE,
        GOAL_HARNESS_PROMPT_POLLING_TEST_ROUTE,
        "skillsbench_goal_harness_blind_loop_treatment",
        "skillsbench_goal_harness_prompt_polling_test",
        "goal_harness_prompt_polling_test",
    }:
        blockers.append("route_not_prompt_polling_test")

    allowed = not blockers
    return {
        "schema_version": "goal_harness_treatment_claim_classification_v0",
        "strict_goal_harness_treatment_claim_allowed": allowed,
        "goal_harness_treatment_evidence_tier": (
            "strict_max5_prompt_polling_test" if allowed else "packet_or_incomplete"
        ),
        "goal_harness_treatment_claim_blocker": (
            "none" if allowed else ",".join(blockers)
        ),
        "controller_trace_present": controller_trace_present,
        "round_reward_count": round_count,
    }
