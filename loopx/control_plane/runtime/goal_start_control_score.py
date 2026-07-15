from __future__ import annotations

from typing import Any

from loopx.benchmark_case_state import (
    BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS,
    BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS,
)

from .public_safety import (
    LOOPX_COMMAND_RECORD_TODO_ID_PATTERN,
    compact_loopx_command_records,
    public_safe_compact_list,
    public_safe_compact_text,
)


MAX_GOAL_START_TODOS = 8


def _safe_string(value: Any, *, limit: int = 140) -> str:
    if not isinstance(value, str):
        return ""
    return value[:limit] if value else ""


def _max_int(*values: Any) -> int:
    safe_values = [
        max(0, value)
        for value in values
        if isinstance(value, int) and not isinstance(value, bool)
    ]
    return max(safe_values) if safe_values else 0


def _public_count_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        key[:80]: count
        for key, count in value.items()
        if (
            isinstance(key, str)
            and key
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count >= 0
        )
    }


def _subcommand_family_count(counter: dict[str, int], *families: str) -> int:
    total = 0
    for command, count in counter.items():
        normalized = " ".join(command.split())
        if any(
            normalized == family or normalized.startswith(f"{family} ")
            for family in families
        ):
            total += max(0, count)
    return total


def _subcommand_count(families: tuple[str, ...], *maps: Any) -> int:
    return max(
        (
            _subcommand_family_count(_public_count_map(item), *families)
            for item in maps
        ),
        default=0,
    )


def goal_start_public_text_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = public_safe_compact_text(item, limit=180)
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def goal_start_public_todo_id_list(value: Any, *, limit: int = 16) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        todo_id = public_safe_compact_text(item, limit=100)
        if (
            todo_id
            and LOOPX_COMMAND_RECORD_TODO_ID_PATTERN.match(todo_id)
            and todo_id not in result
        ):
            result.append(todo_id)
        if len(result) >= limit:
            break
    return result


def goal_start_public_command_records(*values: Any) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for value in values:
        records.extend(compact_loopx_command_records(value, limit=128 - len(records)))
        if len(records) >= 128:
            break
    return records


def _planned_todo_packet(
    counters: dict[str, Any],
    runner_prerequisites: dict[str, Any],
) -> tuple[list[str], list[str]]:
    agent_authored_required = bool(
        counters.get("goal_start_agent_authored_plan_required") is True
        or runner_prerequisites.get("goal_start_agent_authored_plan_required") is True
        or runner_prerequisites.get("goal_start_host_preseed_forbidden") is True
    )
    record_source = counters.get(
        "remote_command_file_bridge_agent_successful_loopx_command_records"
    )
    if not isinstance(record_source, list) or not record_source:
        record_source = runner_prerequisites.get(
            "remote_command_file_bridge_agent_successful_loopx_command_records"
        )
    command_ids: list[str] = []
    for record in goal_start_public_command_records(record_source):
        if record.get("subcommand") != "todo add":
            continue
        todo_id = record.get("todo_id", "")
        if todo_id and todo_id not in command_ids:
            command_ids.append(todo_id)
    if agent_authored_required:
        return command_ids[:MAX_GOAL_START_TODOS], []

    ids = command_ids or (
        goal_start_public_todo_id_list(counters.get("planned_todo_ids"))
        or goal_start_public_todo_id_list(
            runner_prerequisites.get("planned_todo_ids")
        )
    )
    texts = goal_start_public_text_list(
        counters.get("planned_todo_texts_public_safe")
    ) or goal_start_public_text_list(
        runner_prerequisites.get("planned_todo_texts_public_safe")
    )
    if not ids and (
        counters.get("goal_start_product_mode") is True
        or runner_prerequisites.get("goal_start_product_mode") is True
        or runner_prerequisites.get("goal_start_plan_required") is True
    ):
        ids = list(BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS)
    if not texts and ids:
        texts = list(BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS)
    return ids[:MAX_GOAL_START_TODOS], texts[:MAX_GOAL_START_TODOS]


