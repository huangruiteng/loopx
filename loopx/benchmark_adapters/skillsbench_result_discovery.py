"""Public-safe SkillsBench result.json discovery helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SKILLSBENCH_RESULT_DISCOVERY_SCHEMA_VERSION = "skillsbench_result_discovery_v0"


def _skillsbench_safe_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def discover_skillsbench_benchflow_result_json(
    search_root: str | Path,
    *,
    expected_result_json: str | Path | None = None,
    task_id: str | None = None,
    rollout_name: str | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    """Find an official SkillsBench/BenchFlow result.json below a safe root.

    The discovery reads only compact official result.json metadata. It does not
    inspect prompts, trajectories, verifier logs, task text, screenshots, or
    credentials. This shared helper keeps CLI ledger ingest aligned with the
    automation-loop reducer when BenchFlow materializes nested result paths.
    """

    root = Path(search_root).expanduser()
    requested_task = str(task_id or "").strip()
    requested_rollout = str(rollout_name or "").strip()

    def base_discovery(status: str, policy: str) -> dict[str, Any]:
        return {
            "schema_version": SKILLSBENCH_RESULT_DISCOVERY_SCHEMA_VERSION,
            "status": status,
            "selection_policy": policy,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
        }

    if root.name == "result.json":
        discovery = base_discovery(
            "found" if root.is_file() else "missing",
            "explicit_result_json",
        )
        discovery["candidate_count"] = 1 if root.is_file() else 0
        if root.is_file():
            discovery["selected_relative_to_root"] = root.name
            discovery["selected_relative_to_job"] = root.name
            return root, discovery
        return None, discovery

    expected = Path(expected_result_json).expanduser() if expected_result_json else None
    if expected is not None and expected.is_file():
        discovery = base_discovery("found", "planned_result_path")
        discovery["candidate_count"] = 1
        discovery["selected_relative_to_root"] = _skillsbench_safe_relative(
            expected,
            root,
        )
        discovery["selected_relative_to_job"] = discovery["selected_relative_to_root"]
        return expected, discovery

    if not root.is_dir():
        discovery = base_discovery("missing", "result_root_scan")
        discovery["candidate_count"] = 0
        return None, discovery

    candidates = sorted(path for path in root.rglob("result.json") if path.is_file())
    ranked: list[tuple[int, float, str, Path, list[str]]] = []
    for candidate in candidates:
        score = 0
        reasons: list[str] = []
        if requested_rollout and candidate.parent.name == requested_rollout:
            score += 100
            reasons.append("parent_matches_requested_rollout")
        elif requested_task and candidate.parent.name.startswith(f"{requested_task}__"):
            score += 30
            reasons.append("parent_matches_task_rollout_prefix")
        try:
            result = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result = {}
        if isinstance(result, dict):
            result_task = str(result.get("task_name") or "")
            if requested_task and result_task == requested_task:
                score += 50
                reasons.append("result_task_matches_request")
            result_rollout = str(result.get("rollout_name") or "")
            if requested_rollout and result_rollout == requested_rollout:
                score += 100
                reasons.append("result_rollout_matches_request")
            elif requested_task and result_rollout.startswith(f"{requested_task}__"):
                score += 20
                reasons.append("result_rollout_matches_task_prefix")
            if not requested_task and not requested_rollout and len(candidates) == 1:
                score += 1
                reasons.append("single_candidate")
        if score <= 0:
            continue
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            mtime = 0.0
        ranked.append((score, mtime, candidate.as_posix(), candidate, reasons))

    if not ranked:
        discovery = base_discovery(
            "ambiguous" if candidates else "missing",
            "result_root_scan_best_match",
        )
        discovery["candidate_count"] = len(candidates)
        discovery["matched_candidate_count"] = 0
        return None, discovery

    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    top_score, _top_mtime, _path_key, selected, reasons = ranked[0]
    tied_top_count = sum(
        1 for score, _mtime, _path, _candidate, _reasons in ranked if score == top_score
    )
    discovery = base_discovery("found", "result_root_scan_best_match")
    discovery.update(
        {
            "tie_breaker": "highest_match_score_then_newest_mtime",
            "candidate_count": len(candidates),
            "matched_candidate_count": len(ranked),
            "top_score_candidate_count": tied_top_count,
            "selected_relative_to_root": _skillsbench_safe_relative(selected, root),
            "selection_reasons": reasons,
        }
    )
    discovery["selected_relative_to_job"] = discovery["selected_relative_to_root"]
    return selected, discovery


