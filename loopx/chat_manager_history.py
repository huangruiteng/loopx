"""Recent Core delivery receipts, filtered before presentation limits."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from .chat_manager_details import _text
from .control_plane.runtime.run_context_retention import goal_semantic_history_from_runs
from .control_plane.work_items.delivery_outcome import PROGRESS_DELIVERY_OUTCOMES
from .history import STATUS_NEUTRAL_CLASSIFICATIONS, load_index


def read_manager_delivery_history(
    runtime_root: Path, goal_id: str, *, now=None, limit=24
):
    now = now or datetime.now().astimezone()
    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    path = runtime_root / "goals" / goal_id / "runs" / "index.jsonl"
    base = {
        "window_start": start.isoformat(),
        "window_end": now.isoformat(),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "deliveries": [],
    }
    try:
        if not path.is_file():
            raise OSError("missing Core run index")
        before = path.stat()
        runs, raw_count = load_index(path)
        after = path.stat()

        def signature(st):
            return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)

        if signature(before) != signature(after):
            return {
                **base,
                "status": "conflicting",
                "coverage": {"matched": None, "included": 0, "omitted": None},
            }

        rows = []
        invalid = 0
        for run in runs:
            if run.get("classification") in STATUS_NEUTRAL_CLASSIFICATIONS:
                continue
            if run.get("delivery_outcome") not in PROGRESS_DELIVERY_OUTCOMES:
                continue
            try:
                at = datetime.fromisoformat(
                    str(run.get("generated_at")).replace("Z", "+00:00")
                )
                if at.tzinfo is None:
                    raise ValueError("timestamp has no offset")
            except ValueError:
                invalid += 1
                continue
            if not start <= at <= now:
                continue
            if run.get("goal_id") not in (None, goal_id):
                invalid += 1
                continue
            semantic = goal_semantic_history_from_runs([run])
            evidence = any(
                a.get("latest_evidence_delivery_run") for a in semantic["agents"]
            )
            observation = run.get("progress_observation") or {}
            rows.append(
                {
                    "recorded_at": at.isoformat(),
                    "goal_id": goal_id,
                    "agent_id": _text(run.get("agent_id"), 160),
                    "todo_id": _text(run.get("todo_id"), 160),
                    "classification": _text(run.get("classification"), 200),
                    "reported_follow_up": _text(run.get("recommended_action"), 360),
                    "outcome": run["delivery_outcome"],
                    "verification": "core_recorded_evidence_refs"
                    if evidence
                    else "agent_reported_outcome",
                    "evidence_count": len(observation.get("evidence_ids") or []),
                    "source_ref": "sha256:"
                    + hashlib.sha256(
                        json.dumps(run, sort_keys=True).encode()
                    ).hexdigest(),
                }
            )
        rows.sort(key=lambda r: datetime.fromisoformat(r["recorded_at"]), reverse=True)
        included = []
        day_counts = {}
        for row in rows:
            day = (
                datetime.fromisoformat(row["recorded_at"])
                .astimezone(now.tzinfo)
                .date()
                .isoformat()
            )
            day_counts[day] = day_counts.get(day, 0) + 1
            if day_counts[day] <= limit:
                included.append(row)
        return {
            **base,
            "status": "read",
            "source_revision": "sha256:"
            + hashlib.sha256(str(signature(after)).encode()).hexdigest(),
            "deliveries": included,
            "coverage": {
                "index_records": raw_count,
                "matched": len(rows),
                "included": len(included),
                "omitted": len(rows) - len(included),
                "matched_by_day": day_counts,
                "limit_per_day": limit,
                "invalid_delivery_records": invalid,
            },
            "limitations": [
                "Recorded time is not necessarily work time. Agent-reported outcomes are not independent verification.",
                "Evidence references identify receipts; referenced artifacts have not been read.",
            ],
        }
    except (OSError, ValueError, TypeError, KeyError):
        return {
            **base,
            "status": "unavailable",
            "coverage": {"matched": None, "included": 0, "omitted": None},
        }