def _build_todo_snapshot(
    *,
    counters: dict[str, Any],
    runner_prerequisites: dict[str, Any],
    selected_p0_todo_id: str,
    agent_claim_count: int,
    agent_update_count: int,
    agent_complete_count: int,
    selected_todo_claimed: bool,
    selected_todo_updated_before_solver: bool,
) -> dict[str, Any]:
    planned_ids, planned_texts = _planned_todo_packet(counters, runner_prerequisites)
    if not selected_p0_todo_id and planned_ids:
        selected_p0_todo_id = planned_ids[0]
    record_source = counters.get(
        "remote_command_file_bridge_agent_successful_loopx_command_records"
    )
    if not isinstance(record_source, list) or not record_source:
        record_source = runner_prerequisites.get(
            "remote_command_file_bridge_agent_successful_loopx_command_records"
        )
    records = goal_start_public_command_records(record_source)
    counts_by_todo: dict[str, dict[str, int]] = {}
    complete_without_todo_id = 0
    for record in records:
        subcommand = record.get("subcommand", "")
        if subcommand not in {"todo claim", "todo update", "todo complete"}:
            continue
        todo_id = record.get("todo_id", "")
        if not todo_id:
            if subcommand == "todo complete":
                complete_without_todo_id += 1
            continue
        counts = counts_by_todo.setdefault(
            todo_id,
            {"claim": 0, "update": 0, "complete": 0},
        )
        counts[subcommand.split()[1]] += 1

    inferred_identity = False
    if not records and selected_p0_todo_id:
        selected_counts = counts_by_todo.setdefault(
            selected_p0_todo_id,
            {"claim": 0, "update": 0, "complete": 0},
        )
        if agent_claim_count > 0 or selected_todo_claimed:
            selected_counts["claim"] = max(selected_counts["claim"], agent_claim_count)
        if agent_update_count > 0 or selected_todo_updated_before_solver:
            selected_counts["update"] = max(
                selected_counts["update"],
                agent_update_count,
            )
        if agent_complete_count > 0:
            selected_counts["complete"] = max(
                selected_counts["complete"],
                agent_complete_count,
            )
            inferred_identity = True

    completed_ids = sorted(
        todo_id
        for todo_id, counts in counts_by_todo.items()
        if counts.get("complete", 0) > 0
    )
    selected_counts = counts_by_todo.get(
        selected_p0_todo_id,
        {"claim": 0, "update": 0, "complete": 0},
    )
    selected_complete_count = max(0, selected_counts.get("complete", 0))
    selected_duplicate_complete_count = max(0, selected_complete_count - 1)
    non_selected_complete_count = sum(
        max(0, counts.get("complete", 0))
        for todo_id, counts in counts_by_todo.items()
        if todo_id != selected_p0_todo_id
    )

    planned_todos: list[dict[str, Any]] = []
    for index, todo_id in enumerate(planned_ids):
        counts = counts_by_todo.get(
            todo_id,
            {"claim": 0, "update": 0, "complete": 0},
        )
        complete_count = max(0, counts.get("complete", 0))
        if complete_count > 0:
            status = "done_observed"
        elif todo_id == selected_p0_todo_id:
            status = "open_or_in_progress_observed"
        else:
            status = "open_or_deferred_observed"
        item: dict[str, Any] = {
            "todo_id": todo_id,
            "role": "selected_p0" if todo_id == selected_p0_todo_id else "supporting",
            "status": status,
            "claim_count": max(0, counts.get("claim", 0)),
            "update_count": max(0, counts.get("update", 0)),
            "complete_count": complete_count,
        }
        if index < len(planned_texts):
            item["text_public_safe"] = planned_texts[index]
        planned_todos.append(item)

    return {
        "schema_version": "skillsbench_goal_start_todo_snapshot_v0",
        "raw_material_recorded": False,
        "planned_todos": planned_todos,
        "planned_todo_ids": planned_ids,
        "planned_todo_texts_public_safe": planned_texts,
        "selected_p0_todo_id": selected_p0_todo_id,
        "completed_todo_ids": completed_ids[:MAX_GOAL_START_TODOS],
        "completed_todo_id_count": len(completed_ids),
        "selected_todo_complete_count": selected_complete_count,
        "selected_todo_duplicate_complete_count": selected_duplicate_complete_count,
        "non_selected_todo_complete_count": non_selected_complete_count,
        "todo_complete_without_todo_id_count": complete_without_todo_id,
        "todo_identity_attribution": (
            "inferred_from_counts" if inferred_identity else "command_record_observed"
        ),
    }


