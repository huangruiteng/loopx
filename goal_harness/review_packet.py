from __future__ import annotations

import re
import shlex
from typing import Any

from .execution_profile import (
    compact_execution_profile,
    execution_profile_outcome_floor,
    execution_profile_threshold,
    outcome_floor_threshold,
)
from .handoff_budget import build_handoff_interface_budget


LOCAL_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(^|[\s`'\"=:(])(?:/[A-Za-z0-9._-]+(?:/[^\s`'\",)]+)+|[A-Za-z]:[\\/][^\s`'\",)]+)"
)


def redact_local_absolute_paths(value: str) -> str:
    return LOCAL_ABSOLUTE_PATH_PATTERN.sub(lambda match: f"{match.group(1)}<local-path>", value)


def compact_packet_text(value: str, limit: int = 180) -> str:
    compact = " ".join(str(value).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def command_block(command: str | None) -> str:
    if not command:
        return "（当前没有可执行命令；先读取 status/history。）"
    return "\n".join(["```bash", command, "```"])


def build_status_command(status_payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "goal-harness \\",
            f"  --registry {shlex.quote(str(status_payload.get('registry') or '<registry>'))} \\",
            f"  --runtime-root {shlex.quote(str(status_payload.get('runtime_root') or '<runtime-root>'))} \\",
            "  --format json \\",
            "  status",
        ]
    )


def build_history_command(status_payload: dict[str, Any], goal_id: str) -> str:
    return "\n".join(
        [
            "goal-harness \\",
            f"  --registry {shlex.quote(str(status_payload.get('registry') or '<registry>'))} \\",
            f"  --runtime-root {shlex.quote(str(status_payload.get('runtime_root') or '<runtime-root>'))} \\",
            "  history \\",
            f"  --goal-id {shlex.quote(goal_id)} \\",
            "  --limit 3",
        ]
    )


def build_read_only_map_command(status_payload: dict[str, Any], goal_id: str) -> str:
    return "\n".join(
        [
            "goal-harness \\",
            f"  --registry {shlex.quote(str(status_payload.get('registry') or '<registry>'))} \\",
            f"  --runtime-root {shlex.quote(str(status_payload.get('runtime_root') or '<runtime-root>'))} \\",
            "  read-only-map \\",
            f"  --goal-id {shlex.quote(goal_id)} \\",
            "  --dry-run",
        ]
    )


def build_quota_should_run_command(status_payload: dict[str, Any], goal_id: str) -> str:
    return "\n".join(
        [
            "goal-harness \\",
            f"  --registry {shlex.quote(str(status_payload.get('registry') or '<registry>'))} \\",
            f"  --runtime-root {shlex.quote(str(status_payload.get('runtime_root') or '<runtime-root>'))} \\",
            "  --format json \\",
            "  quota should-run \\",
            f"  --goal-id {shlex.quote(goal_id)}",
        ]
    )


def operator_gate_reason_summary(goal_id: str, decision: str) -> str:
    if decision == "approve":
        return controller_approval_reason(goal_id)
    if decision == "reject":
        return f"暂不同意 {goal_id} 先做 read-only map dry-run，原因：<public-safe-reason>"
    if decision == "defer":
        return f"暂缓 {goal_id} read-only map dry-run，等待：<public-safe-condition>"
    return "<public-safe-reason>"


def build_operator_gate_command(status_payload: dict[str, Any], goal_id: str, *, decision: str = "approve") -> str:
    return "\n".join(
        [
            "goal-harness \\",
            f"  --registry {shlex.quote(str(status_payload.get('registry') or '<registry>'))} \\",
            f"  --runtime-root {shlex.quote(str(status_payload.get('runtime_root') or '<runtime-root>'))} \\",
            "  operator-gate \\",
            f"  --goal-id {shlex.quote(goal_id)} \\",
            f"  --decision {shlex.quote(decision)} \\",
            f"  --reason-summary {shlex.quote(operator_gate_reason_summary(goal_id, decision))} \\",
            "  --dry-run",
        ]
    )


def controller_reply(goal_id: str) -> str:
    return f"同意 {goal_id} 先做 read-only map dry-run / 暂不同意 + 一句话原因。"


def controller_approval_reason(goal_id: str) -> str:
    return f"同意 {goal_id} 先做 read-only map dry-run，不授权写入或生产动作"


def operator_gate_decision_commands(status_payload: dict[str, Any], goal_id: str) -> dict[str, str]:
    return {
        decision: build_operator_gate_command(status_payload, goal_id, decision=decision)
        for decision in ("approve", "reject", "defer")
    }


def find_goal(status_payload: dict[str, Any], goal_id: str) -> dict[str, Any] | None:
    run_history = status_payload.get("run_history")
    if not isinstance(run_history, dict):
        return None
    for goal in run_history.get("goals") or []:
        if isinstance(goal, dict) and goal.get("id") == goal_id:
            return goal
    return None


def find_queue_item(status_payload: dict[str, Any], goal_id: str) -> dict[str, Any] | None:
    attention_queue = status_payload.get("attention_queue")
    if not isinstance(attention_queue, dict):
        return None
    for item in attention_queue.get("items") or []:
        if isinstance(item, dict) and item.get("goal_id") == goal_id:
            return item
    return None


def decision_freshness_warning(status_payload: dict[str, Any], goal_id: str) -> dict[str, Any] | None:
    freshness = (
        status_payload.get("decision_freshness_summary")
        if isinstance(status_payload.get("decision_freshness_summary"), dict)
        else {}
    )
    raw_items = freshness.get("items") if isinstance(freshness.get("items"), list) else []
    items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        if str(item.get("goal_id") or "") != goal_id:
            continue
        if item.get("requires_decision_point_rebase") is not True:
            continue
        items.append(
            {
                "decision_kind": item.get("decision_kind"),
                "freshness_state": item.get("freshness_state"),
                "decision_at": item.get("decision_at"),
                "classification": item.get("classification"),
                "age_days": item.get("age_days"),
                "newer_event_count_7d": item.get("newer_event_count_7d"),
            }
        )
    if not items:
        return None
    return {
        "source": freshness.get("source") or "run_history",
        "window_days": freshness.get("window_days"),
        "message": "旧 reward/gate 决策复用前需在当前 registry/state/quota/policy/run status 上重新对齐。",
        "items": items[:3],
    }


def decision_freshness_packet_lines(warning: dict[str, Any] | None) -> list[str]:
    if not isinstance(warning, dict) or not warning:
        return []
    lines = [
        "",
        "【决策 freshness 警告】",
        str(warning.get("message") or "旧决策复用前需做 decision-point rebase。"),
    ]
    for item in warning.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- "
            f"{compact_packet_text(str(item.get('decision_kind') or 'decision'), limit=60)} "
            f"state={compact_packet_text(str(item.get('freshness_state') or 'unknown'), limit=80)} "
            f"age_days={item.get('age_days')} "
            f"newer_7d={item.get('newer_event_count_7d')} "
            f"at={compact_packet_text(str(item.get('decision_at') or ''), limit=80)}"
        )
    lines.append("处理方式：这不是仓库回滚；只在审批/转交这一瞬间重读当前控制面状态后再复用旧决策。")
    return [redact_local_absolute_paths(line) for line in lines]


