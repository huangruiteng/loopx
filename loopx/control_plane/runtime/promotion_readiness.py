from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


PROMOTION_READINESS_PROXY_NOTE = (
    "canary promotion-readiness projection from append-only run history; exact evidence stays in run artifacts"
)

ParseTimestamp = Callable[[Any], Any]
FreshnessBuilder = Callable[[dict[str, Any]], dict[str, Any]]
LatestReadinessEvent = Callable[[Path], dict[str, Any]]


def build_promotion_readiness_summary(
    history: dict[str, Any],
    *,
    parse_timestamp: ParseTimestamp,
    readiness_classifications: set[str],
    add_promotion_readiness_freshness: FreshnessBuilder,
    latest_promotion_readiness_event: LatestReadinessEvent,
    freshness_hours: int,
    runtime_root: Path | None = None,
    proxy_note: str = PROMOTION_READINESS_PROXY_NOTE,
) -> dict[str, Any]:
    latest: dict[str, Any] | None = None
    latest_at = None
    sample_count = 0
    source = "run_history"
    for run in history.get("runs") or []:
        if not isinstance(run, dict):
            continue
        classification = str(run.get("classification") or "")
        if classification not in readiness_classifications:
            continue
        sample_count += 1
        generated_at = parse_timestamp(run.get("generated_at"))
        if generated_at is None:
            continue
        if latest_at is None or generated_at > latest_at:
            latest_at = generated_at
            latest = run

    if latest is None and runtime_root is not None:
        full_scan_latest = latest_promotion_readiness_event(runtime_root)
        if full_scan_latest.get("available"):
            latest = full_scan_latest
            source = "run_history_full_scan"

    if latest is None:
        readiness = add_promotion_readiness_freshness(
            {
                "available": False,
                "source": source,
                "reason": (
                    "no canary promotion readiness run found in full run history"
                    if runtime_root is not None
                    else "no canary promotion readiness run found in sampled history"
                ),
            }
        )
    else:
        readiness = add_promotion_readiness_freshness(
            {
                "available": True,
                "source": source,
                "goal_id": latest.get("goal_id"),
                "generated_at": latest.get("generated_at"),
                "classification": latest.get("classification"),
                "delivery_batch_scale": latest.get("delivery_batch_scale"),
                "delivery_outcome": latest.get("delivery_outcome"),
                "recommended_action": latest.get("recommended_action"),
                "json_exists": bool(latest.get("json_exists")),
                "markdown_exists": bool(latest.get("markdown_exists")),
            }
        )
    readiness.update(
        {
            "sample_run_count": sample_count,
            "proxy_note": proxy_note,
            "freshness_window_hours": freshness_hours,
        }
    )
    return readiness