def build_goal_start_product_mode_control_score(
    compact: dict[str, Any],
    *,
    runner_prerequisites: dict[str, Any],
) -> dict[str, Any]:
    """Summarize goal-start closure from public compact counters."""

    counters = (
        compact.get("interaction_counters")
        if isinstance(compact.get("interaction_counters"), dict)
        else {}
    )
    runner_prerequisites = dict(runner_prerequisites)
    compact_runner_prerequisites = compact.get("runner_prerequisites")
    if isinstance(compact_runner_prerequisites, dict):
        runner_prerequisites.update(compact_runner_prerequisites)
    lifecycle_contract = (
        compact.get("product_mode_lifecycle_contract")
        if isinstance(compact.get("product_mode_lifecycle_contract"), dict)
        else {}
    )

    required = bool(
        counters.get("goal_start_product_mode") is True
        or runner_prerequisites.get("goal_start_product_mode") is True
        or runner_prerequisites.get("goal_start_plan_required") is True
    )
    if not required:
        return {}

    agent_successful_subcommands = counters.get(
        "remote_command_file_bridge_agent_successful_loopx_subcommand_counts"
    )
    agent_requested_subcommands = counters.get(
        "remote_command_file_bridge_agent_loopx_subcommand_counts"
    )
    prereq_agent_successful_subcommands = runner_prerequisites.get(
        "remote_command_file_bridge_agent_successful_loopx_subcommand_counts"
    )
    prereq_agent_requested_subcommands = runner_prerequisites.get(
        "remote_command_file_bridge_agent_loopx_subcommand_counts"
    )
    driver_commands = counters.get(
        "remote_command_file_bridge_driver_lifecycle_command_counts"
    )
    prereq_driver_commands = runner_prerequisites.get(
        "remote_command_file_bridge_driver_lifecycle_command_counts"
    )
    driver_failure_count = _max_int(
        counters.get("remote_command_file_bridge_driver_lifecycle_failure_count"),
        runner_prerequisites.get(
            "remote_command_file_bridge_driver_lifecycle_failure_count"
        ),
    )
    driver_commands_count_as_successful = driver_failure_count == 0
    agent_authored_required = bool(
        counters.get("goal_start_agent_authored_plan_required") is True
        or runner_prerequisites.get("goal_start_agent_authored_plan_required") is True
        or runner_prerequisites.get("goal_start_host_preseed_forbidden") is True
    )
    record_source = counters.get(
        "remote_command_file_bridge_agent_successful_loopx_command_records"
    )
    if not isinstance(record_source, list) or not record_source:
        record_source = runner_prerequisites.get(
            "remote_command_file_bridge_agent_successful_loopx_command_records"
        )
    command_records = goal_start_public_command_records(record_source)
    start_goal_indexes = [
        index
        for index, record in enumerate(command_records)
        if record.get("subcommand") == "start-goal"
    ]
    todo_add_indexes = [
        index
        for index, record in enumerate(command_records)
        if record.get("subcommand") == "todo add"
    ]
    todo_add_ids = [
        record.get("todo_id", "")
        for record in command_records
        if record.get("subcommand") == "todo add"
    ]
    claimed_todo_ids = [
        record.get("todo_id", "")
        for record in command_records
        if record.get("subcommand") == "todo claim"
    ]

    selected_p0_todo_id_from_state = _safe_string(
        counters.get("selected_p0_todo_id")
        or runner_prerequisites.get("selected_p0_todo_id"),
        limit=100,
    )
    planned_todo_ids, planned_todo_texts = _planned_todo_packet(
        counters,
        runner_prerequisites,
    )
    expected_todo_count = _max_int(
        runner_prerequisites.get("goal_start_planned_todo_count_expected")
    )
    if agent_authored_required:
        selected_p0_todo_id = selected_p0_todo_id_from_state
        if selected_p0_todo_id not in planned_todo_ids:
            selected_p0_todo_id = next(
                (todo_id for todo_id in claimed_todo_ids if todo_id in planned_todo_ids),
                planned_todo_ids[0] if planned_todo_ids else "",
            )
        ordered_unique_todo_adds = bool(
            todo_add_ids
            and all(todo_add_ids)
            and len(todo_add_ids) == len(set(todo_add_ids))
            and todo_add_ids == planned_todo_ids
        )
        planned_todo_count = len(planned_todo_ids)
        planned_p0_count = 1 if selected_p0_todo_id else 0
        goal_start_guided_observed = bool(start_goal_indexes)
        planner_before_todo_write = bool(
            start_goal_indexes
            and todo_add_indexes
            and start_goal_indexes[0] < todo_add_indexes[0]
        )
        same_priority_order_preserved = ordered_unique_todo_adds
        planned_todo_count_satisfied = bool(
            planned_todo_count > 0
            and (
                expected_todo_count == 0
                or planned_todo_count == expected_todo_count
            )
        )
        goal_start_plan_observed = bool(
            goal_start_guided_observed
            and planned_todo_count_satisfied
            and ordered_unique_todo_adds
        )
    else:
        selected_p0_todo_id = selected_p0_todo_id_from_state
        if not selected_p0_todo_id and planned_todo_ids:
            selected_p0_todo_id = planned_todo_ids[0]
        planned_todo_count = _max_int(counters.get("planned_todo_count"))
        if planned_todo_ids:
            planned_todo_count = max(planned_todo_count, len(planned_todo_ids))
        planned_p0_count = _max_int(counters.get("planned_p0_count"))
        if selected_p0_todo_id:
            planned_p0_count = max(planned_p0_count, 1)
        goal_start_guided_observed = True
        planner_before_todo_write = counters.get("planner_before_todo_write") is True
        same_priority_order_preserved = (
            counters.get("same_priority_order_preserved") is True
        )
        goal_start_plan_observed = counters.get("goal_start_plan_observed") is True
        planned_todo_count_satisfied = bool(
            planned_todo_count > 0
            and (
                expected_todo_count == 0
                or planned_todo_count >= expected_todo_count
            )
        )

    closeout_spend_count = _max_int(
        counters.get("remote_command_file_bridge_agent_quota_spend_slot_count"),
        runner_prerequisites.get(
            "remote_command_file_bridge_agent_quota_spend_slot_count"
        ),
        lifecycle_contract.get("agent_bridge_quota_spend_slot_count"),
    )
    agent_start_goal_count = _subcommand_count(
        ("start-goal",),
        agent_successful_subcommands,
        prereq_agent_successful_subcommands,
        agent_requested_subcommands,
        prereq_agent_requested_subcommands,
    )
    agent_todo_add_count = _subcommand_count(
        ("todo add",),
        agent_successful_subcommands,
        prereq_agent_successful_subcommands,
        agent_requested_subcommands,
        prereq_agent_requested_subcommands,
    )
    agent_start_goal_count = max(agent_start_goal_count, len(start_goal_indexes))
    agent_todo_add_count = max(agent_todo_add_count, len(todo_add_indexes))
    agent_claim_count = _subcommand_count(
        ("todo claim",),
        agent_successful_subcommands,
        prereq_agent_successful_subcommands,
        agent_requested_subcommands,
        prereq_agent_requested_subcommands,
    )
    agent_update_count = _subcommand_count(
        ("todo update",),
        agent_successful_subcommands,
        prereq_agent_successful_subcommands,
        agent_requested_subcommands,
        prereq_agent_requested_subcommands,
    )
    agent_complete_count = _subcommand_count(
        ("todo complete",),
        agent_successful_subcommands,
        prereq_agent_successful_subcommands,
        agent_requested_subcommands,
        prereq_agent_requested_subcommands,
    )
    agent_spend_count = _subcommand_count(
        ("quota spend-slot",),
        agent_successful_subcommands,
        prereq_agent_successful_subcommands,
        agent_requested_subcommands,
        prereq_agent_requested_subcommands,
    )
    driver_claim_count = (
        _subcommand_count(("todo claim",), driver_commands, prereq_driver_commands)
        if driver_commands_count_as_successful
        else 0
    )
    driver_update_count = (
        _subcommand_count(("todo update",), driver_commands, prereq_driver_commands)
        if driver_commands_count_as_successful
        else 0
    )

    selected_claim_indexes = [
        index
        for index, record in enumerate(command_records)
        if record.get("subcommand") == "todo claim"
        and record.get("todo_id") == selected_p0_todo_id
    ]
    selected_update_indexes = [
        index
        for index, record in enumerate(command_records)
        if record.get("subcommand") == "todo update"
        and record.get("todo_id") == selected_p0_todo_id
    ]
    selected_complete_indexes = [
        index
        for index, record in enumerate(command_records)
        if record.get("subcommand") == "todo complete"
        and record.get("todo_id") == selected_p0_todo_id
    ]
    spend_indexes = [
        index
        for index, record in enumerate(command_records)
        if record.get("subcommand") == "quota spend-slot"
    ]
    agent_claim_count = max(
        agent_claim_count,
        sum(record.get("subcommand") == "todo claim" for record in command_records),
    )
    agent_update_count = max(
        agent_update_count,
        sum(record.get("subcommand") == "todo update" for record in command_records),
    )
    agent_complete_count = max(
        agent_complete_count,
        sum(record.get("subcommand") == "todo complete" for record in command_records),
    )
    agent_spend_count = max(agent_spend_count, len(spend_indexes))
    if agent_authored_required:
        selected_todo_claimed = bool(selected_claim_indexes)
        selected_todo_updated_before_solver = bool(selected_update_indexes)
    else:
        selected_todo_claimed = bool(
            counters.get("selected_todo_claimed") is True
            or agent_claim_count > 0
            or driver_claim_count > 0
        )
        selected_todo_updated_before_solver = bool(
            counters.get("selected_todo_updated_before_solver") is True
            or agent_update_count > 0
            or driver_update_count > 0
        )
    selected_todo_spend_observed = bool(
        closeout_spend_count > 0 or agent_spend_count > 0 or spend_indexes
    )
    if agent_authored_required:
        selected_todo_completed_before_spend = bool(
            selected_complete_indexes
            and spend_indexes
            and selected_complete_indexes[0] < spend_indexes[-1]
        )
    else:
        selected_todo_completed_before_spend = bool(
            counters.get("selected_todo_completed_before_spend") is True
            or (agent_complete_count > 0 and selected_todo_spend_observed)
        )
    todo_snapshot = _build_todo_snapshot(
        counters=counters,
        runner_prerequisites=runner_prerequisites,
        selected_p0_todo_id=selected_p0_todo_id,
        agent_claim_count=agent_claim_count,
        agent_update_count=agent_update_count,
        agent_complete_count=agent_complete_count,
        selected_todo_claimed=selected_todo_claimed,
        selected_todo_updated_before_solver=selected_todo_updated_before_solver,
    )
    selected_todo_complete_count = _max_int(
        todo_snapshot.get("selected_todo_complete_count")
    )
    selected_todo_duplicate_complete_count = _max_int(
        todo_snapshot.get("selected_todo_duplicate_complete_count")
    )
    non_selected_todo_complete_count = _max_int(
        todo_snapshot.get("non_selected_todo_complete_count")
    )
    todo_complete_without_todo_id_count = _max_int(
        todo_snapshot.get("todo_complete_without_todo_id_count")
    )
    completed_todo_id_count = _max_int(todo_snapshot.get("completed_todo_id_count"))
    selected_todo_completed_observed = bool(
        selected_todo_complete_count > 0
        or (not agent_authored_required and agent_complete_count > 0)
    )
    non_selected_todos_preserved = bool(
        non_selected_todo_complete_count == 0
        if agent_authored_required
        else counters.get("non_selected_todos_preserved_open_or_deferred") is True
    )
    quota_spend_missing_after_repeated_complete = bool(
        selected_todo_duplicate_complete_count > 0
        and not selected_todo_spend_observed
    )
    last_decision = _safe_string(counters.get("last_decision"), limit=100)
    premature_done_signal_count = _max_int(
        counters.get("product_mode_declared_done_below_passing_reward_count")
    )
    premature_done_stop_reason = ""
    if counters.get("product_mode_no_open_todo_below_passing_reward_stop") is True:
        premature_done_stop_reason = last_decision or "no_open_todo_below_passing_reward_stop"
    elif (
        counters.get("product_mode_declared_done_below_passing_reward") is True
        and last_decision.startswith("stop_after")
        and "below_passing_reward" in last_decision
    ):
        premature_done_stop_reason = last_decision or "declared_done_below_passing_reward"
    repair_round_entered = _max_int(
        counters.get("product_mode_typed_repair_round_entered")
    )
    repair_todo_identity_observed = bool(
        counters.get("product_mode_typed_repair_todo_identity_observed") is True
    )
    repair_task_or_validation_delta = bool(
        counters.get("product_mode_typed_repair_task_or_validation_delta") is True
    )
    terminal_receipt_consistent = bool(
        counters.get("product_mode_typed_repair_terminal_receipt_consistent") is True
    )

    component_results = [
        {"name": "guided_start_goal_observed", "satisfied": goal_start_guided_observed},
        {"name": "plan_observed", "satisfied": goal_start_plan_observed},
        {
            "name": "planned_todo_count",
            "satisfied": planned_todo_count_satisfied,
        },
        {"name": "planned_p0_count", "satisfied": planned_p0_count > 0},
        {"name": "planner_before_todo_write", "satisfied": planner_before_todo_write},
        {
            "name": "same_priority_order_preserved",
            "satisfied": same_priority_order_preserved,
        },
        {"name": "selected_p0_todo_id", "satisfied": bool(selected_p0_todo_id)},
        {"name": "selected_todo_claimed", "satisfied": selected_todo_claimed},
        {
            "name": "selected_todo_updated",
            "satisfied": selected_todo_updated_before_solver,
        },
        {
            "name": "selected_todo_completed_before_spend",
            "satisfied": selected_todo_completed_before_spend,
        },
        {
            "name": "selected_todo_spend_observed",
            "satisfied": selected_todo_spend_observed,
        },
        {
            "name": "non_selected_todos_preserved_open_or_deferred",
            "satisfied": non_selected_todos_preserved,
        },
        {"name": "no_premature_done_stop", "satisfied": not premature_done_stop_reason},
    ]
    satisfied_count = sum(1 for item in component_results if item["satisfied"])
    component_count = len(component_results)
    score = round(satisfied_count / component_count, 3) if component_count else 0.0
    return {
        "schema_version": "skillsbench_goal_start_product_mode_control_score_v1",
        "required": True,
        "satisfied": satisfied_count == component_count,
        "score": score,
        "component_count": component_count,
        "satisfied_component_count": satisfied_count,
        "raw_material_recorded": False,
        "goal_start_agent_authored_plan_required": agent_authored_required,
        "goal_start_guided_command_observed": goal_start_guided_observed,
        "goal_start_plan_observed": goal_start_plan_observed,
        "planned_todo_count": planned_todo_count,
        "planned_todo_count_expected": expected_todo_count,
        "planned_p0_count": planned_p0_count,
        "planner_before_todo_write": planner_before_todo_write,
        "same_priority_order_preserved": same_priority_order_preserved,
        "selected_p0_todo_id": selected_p0_todo_id,
        "selected_todo_claimed": selected_todo_claimed,
        "selected_todo_updated_observed": selected_todo_updated_before_solver,
        "selected_todo_updated_before_solver": selected_todo_updated_before_solver,
        "selected_todo_completed_before_spend": selected_todo_completed_before_spend,
        "selected_todo_completed_observed": selected_todo_completed_observed,
        "selected_todo_spend_observed": selected_todo_spend_observed,
        "non_selected_todos_preserved_open_or_deferred": non_selected_todos_preserved,
        "quota_spend_missing_after_repeated_complete": (
            quota_spend_missing_after_repeated_complete
        ),
        "premature_done_signal_count": premature_done_signal_count,
        "premature_done_stop_reason": premature_done_stop_reason,
        "repair_round_entered": repair_round_entered,
        "repair_todo_identity_observed": repair_todo_identity_observed,
        "repair_task_or_validation_delta": repair_task_or_validation_delta,
        "terminal_receipt_consistent": terminal_receipt_consistent,
        "agent_start_goal_count": agent_start_goal_count,
        "agent_todo_add_count": agent_todo_add_count,
        "agent_todo_claim_count": agent_claim_count,
        "agent_todo_update_count": agent_update_count,
        "agent_todo_complete_count": agent_complete_count,
        "agent_todo_complete_unique_todo_count": completed_todo_id_count,
        "selected_todo_complete_count": selected_todo_complete_count,
        "selected_todo_duplicate_complete_count": selected_todo_duplicate_complete_count,
        "non_selected_todo_complete_count": non_selected_todo_complete_count,
        "todo_complete_without_todo_id_count": todo_complete_without_todo_id_count,
        "agent_quota_spend_slot_count": max(closeout_spend_count, agent_spend_count),
        "driver_todo_claim_count": driver_claim_count,
        "driver_todo_update_count": driver_update_count,
        "planned_todo_ids": planned_todo_ids,
        "planned_todo_texts_public_safe": planned_todo_texts,
        "goal_start_todo_snapshot": todo_snapshot,
        "component_results": component_results,
    }


