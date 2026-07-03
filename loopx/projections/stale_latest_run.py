from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable, Optional


PathResolver = Callable[[Any, dict[str, Any]], Optional[Path]]
FrontmatterParser = Callable[[str], dict[str, str]]
TimestampParser = Callable[[Any], Any]


def active_state_projection_warning(
    goal: dict[str, Any],
    current_run: dict[str, Any] | None,
    *,
    agent_lane_progress_scope: str,
    resolve_goal_local_path: PathResolver,
    parse_state_frontmatter: FrontmatterParser,
    parse_timestamp: TimestampParser,
) -> dict[str, Any] | None:
    if not isinstance(goal, dict) or not goal.get("registry_member") or not isinstance(current_run, dict):
        return None
    state_path = resolve_goal_local_path(goal.get("state_file"), goal)
    if state_path is None or not state_path.exists():
        return None
    try:
        state_text = state_path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter = parse_state_frontmatter(state_text)
    active_updated_at = frontmatter.get("updated_at")
    active_digest = hashlib.sha256(state_text.encode("utf-8")).hexdigest()[:16]
    run_state = current_run.get("state") if isinstance(current_run.get("state"), dict) else {}
    run_frontmatter = run_state.get("frontmatter") if isinstance(run_state.get("frontmatter"), dict) else {}
    run_state_updated_at = run_frontmatter.get("updated_at")
    run_state_digest = str(run_state.get("sha256_16") or "")
    latest_run_generated_at = str(current_run.get("generated_at") or "")

    active_dt = parse_timestamp(active_updated_at)
    run_state_dt = parse_timestamp(run_state_updated_at)
    run_generated_dt = parse_timestamp(latest_run_generated_at)
    active_newer_than_run_state = bool(active_dt and run_state_dt and active_dt > run_state_dt)
    active_newer_than_run = bool(active_dt and run_generated_dt and active_dt > run_generated_dt)
    digest_mismatch = bool(run_state_digest and active_digest != run_state_digest)
    if not (active_newer_than_run_state or active_newer_than_run or digest_mismatch):
        return None
    for run in goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []:
        if not isinstance(run, dict):
            continue
        if str(run.get("progress_scope") or "") != agent_lane_progress_scope:
            continue
        agent_run_state = run.get("state") if isinstance(run.get("state"), dict) else {}
        agent_run_frontmatter = (
            agent_run_state.get("frontmatter")
            if isinstance(agent_run_state.get("frontmatter"), dict)
            else {}
        )
        agent_run_digest = str(agent_run_state.get("sha256_16") or "")
        agent_run_updated_at = agent_run_frontmatter.get("updated_at")
        agent_run_state_dt = parse_timestamp(agent_run_updated_at)
        agent_run_generated_dt = parse_timestamp(str(run.get("generated_at") or ""))
        if agent_run_digest and agent_run_digest == active_digest:
            return None
        if active_dt and agent_run_state_dt and active_dt <= agent_run_state_dt:
            return None
        if active_dt and not agent_run_state_dt and agent_run_generated_dt and active_dt <= agent_run_generated_dt:
            return None

    reasons: list[str] = []
    if active_newer_than_run:
        reasons.append("active_state_updated_after_latest_run")
    if active_newer_than_run_state:
        reasons.append("active_state_updated_after_latest_run_snapshot")
    if digest_mismatch:
        reasons.append("active_state_digest_differs_from_latest_run_snapshot")

    return {
        "kind": "stale_latest_run_projection",
        "source": "active_state_vs_latest_run",
        "severity": "warning",
        "requires_refresh_state": True,
        "reason": ",".join(reasons),
        "active_state_updated_at": active_updated_at,
        "latest_run_generated_at": latest_run_generated_at,
        "latest_run_state_updated_at": run_state_updated_at,
        "latest_run_classification": current_run.get("classification"),
        "recommended_action": "run refresh-state before trusting latest_run-derived routing",
    }
