from __future__ import annotations

from typing import Any

from ..agents.agent_scope import _action_scope_tokens_from_text
from .recent_runs import goal_latest_runs


def recent_reward_lessons(
    status_payload: dict[str, Any], *, goal_id: str
) -> list[dict[str, Any]]:
    lessons: list[dict[str, Any]] = []
    run_history = (
        status_payload.get("run_history")
        if isinstance(status_payload.get("run_history"), dict)
        else {}
    )
    for goal in run_history.get("goals") or []:
        if not isinstance(goal, dict) or str(goal.get("id") or "") != goal_id:
            continue
        lessons.extend(
            dict(lesson)
            for lesson in (goal.get("active_reward_lessons") or [])
            if isinstance(lesson, dict)
        )
        break
    seen_reward_ids = {
        str(lesson.get("reward_id") or "") for lesson in lessons if lesson.get("reward_id")
    }
    for run in goal_latest_runs(status_payload, goal_id=goal_id):
        reward = run.get("human_reward") if isinstance(run.get("human_reward"), dict) else {}
        lesson = reward.get("lesson") if isinstance(reward.get("lesson"), dict) else {}
        if not lesson:
            continue
        reward_id = str(reward.get("reward_id") or "")
        if reward_id and reward_id in seen_reward_ids:
            continue
        lessons.append(
            {
                "reward_id": reward_id or None,
                "generated_at": run.get("generated_at"),
                "decision": reward.get("decision"),
                "reward": reward.get("reward"),
                "kind": lesson.get("kind"),
                "summary": lesson.get("summary"),
                "strength": lesson.get("strength") or "advisory",
                "scope": lesson.get("scope") or "goal",
                "scope_key": lesson.get("scope_key"),
                "avoid": lesson.get("avoid") if isinstance(lesson.get("avoid"), list) else [],
                "prefer": lesson.get("prefer") if isinstance(lesson.get("prefer"), list) else [],
            }
        )
    return lessons


def reward_lesson_projection(
    status_payload: dict[str, Any], *, goal_id: str
) -> dict[str, Any] | None:
    lessons = recent_reward_lessons(status_payload, goal_id=goal_id)
    if not lessons:
        return None
    items = [
        {
            key: lesson.get(key)
            for key in (
                "reward_id",
                "recorded_at",
                "generated_at",
                "kind",
                "summary",
                "strength",
                "scope",
                "scope_key",
                "avoid",
                "prefer",
            )
            if lesson.get(key) not in (None, [], "")
        }
        for lesson in lessons[:5]
    ]
    return {
        "schema_version": "reward_lesson_projection_v0",
        "source": "goal_reward_event_ledger",
        "goal_id": goal_id,
        "active_count": len(lessons),
        "required_count": sum(
            1 for lesson in lessons if lesson.get("strength") == "required"
        ),
        "items": items,
        "application_evidence_required": any(
            lesson.get("strength") == "required" for lesson in lessons
        ),
    }


def reward_lesson_projection_warning(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    recommended_action: str | None,
) -> dict[str, Any] | None:
    action = str(recommended_action or "").strip()
    if not action:
        return None
    action_lower = action.lower()
    action_tokens = _action_scope_tokens_from_text(action)
    matches: list[dict[str, Any]] = []
    for lesson in recent_reward_lessons(status_payload, goal_id=goal_id):
        for avoid in lesson.get("avoid") or []:
            avoid_text = str(avoid or "").strip()
            if not avoid_text:
                continue
            avoid_tokens = _action_scope_tokens_from_text(avoid_text)
            exact_match = avoid_text.lower() in action_lower
            if not exact_match and not avoid_tokens:
                continue
            token_overlap = sorted(action_tokens & avoid_tokens)
            if not exact_match and len(token_overlap) < min(2, len(avoid_tokens)):
                continue
            matches.append(
                {
                    "generated_at": lesson.get("generated_at"),
                    "decision": lesson.get("decision"),
                    "kind": lesson.get("kind"),
                    "summary": lesson.get("summary"),
                    "reward_id": lesson.get("reward_id"),
                    "strength": lesson.get("strength") or "advisory",
                    "scope": lesson.get("scope") or "goal",
                    "avoid": avoid_text,
                    "token_overlap": token_overlap[:5],
                }
            )
    if not matches:
        return None
    return {
        "schema_version": "reward_lesson_projection_warning_v0",
        "source": "goal_reward_event_ledger",
        "goal_id": goal_id,
        "message": (
            "recommended_action overlaps a recent human_reward lesson avoid rule; "
            "rebase the route or update the affected todo/next action before continuing"
        ),
        "recommended_action": action,
        "match_count": len(matches),
        "matches": matches[:3],
    }