def compact_goal_start_todo_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    if isinstance(value.get("raw_material_recorded"), bool):
        compact["raw_material_recorded"] = value["raw_material_recorded"]
    for field in (
        "completed_todo_id_count",
        "selected_todo_complete_count",
        "selected_todo_duplicate_complete_count",
        "non_selected_todo_complete_count",
        "todo_complete_without_todo_id_count",
    ):
        raw = value.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool):
            compact[field] = max(0, raw)
    for field in ("selected_p0_todo_id", "todo_identity_attribution"):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    planned_ids = public_safe_compact_list(
        value.get("planned_todo_ids"),
        limit=MAX_GOAL_START_TODOS,
    )
    if planned_ids:
        compact["planned_todo_ids"] = planned_ids
    completed_ids = public_safe_compact_list(
        value.get("completed_todo_ids"),
        limit=MAX_GOAL_START_TODOS,
    )
    if completed_ids:
        compact["completed_todo_ids"] = completed_ids
    planned_texts = public_safe_compact_list(
        value.get("planned_todo_texts_public_safe"),
        limit=MAX_GOAL_START_TODOS,
    )
    if planned_texts:
        compact["planned_todo_texts_public_safe"] = planned_texts
    planned_todos: list[dict[str, Any]] = []
    source_todos = value.get("planned_todos")
    if isinstance(source_todos, list):
        for item in source_todos[:MAX_GOAL_START_TODOS]:
            if not isinstance(item, dict):
                continue
            todo: dict[str, Any] = {}
            for field in ("todo_id", "role", "status", "text_public_safe"):
                text = public_safe_compact_text(item.get(field), limit=180)
                if text:
                    todo[field] = text
            for field in ("claim_count", "update_count", "complete_count"):
                raw = item.get(field)
                if isinstance(raw, int) and not isinstance(raw, bool):
                    todo[field] = max(0, raw)
            if todo:
                planned_todos.append(todo)
    if planned_todos:
        compact["planned_todos"] = planned_todos
    return compact


