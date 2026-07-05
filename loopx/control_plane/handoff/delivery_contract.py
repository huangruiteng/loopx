from __future__ import annotations

from typing import Any

from ...execution_profile import (
    compact_execution_profile,
    execution_profile_outcome_floor,
    execution_profile_threshold,
    outcome_floor_threshold,
)
from ..runtime.public_safety import compact_text


def compact_packet_text(value: str, limit: int = 180) -> str:
    return compact_text(str(value), limit=limit)


def _contract_minimum_text(value: str) -> str:
    return value.replace("_or_", "/")


def _contract_must_include_text(values: list[str]) -> str:
    display = {
        "coherent_artifact": "artifact",
        "targeted_validation": "targeted validation",
        "state_writeback": "state writeback",
    }
    return "、".join(display.get(value, value.replace("_", " ")) for value in values)


def _contract_label_text(values: list[str]) -> str:
    return "、".join(value.replace("_", " ") for value in values if value)


def handoff_delivery_contract(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
    profile = compact_execution_profile(
        project_asset.get("execution_profile")
        if isinstance(project_asset.get("execution_profile"), dict)
        else None
    )
    threshold = execution_profile_threshold(profile)
    readiness = (
        item.get("handoff_readiness")
        if isinstance(item.get("handoff_readiness"), dict)
        else {}
    )
    streak = readiness.get("post_handoff_small_scale_streak")
    outcome_floor = execution_profile_outcome_floor(profile)
    outcome_threshold = outcome_floor_threshold(profile)
    outcome_gap_streak = readiness.get("post_handoff_outcome_gap_streak")
    small_degraded = isinstance(streak, int) and streak >= threshold
    outcome_degraded = (
        isinstance(outcome_gap_streak, int)
        and outcome_gap_streak >= outcome_threshold
    )
    if not small_degraded and not outcome_degraded:
        return None
    recent_runs = readiness.get("post_handoff_recent_runs")
    recent_scales = [
        str(run.get("delivery_batch_scale") or "unknown").strip() or "unknown"
        for run in recent_runs or []
        if isinstance(run, dict)
    ][:3]
    minimum_scale = str(profile.get("minimum_scale") or "multi_surface_or_implementation")
    must_include = [
        str(value)
        for value in (
            profile.get("must_include")
            if isinstance(profile.get("must_include"), list)
            else []
        )
        if str(value).strip()
    ] or ["coherent_artifact", "targeted_validation", "state_writeback"]
    spend_rule = str(profile.get("spend_rule") or "spend_only_after_artifact_validation_writeback")
    must_advance = [
        str(value)
        for value in (
            outcome_floor.get("must_advance")
            if isinstance(outcome_floor.get("must_advance"), list)
            else []
        )
        if str(value).strip()
    ]
    avoid = [
        str(value)
        for value in (
            outcome_floor.get("avoid")
            if isinstance(outcome_floor.get("avoid"), list)
            else []
        )
        if str(value).strip()
    ]
    mode = (
        "expand_after_surface_progress_loop"
        if outcome_degraded and not small_degraded
        else "expand_after_repeated_small_delivery"
    )
    outcome_summary = (
        f"outcome_gap_streak={outcome_gap_streak}; outcome_threshold={outcome_threshold}; "
        if outcome_degraded
        else ""
    )
    summary = compact_packet_text(
        f"{mode}; "
        f"minimum_scale={minimum_scale}; "
        f"include={'+'.join(must_include)}; "
        f"spend_rule={spend_rule}; "
        f"{outcome_summary}"
        f"small_threshold={threshold}; "
        "if_blocked=report_blocker_without_spend",
        limit=220,
    )
    floor_sentence = ""
    if outcome_degraded and (must_advance or avoid):
        floor_sentence = (
            f"推进 floor={_contract_label_text(must_advance)}；"
            f"避免 {_contract_label_text(avoid)}；"
        )
    instruction = compact_packet_text(
        "下一轮回到 active state P0/P1 outcome 做 audit，"
        f"选连贯段，至少 {_contract_minimum_text(minimum_scale)}；"
        f"{floor_sentence}"
        f"含真实 {_contract_must_include_text(must_include)}；"
        "禁止 isolated test/surface-only propagation；"
        "若只能小步/表面，blocker，不 spend。",
        limit=260,
    )
    return {
        "mode": mode,
        "minimum_scale": minimum_scale,
        "must_include": must_include,
        "outcome_floor": outcome_floor,
        "spend_rule": spend_rule,
        "small_scale_streak_threshold": threshold,
        "outcome_gap_streak_threshold": outcome_threshold,
        "if_blocked": "report_blocker_without_spend",
        "post_handoff_small_scale_streak": streak,
        "post_handoff_outcome_gap_streak": outcome_gap_streak,
        "recent_scales": recent_scales,
        "execution_profile": profile,
        "summary": summary,
        "instruction": instruction,
    }


def handoff_delivery_contract_summary(contract: dict[str, Any] | None) -> str | None:
    if not isinstance(contract, dict):
        return None
    instruction = str(contract.get("instruction") or "").strip()
    if instruction:
        return instruction
    summary = str(contract.get("summary") or "").strip()
    return summary or None