def open_todo_texts(todos: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(todos, dict):
        return []
    items = todos.get("items") if isinstance(todos.get("items"), list) else []
    if not items and isinstance(todos.get("first_open_items"), list):
        items = todos.get("first_open_items") or []
    result: list[str] = []
    for item in items:
        if not isinstance(item, dict) or item.get("done"):
            continue
        text = str(item.get("text") or "").strip()
        if text:
            result.append(compact_packet_text(text))
            if len(result) >= limit:
                return result
    return result


def first_open_todo_text(todos: Any) -> str | None:
    items = open_todo_texts(todos, limit=1)
    return items[0] if items else None


def todo_text_from_project_asset(item: dict[str, Any] | None, key: str) -> str | None:
    items = todo_texts_from_project_asset(item, key, limit=1)
    return items[0] if items else None


def todo_texts_from_project_asset(item: dict[str, Any] | None, key: str, *, limit: int = 3) -> list[str]:
    if not isinstance(item, dict):
        return []
    project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
    summary = project_asset.get(key) if isinstance(project_asset.get(key), dict) else {}
    summary_items = open_todo_texts(summary, limit=limit)
    if summary_items:
        return summary_items
    next_text = str(summary.get("next") or "").strip()
    if next_text:
        return [compact_packet_text(next_text)]
    return open_todo_texts(item.get(key), limit=limit)


def project_asset_source(item: dict[str, Any] | None) -> str:
    if isinstance(item, dict) and isinstance(item.get("project_asset"), dict):
        return "project_asset"
    return "legacy_raw_fallback"


def project_asset_source_line(source: str) -> str:
    if source == "project_asset":
        return "project_asset（owner/gate/next/stop 来自 attention_queue.project_asset）"
    return "legacy/raw fallback（未收到 project_asset；summary/action/todos 来自 raw queue/status 降级判断，不能当 owner/gate/stop authority）"


def handoff_followthrough_summary(item: dict[str, Any] | None) -> str | None:
    if not isinstance(item, dict):
        return None
    readiness = item.get("handoff_readiness") if isinstance(item.get("handoff_readiness"), dict) else {}
    latest_run = (
        readiness.get("post_handoff_latest_run")
        if isinstance(readiness.get("post_handoff_latest_run"), dict)
        else {}
    )
    if not latest_run:
        return None
    classification = str(latest_run.get("classification") or "unknown").strip() or "unknown"
    scale = str(latest_run.get("delivery_batch_scale") or "unknown").strip() or "unknown"
    generated_at = str(latest_run.get("generated_at") or "").strip()
    streak = readiness.get("post_handoff_small_scale_streak")
    streak_text = f", small_streak={streak}" if isinstance(streak, int) else ""
    suffix = f", at={generated_at}" if generated_at else ""
    return compact_packet_text(
        f"post_handoff_run={classification}, scale={scale}{streak_text}{suffix}",
        limit=220,
    )


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
    readiness = item.get("handoff_readiness") if isinstance(item.get("handoff_readiness"), dict) else {}
    streak = readiness.get("post_handoff_small_scale_streak")
    outcome_floor = execution_profile_outcome_floor(profile)
    outcome_threshold = outcome_floor_threshold(profile)
    outcome_gap_streak = readiness.get("post_handoff_outcome_gap_streak")
    small_degraded = isinstance(streak, int) and streak >= threshold
    outcome_degraded = isinstance(outcome_gap_streak, int) and outcome_gap_streak >= outcome_threshold
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
        for value in (profile.get("must_include") if isinstance(profile.get("must_include"), list) else [])
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


def authority_material_summary(goal: dict[str, Any] | None) -> str | None:
    if not isinstance(goal, dict):
        return None
    registry = goal.get("authority_registry")
    if not isinstance(registry, dict) or not registry.get("declared"):
        return None
    material_total = int(registry.get("project_material_count") or 0)
    topic_count = int(registry.get("topic_authority_count") or 0)
    if material_total <= 0 and topic_count <= 0:
        return None
    parts = [
        f"topics={topic_count}",
        f"materials={material_total}",
        f"repositories={int(registry.get('project_material_repository_count') or 0)}",
        f"owner_review_required={int(registry.get('project_material_owner_review_required_count') or 0)}",
        f"stale={int(registry.get('project_material_stale_count') or 0)}",
        f"current_authority={int(registry.get('project_material_current_authority_count') or 0)}",
        f"risk={registry.get('conflict_risk') or 'unknown'}",
    ]
    return "authority/material: " + ", ".join(parts)


def latest_run(goal: dict[str, Any] | None) -> dict[str, Any] | None:
    runs = goal.get("latest_runs") if isinstance(goal, dict) else None
    if isinstance(runs, list) and runs and isinstance(runs[0], dict):
        return runs[0]
    return None


def infer_action_kind(item: dict[str, Any] | None, goal: dict[str, Any] | None) -> str:
    run = latest_run(goal)
    missing_gates = item.get("missing_gates") if isinstance(item, dict) else None
    if not isinstance(missing_gates, list) and isinstance(run, dict):
        readiness = run.get("controller_readiness")
        missing_gates = readiness.get("missing_gates") if isinstance(readiness, dict) else None
    missing_gate_set = {str(gate) for gate in missing_gates or [] if gate}
    if isinstance(item, dict) and item.get("severity") == "high":
        return "health"
    if "human_reward_capture" in missing_gate_set:
        return "reward"
    waiting_on = str(item.get("waiting_on") if isinstance(item, dict) else "")
    if waiting_on in {"controller", "user_or_controller"}:
        return "controller"
    if waiting_on == "external_evidence":
        return "evidence"
    if waiting_on == "codex":
        quota = item.get("quota") if isinstance(item, dict) and isinstance(item.get("quota"), dict) else {}
        asset = item.get("project_asset") if isinstance(item, dict) and isinstance(item.get("project_asset"), dict) else {}
        asset_quota = asset.get("quota") if isinstance(asset.get("quota"), dict) else {}
        if quota.get("state") == "focus_wait" or asset_quota.get("state") == "focus_wait":
            return "focus_wait"
        return "codex"
    return "status"


def human_prompt(kind: str) -> dict[str, str]:
    if kind == "reward":
        return {
            "question": "是否把这次判断记录为 run-bound human_reward？",
            "reply": "同意记录 / 暂不同意 + 一句话原因。",
            "boundary": "只有去掉 --dry-run 才会写 human_reward 和 active-state 摘要；这不是 write-control、controller opt-in 或生产动作授权。",
        }
    if kind == "controller":
        return {
            "question": "是否允许目标项目进入 read-only/controller opt-in？",
            "reply": "同意先做 read-only map dry-run / 暂不同意 + 一句话原因。",
            "boundary": "这只授权项目 Agent 预览 dry-run 路径；不写 operator gate、run history、write-control、实验控制或生产动作。",
        }
    if kind == "codex":
        return {
            "question": "是否让项目 Agent 沿 safe local path 继续？",
            "reply": "同意继续 / 暂不同意 + 一句话原因。",
            "boundary": "如果下一步需要写入、reward append、approval 或 write-control，项目 Agent 必须先停下等明确授权。",
        }
    if kind == "evidence":
        return {
            "question": "是否继续等待外部证据，而不升级成决策建议？",
            "reply": "继续等待 / 不继续等待 + 一句话原因。",
            "boundary": "观察状态不是 reward、approval 或 controller opt-in。",
        }
    if kind == "focus_wait":
        return {
            "question": "是否继续保持 focus wait，直到 owner blocker 有新证据？",
            "reply": "继续等待 / 提供新证据并恢复 delivery / 暂缓该线 + 一句话原因。",
            "boundary": "focus wait 不是 delivery 授权；没有新 owner evidence、clean baseline 或外部 eval 时，项目 Agent 只读 status/history。",
        }
    if kind == "health":
        return {
            "question": "是否先修健康阻塞，再讨论 reward/controller/codex handoff？",
            "reply": "先修阻塞 / 暂不处理 + 一句话原因。",
            "boundary": "健康修复不等于授权 reward append、approval 或 write-control。",
        }
    return {
        "question": "当前是否需要转给项目 Agent 继续处理？",
        "reply": "继续 / 不继续 / 继续观察 + 一句话原因。",
        "boundary": "本回复不自动写 reward、approval、controller opt-in 或 write-control。",
    }


def suggested_decision(kind: str, item: dict[str, Any] | None, goal_id: str | None = None) -> str:
    if kind == "controller":
        lead = f"同意 {goal_id} 先做" if goal_id else "同意先做"
        question = str(item.get("operator_question") if isinstance(item, dict) else "")
        if "read-only map" in question:
            return f"{lead} read-only map dry-run；不授权写入或生产动作。"
        return f"{lead}只读 controller dry-run；不授权写入或生产动作。"
    if kind == "reward":
        return "同意记录这次 human reward / 暂不同意，原因是..."
    if kind == "codex":
        return "同意让 Codex 沿 safe path 继续；如需写入再单独请求授权。"
    if kind == "evidence":
        return "继续等待外部证据；暂不升级成决策建议。"
    if kind == "focus_wait":
        return "继续保持 focus wait；有新 owner evidence、clean baseline 或外部 eval 后再恢复 delivery。"
    if kind == "health":
        return "先修健康阻塞；暂不处理 reward/controller/codex handoff。"
    return "继续 / 不继续 / 继续观察，并补一句原因。"


def project_agent_command(
    status_payload: dict[str, Any],
    goal_id: str,
    kind: str,
    item: dict[str, Any] | None,
    goal: dict[str, Any] | None = None,
) -> str:
    if kind == "reward":
        return build_history_command(status_payload, goal_id)
    if isinstance(item, dict) and item.get("agent_command") and kind in {"controller", "codex"}:
        return str(item.get("agent_command"))
    if kind == "controller":
        return build_read_only_map_command(status_payload, goal_id)
    if kind == "codex":
        if connected_delivery_handoff(item, goal):
            return build_quota_should_run_command(status_payload, goal_id)
        return build_history_command(status_payload, goal_id)
    if kind == "focus_wait":
        return build_history_command(status_payload, goal_id)
    return build_status_command(status_payload)


def target_goal_guard(goal_id: str) -> str:
    return (
        f"目标校验：本段只适用于 goal_id=`{goal_id}`；如果与你当前 active goal "
        "或 registry entry 不一致，停止并回报目标不匹配。"
    )


def agent_context_rule() -> str:
    return (
        "上下文规则：本段只携带最小当前指令；如需核验上下文，只读目标 active "
        "state/status/history 和本命令输出，不要从旧聊天或旧 packet 拼当前状态。"
    )


def operator_gate_approved_handoff(item: dict[str, Any] | None, goal: dict[str, Any] | None) -> bool:
    if not isinstance(item, dict) or not item.get("agent_command"):
        return False
    if str(item.get("status") or "") == "operator_gate_approved":
        return True
    run = latest_run(goal)
    operator_gate = run.get("operator_gate") if isinstance(run, dict) else None
    return (
        isinstance(operator_gate, dict)
        and operator_gate.get("decision") == "approve"
        and bool(operator_gate.get("agent_command"))
    )


def connected_delivery_handoff(item: dict[str, Any] | None, goal: dict[str, Any] | None = None) -> bool:
    if not isinstance(item, dict):
        return False
    adapter_status = str(item.get("adapter_status") or "").strip()
    if adapter_status != "connected-delivery" and isinstance(goal, dict):
        adapter_status = str(goal.get("adapter_status") or "").strip()
    if adapter_status != "connected-delivery":
        return False
    if str(item.get("waiting_on") or "") != "codex":
        return False
    quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
    return str(quota.get("state") or "") == "eligible"


def project_agent_section(
    kind: str,
    command: str,
    goal_id: str,
    *,
    agent_todo_text: str | None = None,
    agent_todo_items: list[str] | None = None,
    authority_summary: str | None = None,
    project_asset_source_text: str | None = None,
    handoff_followthrough_text: str | None = None,
    handoff_delivery_contract_text: str | None = None,
    approved_operator_gate: bool = False,
    connected_delivery: bool = False,
) -> str:
    goal_guard = target_goal_guard(goal_id)
    context_rule = agent_context_rule()
    todo_line = f"Agent 待办：{agent_todo_text}" if agent_todo_text else None
    extra_todo_lines = [
        f"Agent 待办候选 {index + 2}：{text}"
        for index, text in enumerate((agent_todo_items or [])[1:3])
        if text
    ]
    authority_line = f"材料上下文：{authority_summary}；只用这些脱敏计数判断 freshness / owner gap，不要要求内部链接或原文。" if authority_summary else None
    source_line = f"项目资产来源：{project_asset_source_text}" if project_asset_source_text else None
    followthrough_line = f"交付观测：{handoff_followthrough_text}" if handoff_followthrough_text else None
    delivery_contract_line = f"交付合同：{handoff_delivery_contract_text}" if handoff_delivery_contract_text else None
    if approved_operator_gate:
        lines = [
            goal_guard,
            context_rule,
            source_line,
            todo_line,
            *extra_todo_lines,
            authority_line,
            followthrough_line,
            delivery_contract_line,
            "转发条件：operator gate 已记录为 approve；本段只用于把已批准的 agent_command 交给目标项目 Agent。",
            "执行边界：只执行下面命令；这是只读/dry-run 执行，不是写权限、主控接管或生产动作授权。",
            "停止条件：命令失败，或需要写入、run history append、生产动作、更高权限时，停下并用中文回报结果。",
            "",
            command_block(command),
        ]
    elif connected_delivery and kind == "codex":
        lines = [
            goal_guard,
            context_rule,
            source_line,
            todo_line,
            *extra_todo_lines,
            authority_line,
            followthrough_line,
            delivery_contract_line,
            "转发条件：目标 registry 已是 connected-delivery，且 quota/owner/gate 显示 codex-ready；本段用于目标项目 Agent 做真实 delivery。",
            "执行边界：先执行下面 quota guard；若 should_run=true，读取 active state/status/goal_boundary/execution_profile 后，选择一个 write_scope 内的 bounded delivery segment，可改文件、验证、写回、spend。",
            "停止条件：只能继续 isolated test、surface-only 下游传播，或需要未授权写入范围、生产动作、destructive git、私密材料时，回报 blocker，不 spend。",
            "",
            command_block(command),
        ]
    elif kind == "reward":
        lines = [
            goal_guard,
            context_rule,
            source_line,
            todo_line,
            *extra_todo_lines,
            authority_line,
            followthrough_line,
            delivery_contract_line,
            "转发条件：只有用户已经真实记录 run-bound human_reward 后，才把本段发给项目 Agent。",
            "执行边界：不要替用户写 reward；active state 只做摘要，reward 的权威来源是 run-bound human_reward overlay。",
            "停止条件：如果 reward 还停留在 dry-run / 草稿 / 口头判断，停下等待用户记录；如果已经记录，只用下面 history 路径读取。",
            "",
            command_block(command),
        ]
    elif kind == "controller":
        lines = [
            goal_guard,
            context_rule,
            source_line,
            todo_line,
            *extra_todo_lines,
            authority_line,
            followthrough_line,
            delivery_contract_line,
            "转发条件：只有用户已经明确同意 read-only/controller dry-run 后，才把本段发给项目 Agent。",
            "执行边界：只执行下面只读或 dry-run 项目路径；不要运行用户本地 Gate 记录草稿。",
            "停止条件：需要真实 approval、write-control、run history append、生产动作或命令失败时，停下等明确授权。",
            "",
            command_block(command),
        ]
    elif kind == "focus_wait":
        lines = [
            goal_guard,
            context_rule,
            source_line,
            todo_line,
            *extra_todo_lines,
            authority_line,
            followthrough_line,
            delivery_contract_line,
            "转发条件：仅当目标项目 Agent 需要当前等待边界时转发；这不是恢复 delivery 的授权。",
            "执行边界：只读 status/history，确认当前 owner blocker、证据入口和 stop condition；不要继续实现、adapter work、写入或生产动作。",
            "停止条件：没有新的 owner evidence、clean baseline 或外部 eval 时，保持 focus_wait 并用中文回报仍在等待什么。",
            "",
            command_block(command),
        ]
    else:
        lines = [
            goal_guard,
            context_rule,
            source_line,
            todo_line,
            *extra_todo_lines,
            authority_line,
            followthrough_line,
            delivery_contract_line,
            "转发条件：只有用户已经同意 safe local path 后，才把本段发给项目 Agent。",
            "执行边界：读取本项目 status/history 后，只执行下面只读或 dry-run 路径。",
            "停止条件：需要真实写 reward、approval、write-control、run history append、生产动作或命令失败时，停下等明确授权。",
            "",
            command_block(command),
        ]
    return "\n".join(line for line in lines if line)


def build_review_packet(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    action_kind: str | None = None,
    review_url: str | None = None,
) -> dict[str, Any]:
    item = find_queue_item(status_payload, goal_id)
    goal = find_goal(status_payload, goal_id)
    if item is None and goal is None:
        return {
            "ok": False,
            "goal_id": goal_id,
            "error": f"goal not found in status payload: {goal_id}",
        }

    kind = action_kind or infer_action_kind(item, goal)
    prompt = human_prompt(kind)
    question = str(item.get("operator_question") or prompt["question"]) if isinstance(item, dict) else prompt["question"]
    summary = str(item.get("recommended_action") or "当前状态源没有对应的 action card。") if isinstance(item, dict) else "当前状态源没有对应的 action card。"
    user_todo_text = todo_text_from_project_asset(item, "user_todos")
    agent_todo_items = todo_texts_from_project_asset(item, "agent_todos")
    agent_todo_text = agent_todo_items[0] if agent_todo_items else None
    asset_source = project_asset_source(item)
    asset_source_line = project_asset_source_line(asset_source)
    authority_summary = authority_material_summary(goal)
    followthrough_summary = handoff_followthrough_summary(item)
    delivery_contract = handoff_delivery_contract(item)
    delivery_contract_text = handoff_delivery_contract_summary(delivery_contract)
    freshness_warning = decision_freshness_warning(status_payload, goal_id)
    freshness_warning_lines = decision_freshness_packet_lines(freshness_warning)
    command = redact_local_absolute_paths(project_agent_command(status_payload, goal_id, kind, item, goal))
    approved_handoff = operator_gate_approved_handoff(item, goal)
    delivery_handoff = connected_delivery_handoff(item, goal) and kind == "codex"
    gate_commands = operator_gate_decision_commands(status_payload, goal_id) if kind == "controller" else {}
    gate_command = gate_commands.get("approve") if gate_commands else None
    decision = suggested_decision(kind, item, goal_id)
    if user_todo_text and kind == "controller":
        decision = f"先确认待办；完成后：{decision}"
    reply = controller_reply(goal_id) if kind == "controller" else prompt["reply"]
    boundary = prompt["boundary"]
    if approved_handoff:
        question = "operator gate 已批准；是否把短交接发给目标项目 Agent？"
        decision = "直接转发给项目 Agent；不追加写权限、主控接管或生产动作授权。"
        reply = "转发下方【给项目 Agent】即可。"
        boundary = "这只是执行已批准的只读/dry-run agent_command；如需写入或更高权限，项目 Agent 必须再次停下。"
    owner_blocker_text = user_todo_text if kind == "focus_wait" else None
    agent_text = project_agent_section(
        kind,
        command,
        goal_id,
        agent_todo_text=agent_todo_text,
        agent_todo_items=agent_todo_items,
        authority_summary=authority_summary,
        project_asset_source_text=asset_source_line,
        handoff_followthrough_text=followthrough_summary,
        handoff_delivery_contract_text=delivery_contract_text,
        approved_operator_gate=approved_handoff,
        connected_delivery=delivery_handoff,
    )
    handoff_interface_budget = build_handoff_interface_budget(agent_text)
    type_label = {
        "reward": "Reward",
        "controller": "Controller",
        "codex": "Codex",
        "focus_wait": "Focus Wait",
        "evidence": "Evidence",
        "health": "Health",
    }.get(kind, "Status")
    lines = [
        "【Goal Harness Review Packet】",
        f"目标：{goal_id}",
        f"类型：{type_label}",
        f"链接：{review_url or 'CLI generated packet; no dashboard URL provided.'}",
        f"摘要：{summary}",
        f"来源：{asset_source_line}",
        f"材料：{authority_summary}（仅脱敏计数；不含内部链接、路径或正文。）" if authority_summary else None,
        *freshness_warning_lines,
        "",
        "【人只需判断】",
        f"解锁条件：{owner_blocker_text}（有新证据或明确暂缓后再调整 focus）" if owner_blocker_text else None,
        f"待办：{user_todo_text}（先处理/暂缓再判 gate）" if user_todo_text and kind == "controller" else None,
        f"问题：{question}",
        f"建议判断：{decision}",
        f"回复：{reply}",
        f"边界：{boundary}",
    ]
    if gate_command:
        lines.extend(
            [
                "",
                "【用户本地 Gate 记录草稿】",
                "用途：人确认后，由用户或主控先 dry-run 预览 durable operator gate；不要把它当作项目 Agent 执行命令。",
                "记录规则：保留 --dry-run 只预览；确认写入 durable operator gate 时再删除 --dry-run。若拒绝或暂缓，只把 --decision 和 --reason-summary 改成 reject / defer 与一句 public-safe 原因。",
                command_block(gate_command),
            ]
        )
    lines.extend(
        [
            "",
            "【给项目 Agent】",
            agent_text,
            "",
            "回报：用中文说明 changed files、validation 和 next safe action。",
        ]
    )
    return {
        "ok": True,
        "goal_id": goal_id,
        "kind": kind,
        "waiting_on": item.get("waiting_on") if isinstance(item, dict) else None,
        "status": item.get("status") if isinstance(item, dict) else goal.get("status") if isinstance(goal, dict) else None,
        "review_url": review_url,
        "question": question,
        "suggested_decision": decision,
        "project_agent_command": command,
        "project_agent_handoff": agent_text,
        "operator_gate_approved_handoff": approved_handoff,
        "connected_delivery_handoff": delivery_handoff,
        "operator_gate_dry_run_command": gate_command,
        "operator_gate_decision_commands": gate_commands,
        "user_todo_text": user_todo_text,
        "owner_blocker_text": owner_blocker_text,
        "agent_todo_text": agent_todo_text,
        "agent_todo_items": agent_todo_items,
        "authority_summary": authority_summary,
        "handoff_followthrough_summary": followthrough_summary,
        "handoff_delivery_contract": delivery_contract,
        "handoff_interface_budget": handoff_interface_budget,
        "decision_freshness_warning": freshness_warning,
        "project_asset_source": asset_source,
        "packet": "\n".join(line for line in lines if line),
    }


def render_review_packet_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return "\n".join(
            [
                "# Goal Harness Review Packet",
                "",
                f"- ok: `{payload.get('ok')}`",
                f"- goal_id: `{payload.get('goal_id')}`",
                f"- error: {payload.get('error')}",
            ]
        )
    return str(payload.get("packet") or "")