def compact_goal_start_product_mode_control_score(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in (
        "required",
        "satisfied",
        "raw_material_recorded",
        "goal_start_agent_authored_plan_required",
        "goal_start_guided_command_observed",
        "goal_start_plan_observed",
        "planner_before_todo_write",
        "same_priority_order_preserved",
        "selected_todo_claimed",
        "selected_todo_updated_observed",
        "selected_todo_updated_before_solver",
        "selected_todo_completed_before_spend",
        "selected_todo_completed_observed",
        "selected_todo_spend_observed",
        "non_selected_todos_preserved_open_or_deferred",
        "quota_spend_missing_after_repeated_complete",
        "repair_todo_identity_observed",
        "repair_task_or_validation_delta",
        "terminal_receipt_consistent",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "component_count",
        "satisfied_component_count",
        "planned_todo_count",
        "planned_todo_count_expected",
        "planned_p0_count",
        "premature_done_signal_count",
        "agent_start_goal_count",
        "agent_todo_add_count",
        "agent_todo_claim_count",
        "agent_todo_update_count",
        "agent_todo_complete_count",
        "agent_todo_complete_unique_todo_count",
        "selected_todo_complete_count",
        "selected_todo_duplicate_complete_count",
        "non_selected_todo_complete_count",
        "todo_complete_without_todo_id_count",
        "agent_quota_spend_slot_count",
        "driver_todo_claim_count",
        "driver_todo_update_count",
        "repair_round_entered",
    ):
        raw = value.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool):
            compact[field] = max(0, raw)
    score = value.get("score")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        compact["score"] = float(score)
    for field in ("selected_p0_todo_id", "premature_done_stop_reason"):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    planned_ids = public_safe_compact_list(
        value.get("planned_todo_ids"),
        limit=MAX_GOAL_START_TODOS,
    )
    if planned_ids:
        compact["planned_todo_ids"] = planned_ids
    planned_texts = public_safe_compact_list(
        value.get("planned_todo_texts_public_safe"),
        limit=MAX_GOAL_START_TODOS,
    )
    if planned_texts:
        compact["planned_todo_texts_public_safe"] = planned_texts
    snapshot = compact_goal_start_todo_snapshot(value.get("goal_start_todo_snapshot"))
    if snapshot:
        compact["goal_start_todo_snapshot"] = snapshot
    return compact
