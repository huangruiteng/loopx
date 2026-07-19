from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_AWARE_WAKE_MODEL = "todo_readiness_edge_plus_fixed_retry"
DEFAULT_READINESS_POLL_SECONDS = 2.0


def lane_agent_map(lanes: Iterable[Mapping[str, object]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for lane in lanes:
        lane_id = str(lane.get("lane_id") or "").strip()
        agent_id = str(lane.get("agent_id") or lane_id).strip()
        if lane_id:
            result[lane_id] = agent_id
    return result


def todo_readiness_projection(
    payload: Mapping[str, object],
    *,
    lane_agents: Mapping[str, str],
) -> dict[str, object]:
    todos = payload.get("todos")
    if not isinstance(todos, list):
        return {
            "recognized": False,
            "reason": "todo_projection_missing",
            "mapped_todo_count": 0,
            "runnable_lane_tokens": {},
        }

    lanes_by_agent: dict[str, list[str]] = {}
    for lane_id, agent_id in lane_agents.items():
        lanes_by_agent.setdefault(agent_id, []).append(lane_id)

    goal_todo_count = sum(1 for item in todos if isinstance(item, Mapping))
    mapped_count = 0
    runnable: dict[str, list[str]] = {}
    for raw_item in todos:
        if not isinstance(raw_item, Mapping):
            continue
        claimed_by = str(raw_item.get("claimed_by") or "").strip()
        raw_excluded = raw_item.get("excluded_agents") or []
        excluded_values = (
            raw_excluded
            if isinstance(raw_excluded, (list, tuple, set))
            else [raw_excluded]
        )
        excluded = {
            str(value).strip() for value in excluded_values if str(value).strip()
        }
        target_lanes = lanes_by_agent.get(claimed_by, [])
        if target_lanes:
            mapped_count += 1
        elif not claimed_by and str(
            raw_item.get("task_class") or "advancement_task"
        ).strip() == "advancement_task":
            target_lanes = [
                lane_id
                for lane_id, agent_id in lane_agents.items()
                if agent_id not in excluded
            ]
        else:
            continue
        if (
            raw_item.get("done") is True
            or str(raw_item.get("status") or "open").strip().lower() != "open"
            or raw_item.get("resume_ready") is False
            or claimed_by in excluded
        ):
            continue
        todo_id = str(raw_item.get("todo_id") or raw_item.get("index") or "").strip()
        for lane_id in target_lanes:
            runnable.setdefault(lane_id, []).append(todo_id or "open")

    tokens = {
        lane_id: tuple(sorted(todo_ids))
        for lane_id, todo_ids in runnable.items()
        if todo_ids
    }
    return {
        "recognized": goal_todo_count > 0,
        "reason": "goal_todo_projection" if goal_todo_count else "no_goal_todos",
        "goal_todo_count": goal_todo_count,
        "mapped_todo_count": mapped_count,
        "runnable_lane_tokens": tokens,
    }


def read_todo_readiness(
    *,
    cli_bin: str,
    registry: Path,
    runtime_root: Path,
    goal_id: str,
    lane_agents: Mapping[str, str],
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    command = [
        cli_bin,
        "--format",
        "json",
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime_root),
        "todo",
        "list",
        "--goal-id",
        goal_id,
        "--role",
        "agent",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "recognized": False,
            "reason": "todo_projection_command_failed",
            "error": str(exc),
            "mapped_todo_count": 0,
            "runnable_lane_tokens": {},
        }
    if completed.returncode != 0:
        return {
            "recognized": False,
            "reason": "todo_projection_command_failed",
            "error": (completed.stderr or completed.stdout).strip()[:500],
            "mapped_todo_count": 0,
            "runnable_lane_tokens": {},
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {
            "recognized": False,
            "reason": "todo_projection_invalid_json",
            "error": str(exc),
            "mapped_todo_count": 0,
            "runnable_lane_tokens": {},
        }
    if not isinstance(payload, Mapping):
        return {
            "recognized": False,
            "reason": "todo_projection_invalid_payload",
            "mapped_todo_count": 0,
            "runnable_lane_tokens": {},
        }
    return todo_readiness_projection(payload, lane_agents=lane_agents)


def resolve_initial_wake_plan(
    *,
    lanes: Iterable[Mapping[str, object]],
    cli_bin: str,
    registry: Path,
    runtime_root: Path,
    goal_id: str,
) -> dict[str, object]:
    agents = lane_agent_map(lanes)
    projection = (
        read_todo_readiness(
            cli_bin=cli_bin,
            registry=registry,
            runtime_root=runtime_root,
            goal_id=goal_id,
            lane_agents=agents,
        )
        if goal_id and agents
        else {
            "recognized": False,
            "reason": "goal_or_lane_agent_mapping_missing",
            "mapped_todo_count": 0,
            "runnable_lane_tokens": {},
        }
    )
    tokens = projection.get("runnable_lane_tokens", {})
    return {
        "lane_agents": agents,
        "projection": projection,
        "state_aware": bool(projection.get("recognized")),
        "target_lanes": list(tokens) if isinstance(tokens, Mapping) else [],
    }


def _jsonable_tokens(tokens: Mapping[str, tuple[str, ...]]) -> dict[str, list[str]]:
    return {lane_id: list(value) for lane_id, value in tokens.items()}


def _append_event(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def run_state_aware_wake_loop(
    *,
    cli_bin: str,
    tmux_bin: str,
    registry: Path,
    runtime_root: Path,
    goal_id: str,
    session: str,
    lane_agents: Mapping[str, str],
    initial_projection: Mapping[str, object],
    artifact: Path,
    retry_interval_seconds: float,
    poll_interval_seconds: float = DEFAULT_READINESS_POLL_SECONDS,
) -> None:
    all_lanes = list(lane_agents)
    state_aware = bool(initial_projection.get("recognized"))
    previous_tokens = {
        str(lane_id): tuple(str(item) for item in token)
        for lane_id, token in (
            initial_projection.get("runnable_lane_tokens", {})
            if isinstance(initial_projection.get("runnable_lane_tokens"), Mapping)
            else {}
        ).items()
        if isinstance(token, (list, tuple))
    }
    now = time.monotonic()
    last_wake = {lane_id: now for lane_id in previous_tokens}
    projection_error_active = False
    _append_event(
        artifact,
        {
            "event": "scheduler_started",
            "goal_id": goal_id,
            "mode": STATE_AWARE_WAKE_MODEL if state_aware else "fixed_retry_fallback",
            "runnable_lane_tokens": _jsonable_tokens(previous_tokens),
        },
    )

    retry_interval = max(5.0, float(retry_interval_seconds or 0))
    poll_interval = max(0.5, float(poll_interval_seconds or 0))
    while subprocess.run(
        [tmux_bin, "has-session", "-t", session],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0:
        time.sleep(poll_interval)
        projection = read_todo_readiness(
            cli_bin=cli_bin,
            registry=registry,
            runtime_root=runtime_root,
            goal_id=goal_id,
            lane_agents=lane_agents,
        )
        if projection.get("recognized"):
            state_aware = True
            projection_error_active = False
            raw_tokens = projection.get("runnable_lane_tokens", {})
            if not isinstance(raw_tokens, Mapping):
                raw_tokens = {}
            current_tokens = {
                str(lane_id): tuple(str(item) for item in token)
                for lane_id, token in raw_tokens.items()
                if isinstance(token, (list, tuple))
            }
        elif state_aware:
            if not projection_error_active:
                _append_event(
                    artifact,
                    {
                        "event": "projection_read_failed",
                        "reason": projection.get("reason"),
                        "error": projection.get("error"),
                    },
                )
                projection_error_active = True
            continue
        else:
            current_tokens = {lane_id: ("fallback",) for lane_id in all_lanes}

        now = time.monotonic()
        edge_lanes = [
            lane_id
            for lane_id, token in current_tokens.items()
            if token != previous_tokens.get(lane_id)
        ]
        retry_lanes = [
            lane_id
            for lane_id in current_tokens
            if lane_id not in edge_lanes
            and now - last_wake.get(lane_id, 0.0) >= retry_interval
        ]
        targets = [*edge_lanes, *retry_lanes]
        previous_tokens = current_tokens
        if not targets:
            continue

        command = [
            cli_bin,
            "--format",
            "json",
            "multi-agent",
            "wake",
            "--session-name",
            session,
            "--tmux-bin",
            tmux_bin,
        ]
        for lane_id in targets:
            command.extend(["--lane", lane_id])
        command.append("--execute")
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        try:
            wake_payload: Any = json.loads(completed.stdout)
        except json.JSONDecodeError:
            wake_payload = {
                "ok": False,
                "returncode": completed.returncode,
                "error": (completed.stderr or completed.stdout).strip()[:500],
            }
        _append_event(
            artifact,
            {
                "event": "wake",
                "trigger": "readiness_edge" if edge_lanes else "fixed_retry",
                "target_lanes": targets,
                "runnable_lane_tokens": _jsonable_tokens(current_tokens),
                "wake": wake_payload,
            },
        )
        for lane_id in targets:
            last_wake[lane_id] = now
        if isinstance(wake_payload, Mapping) and wake_payload.get(
            "auto_wake_backoff_recommended"
        ) is True:
            break


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--cli-bin", required=True)
    parser.add_argument("--tmux-bin", required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--goal-id", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--lane-agents-json", required=True)
    parser.add_argument("--initial-projection-json", required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--retry-interval-seconds", type=float, required=True)
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=DEFAULT_READINESS_POLL_SECONDS,
    )
    args = parser.parse_args()
    lane_agents = json.loads(args.lane_agents_json)
    initial_projection = json.loads(args.initial_projection_json)
    if not isinstance(lane_agents, dict) or not isinstance(initial_projection, dict):
        raise ValueError("state-aware wake scheduler requires object projections")
    run_state_aware_wake_loop(
        cli_bin=args.cli_bin,
        tmux_bin=args.tmux_bin,
        registry=args.registry,
        runtime_root=args.runtime_root,
        goal_id=args.goal_id,
        session=args.session,
        lane_agents=lane_agents,
        initial_projection=initial_projection,
        artifact=args.artifact,
        retry_interval_seconds=args.retry_interval_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
