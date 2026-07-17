from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ...domain_packs.issue_fix import (
    persist_issue_fix_reviewer_notification_state,
)
from .cli_input import load_jsonl_rows
from .reviewer_notification import (
    CommandRunner,
    NotificationSinkAdapter,
    build_issue_fix_reviewer_notification_sinks_result,
    reviewer_notification_idempotency_key,
    reviewer_notification_legacy_queue_from_state,
    reviewer_notification_queue_from_state,
    reviewer_notification_receipts_from_state,
    with_reviewer_notification_state,
)
from .reviewer_request import fetch_issue_fix_reviewer_notification_metadata


ISSUE_FIX_REVIEWER_NOTIFICATION_DRAIN_SCHEMA_VERSION = (
    "issue_fix_reviewer_notification_drain_v0"
)
MetadataLoader = Callable[..., tuple[Optional[dict[str, Any]], Optional[str]]]


def _parse_timestamp(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("delivery_observed_at must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("delivery_observed_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _latest_lifecycle_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in rows:
        observation = raw.get("observation")
        if not isinstance(observation, Mapping):
            continue
        repo = str(observation.get("repo") or "").strip()
        pr_ref = str(observation.get("pr_ref") or "").strip()
        if repo and pr_ref:
            latest[(repo, pr_ref)] = dict(raw)
    return list(latest.values())


def _queue_due(receipt: Mapping[str, Any], observed_at: datetime) -> bool:
    try:
        not_before = _parse_timestamp(str(receipt.get("not_before") or ""))
    except ValueError:
        return False
    return not_before <= observed_at


def _queued_delivery_window(
    queue: Sequence[Mapping[str, Any]], observed_at: datetime
) -> tuple[dict[str, Any] | None, str | None]:
    windows: set[tuple[str, str, str]] = set()
    for receipt in queue:
        allowed = receipt.get("allowed_local_time")
        if not isinstance(allowed, Mapping):
            return None, "reviewer_notification_queue_delivery_window_invalid"
        windows.add(
            (
                str(receipt.get("timezone") or ""),
                str(allowed.get("start") or ""),
                str(allowed.get("end") or ""),
            )
        )
    if len(windows) != 1:
        return None, "reviewer_notification_queue_delivery_window_mismatch"
    timezone_name, start_text, end_text = windows.pop()
    try:
        location = ZoneInfo(timezone_name)
        start = time.fromisoformat(start_text)
        end = time.fromisoformat(end_text)
    except (ValueError, ZoneInfoNotFoundError):
        return None, "reviewer_notification_queue_delivery_window_invalid"
    if start == end:
        return None, "reviewer_notification_queue_delivery_window_invalid"
    current = observed_at.astimezone(location).timetz().replace(tzinfo=None)
    allowed_now = (
        start <= current < end if start < end else current >= start or current < end
    )
    return {
        "timezone": timezone_name,
        "allowed_local_time": {"start": start_text, "end": end_text},
        "outside_window": "queue_without_send",
        "allowed_now": allowed_now,
    }, None


def _matching_sinks(
    *,
    sinks_input: Mapping[str, Any],
    repo: str,
    number: int,
    queue: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    queued_keys = {str(receipt.get("idempotency_key") or "") for receipt in queue}
    matches: list[dict[str, Any]] = []
    for raw_sink in sinks_input.get("sinks") or []:
        if not isinstance(raw_sink, Mapping):
            continue
        sink = dict(raw_sink)
        sink_kind = str(sink.get("sink_kind") or "").strip()
        sink_instance_key = str(sink.get("sink_instance_key") or "").strip()
        for receipt in queue:
            reviewers = receipt.get("reviewer_handles")
            reviewers = reviewers if isinstance(reviewers, list) else []
            try:
                key = reviewer_notification_idempotency_key(
                    repo=repo,
                    pr_number=number,
                    sink_kind=sink_kind,
                    sink_instance_key=sink_instance_key,
                    reviewer_handles=reviewers,
                )
            except (TypeError, ValueError):
                continue
            if key in queued_keys and key == receipt.get("idempotency_key"):
                matches.append(sink)
                break
    return matches


def _matched_queue_keys(
    *,
    sinks_input: Mapping[str, Any],
    repo: str,
    number: int,
    queue: Sequence[Mapping[str, Any]],
) -> set[str]:
    keys: set[str] = set()
    for sink in _matching_sinks(
        sinks_input=sinks_input,
        repo=repo,
        number=number,
        queue=queue,
    ):
        sink_kind = str(sink.get("sink_kind") or "").strip()
        sink_instance_key = str(sink.get("sink_instance_key") or "").strip()
        for receipt in queue:
            reviewers = receipt.get("reviewer_handles")
            reviewers = reviewers if isinstance(reviewers, list) else []
            try:
                key = reviewer_notification_idempotency_key(
                    repo=repo,
                    pr_number=number,
                    sink_kind=sink_kind,
                    sink_instance_key=sink_instance_key,
                    reviewer_handles=reviewers,
                )
            except (TypeError, ValueError):
                continue
            if key == receipt.get("idempotency_key"):
                keys.add(key)
                break
    return keys


def _retarget_queue_receipts(
    *,
    repo: str,
    number: int,
    queue: Sequence[Mapping[str, Any]],
    sinks: Sequence[Mapping[str, Any]],
    reviewer_handles: Sequence[str],
) -> list[dict[str, Any]]:
    retargeted: list[dict[str, Any]] = []
    for receipt in queue:
        prior_reviewers = receipt.get("reviewer_handles")
        prior_reviewers = prior_reviewers if isinstance(prior_reviewers, list) else []
        matching_sink: Mapping[str, Any] | None = None
        for sink in sinks:
            key = reviewer_notification_idempotency_key(
                repo=repo,
                pr_number=number,
                sink_kind=str(sink.get("sink_kind") or "").strip(),
                sink_instance_key=str(sink.get("sink_instance_key") or "").strip(),
                reviewer_handles=prior_reviewers,
            )
            if key == receipt.get("idempotency_key"):
                matching_sink = sink
                break
        if matching_sink is None:
            raise ValueError("queued reviewer notification sink is unavailable")
        retargeted.append(
            {
                **dict(receipt),
                "idempotency_key": reviewer_notification_idempotency_key(
                    repo=repo,
                    pr_number=number,
                    sink_kind=str(matching_sink.get("sink_kind") or "").strip(),
                    sink_instance_key=str(
                        matching_sink.get("sink_instance_key") or ""
                    ).strip(),
                    reviewer_handles=reviewer_handles,
                ),
                "reviewer_handles": list(reviewer_handles),
            }
        )
    return retargeted


def drain_issue_fix_reviewer_notification_queue(
    *,
    ledger_path: str | Path,
    sinks_input: Mapping[str, Any],
    execute: bool = False,
    delivery_observed_at: str | None = None,
    limit: int = 20,
    runner: CommandRunner | None = None,
    metadata_loader: MetadataLoader = fetch_issue_fix_reviewer_notification_metadata,
    sink_adapters: Mapping[str, NotificationSinkAdapter] | None = None,
) -> dict[str, Any]:
    """Drain one bounded state-group batch with one PR in each sink message."""

    if not 1 <= int(limit) <= 100:
        raise ValueError("reviewer notification drain limit must be between 1 and 100")
    observed_at = _parse_timestamp(delivery_observed_at)
    observed_text = observed_at.isoformat().replace("+00:00", "Z")
    path = Path(ledger_path)
    rows = _latest_lifecycle_rows(load_jsonl_rows(path) if path.is_file() else [])
    legacy_queue_count = sum(
        len(reviewer_notification_legacy_queue_from_state(row)) for row in rows
    )
    if legacy_queue_count:
        return {
            "ok": False,
            "schema_version": ISSUE_FIX_REVIEWER_NOTIFICATION_DRAIN_SCHEMA_VERSION,
            "mode": "issue-fix-reviewer-notification-drain",
            "status": "blocked",
            "blocker": "reviewer_notification_queue_v1_migration_required",
            "execute": execute,
            "delivery_observed_at": observed_text,
            "grouping_scope": "review_required_state_bucket",
            "monitor_granularity": "one_monitor_per_state_bucket",
            "notification_granularity": "one_pr_per_message",
            "legacy_queue_receipt_count": legacy_queue_count,
            "queued_receipt_count": 0,
            "due_pr_count": 0,
            "processed_pr_count": 0,
            "not_due_receipt_count": 0,
            "verified_pr_count": 0,
            "cancelled_pr_count": 0,
            "cancelled_sink_receipt_count": 0,
            "held_pr_count": 0,
            "blocked_pr_count": 1,
            "items": [],
            "external_reads_performed": False,
            "external_writes_performed": False,
            "state_write_performed": False,
            "private_destination_captured": False,
            "private_member_ids_captured": False,
            "private_bot_profile_captured": False,
            "raw_provider_payload_captured": False,
            "local_paths_captured": False,
        }
    queued_rows: list[tuple[datetime, str, int, dict[str, Any]]] = []
    queued_count = 0
    not_due_count = 0
    for row in rows:
        queue = reviewer_notification_queue_from_state(row)
        if not queue:
            continue
        queued_count += len(queue)
        due = [receipt for receipt in queue if _queue_due(receipt, observed_at)]
        not_due_count += len(queue) - len(due)
        if not due:
            continue
        observation = row.get("observation")
        observation = observation if isinstance(observation, Mapping) else {}
        number = observation.get("number")
        repo = str(observation.get("repo") or "")
        if not isinstance(number, int) or not repo:
            continue
        first_due = min(_parse_timestamp(str(item["not_before"])) for item in due)
        queued_rows.append((first_due, repo, number, row))
    queued_rows.sort(key=lambda value: (value[0], value[1], value[2]))

    items: list[dict[str, Any]] = []
    write_performed = False
    external_reads = False
    external_writes = False
    blocked_count = 0
    cancelled_count = 0
    cancelled_sink_receipt_count = 0
    verified_count = 0
    held_count = 0
    for _, repo, number, row in queued_rows[: int(limit)]:
        observation = row.get("observation")
        observation = observation if isinstance(observation, Mapping) else {}
        permalink = str(
            observation.get("permalink") or f"https://github.com/{repo}/pull/{number}"
        )
        full_queue = reviewer_notification_queue_from_state(row)
        due_queue = [
            receipt for receipt in full_queue if _queue_due(receipt, observed_at)
        ]
        future_queue = [
            receipt for receipt in full_queue if not _queue_due(receipt, observed_at)
        ]
        original_due_count = len(due_queue)
        matched_keys = _matched_queue_keys(
            sinks_input=sinks_input,
            repo=repo,
            number=number,
            queue=due_queue,
        )
        unmatched_due_queue = [
            receipt
            for receipt in due_queue
            if str(receipt.get("idempotency_key") or "") not in matched_keys
        ]
        due_queue = [
            receipt
            for receipt in due_queue
            if str(receipt.get("idempotency_key") or "") in matched_keys
        ]
        matching_sinks = _matching_sinks(
            sinks_input=sinks_input,
            repo=repo,
            number=number,
            queue=due_queue,
        )
        reviewers = list(
            dict.fromkeys(
                str(handle)
                for receipt in due_queue
                for handle in receipt.get("reviewer_handles") or []
            )
        )
        summaries = list(
            dict.fromkeys(
                str(receipt.get("message_summary") or "") for receipt in due_queue
            )
        )
        reviewer_sets = {
            tuple(str(handle) for handle in receipt.get("reviewer_handles") or [])
            for receipt in due_queue
        }
        item: dict[str, Any] = {
            "repo": repo,
            "pr_ref": f"#{number}",
            "permalink": permalink,
            "reviewer_handles": reviewers,
            "queued_receipt_count": original_due_count,
            "status": "preview_due",
            "live_state_verified": False,
            "notification_verified": False,
            "external_write_performed": False,
            "queue_write_performed": False,
        }
        if unmatched_due_queue:
            item["stale_sink_receipt_count"] = len(unmatched_due_queue)
            if execute:
                try:
                    write = persist_issue_fix_reviewer_notification_state(
                        ledger_path,
                        row,
                        receipts=[],
                        queued_receipts=[*future_queue, *due_queue],
                        replace_queued_receipts=True,
                    )
                except (OSError, ValueError):
                    item.update(
                        status="blocked",
                        blocker="reviewer_notification_state_persistence_failed",
                    )
                    blocked_count += 1
                    items.append(item)
                    continue
                item["queue_write_performed"] = write.get("write_performed") is True
                write_performed = bool(
                    write_performed or write.get("write_performed") is True
                )
                cancelled_sink_receipt_count += len(unmatched_due_queue)
                full_queue = [*future_queue, *due_queue]
        if not due_queue:
            item["status"] = (
                "cancelled_stale_sink" if execute else "preview_cancel_stale_sink"
            )
            if execute:
                cancelled_count += 1
            items.append(item)
            continue
        if len(summaries) != 1 or not summaries[0]:
            item.update(
                status="blocked",
                blocker="reviewer_notification_queue_summary_invalid",
            )
            blocked_count += 1
            items.append(item)
            continue
        if len(reviewer_sets) != 1:
            item.update(
                status="blocked",
                blocker="reviewer_notification_queue_reviewer_set_mismatch",
            )
            blocked_count += 1
            items.append(item)
            continue
        delivery_policy, delivery_policy_error = _queued_delivery_window(
            due_queue, observed_at
        )
        if delivery_policy is None:
            item.update(status="blocked", blocker=delivery_policy_error)
            blocked_count += 1
            items.append(item)
            continue
        item["message_summary"] = summaries[0]
        item["queued_delivery_window_honored"] = True
        if delivery_policy["allowed_now"] is not True:
            item["status"] = "held_outside_delivery_window"
            held_count += 1
            items.append(item)
            continue
        if not execute:
            items.append(item)
            continue

        external_reads = True
        kwargs: dict[str, Any] = {"repo": repo, "number": number}
        if runner is not None:
            kwargs["runner"] = runner
        metadata, metadata_error = metadata_loader(**kwargs)
        if metadata is None:
            item.update(
                status="blocked",
                blocker=metadata_error or "github_pr_metadata_unavailable",
            )
            blocked_count += 1
            items.append(item)
            continue
        live_state = str(metadata.get("state") or "UNKNOWN").upper()
        live_review_decision = str(metadata.get("review_decision") or "UNKNOWN").upper()
        live_state_bucket = str(metadata.get("state_bucket") or "unknown")
        live_reviewed = {str(value) for value in metadata.get("reviewed_by") or []}
        if not all(
            field in metadata
            for field in ("requested_reviewers", "comment_notified_reviewers")
        ):
            item.update(
                status="blocked",
                blocker="github_pr_live_reviewer_coverage_incomplete",
            )
            blocked_count += 1
            items.append(item)
            continue
        live_active_coverage = {
            str(value)
            for field in ("requested_reviewers", "comment_notified_reviewers")
            for value in metadata.get(field) or []
        }
        item.update(
            live_state=live_state,
            live_review_decision=live_review_decision,
            live_state_bucket=live_state_bucket,
            live_state_verified=True,
        )
        if live_state == "UNKNOWN" or live_review_decision == "UNKNOWN":
            item.update(
                status="blocked",
                blocker="github_pr_live_state_incomplete",
            )
            blocked_count += 1
            items.append(item)
            continue
        stale_reason = None
        if live_state != "OPEN":
            stale_reason = "pr_not_open"
        elif metadata.get("is_draft") is True:
            stale_reason = "pr_is_draft"
        elif live_review_decision != "REVIEW_REQUIRED":
            stale_reason = "review_no_longer_required"
        elif reviewers and set(reviewers).issubset(live_reviewed):
            stale_reason = "all_queued_reviewers_already_reviewed"
        elif reviewers and not set(reviewers).intersection(live_active_coverage):
            stale_reason = "all_queued_reviewers_no_longer_active"
        if stale_reason:
            try:
                write = persist_issue_fix_reviewer_notification_state(
                    ledger_path,
                    row,
                    receipts=[],
                    queued_receipts=[],
                    replace_queued_receipts=True,
                )
            except (OSError, ValueError):
                item.update(
                    status="blocked",
                    blocker="reviewer_notification_state_persistence_failed",
                )
                blocked_count += 1
            else:
                item.update(
                    status="cancelled_stale",
                    cancellation_reason=stale_reason,
                    queue_write_performed=write.get("write_performed") is True,
                )
                cancelled_count += 1
                write_performed = bool(
                    write_performed or write.get("write_performed") is True
                )
            items.append(item)
            continue
        covered_reviewers = [reviewer for reviewer in reviewers if reviewer in live_reviewed]
        inactive_reviewers = [
            reviewer
            for reviewer in reviewers
            if reviewer not in live_reviewed and reviewer not in live_active_coverage
        ]
        reviewers = [
            reviewer
            for reviewer in reviewers
            if reviewer not in live_reviewed and reviewer in live_active_coverage
        ]
        item["reviewer_handles"] = reviewers
        if covered_reviewers:
            item["covered_reviewer_handles"] = covered_reviewers
        if inactive_reviewers:
            item["inactive_reviewer_handles"] = inactive_reviewers
        try:
            due_queue = _retarget_queue_receipts(
                repo=repo,
                number=number,
                queue=due_queue,
                sinks=matching_sinks,
                reviewer_handles=reviewers,
            )
        except ValueError:
            item.update(
                status="blocked",
                blocker="reviewer_notification_queue_sink_mismatch",
            )
            blocked_count += 1
            items.append(item)
            continue
        full_queue = [*future_queue, *due_queue]
        author = str(metadata.get("author_handle") or "")
        if not author or author in reviewers:
            item.update(
                status="blocked",
                blocker=(
                    "reviewer_notification_author_unavailable"
                    if not author
                    else "reviewer_notification_author_exclusion_failed"
                ),
            )
            blocked_count += 1
            items.append(item)
            continue

        scoped_input = with_reviewer_notification_state(
            {
                **dict(sinks_input),
                "sinks": matching_sinks,
                "delivery_policy": {
                    "timezone": delivery_policy["timezone"],
                    "allowed_local_time": delivery_policy["allowed_local_time"],
                    "outside_window": "queue_without_send",
                },
            },
            reviewer_notification_receipts_from_state(row),
            full_queue,
        )
        build_kwargs: dict[str, Any] = {
            "repo": repo,
            "pr_number": number,
            "pr_url": permalink,
            "pr_title": summaries[0],
            "linked_issue_refs": metadata.get("linked_issue_refs") or [],
            "author_handle": author,
            "reviewer_handles": reviewers,
            "sinks_input": scoped_input,
            "reviewer_artifact_required": False,
            "execute": True,
            "delivery_observed_at": observed_text,
            "sink_adapters": sink_adapters,
        }
        if runner is not None:
            build_kwargs["runner"] = runner
        result = build_issue_fix_reviewer_notification_sinks_result(**build_kwargs)
        result_queue = result.get("queued_receipts")
        result_queue = result_queue if isinstance(result_queue, list) else []
        new_queue = [dict(value) for value in future_queue]
        new_queue.extend(
            dict(value) for value in result_queue if isinstance(value, Mapping)
        )
        receipts = result.get("receipts")
        receipts = receipts if isinstance(receipts, list) else []
        try:
            write = persist_issue_fix_reviewer_notification_state(
                ledger_path,
                row,
                receipts=[str(value) for value in receipts],
                queued_receipts=new_queue,
                replace_queued_receipts=True,
            )
        except (OSError, ValueError):
            item.update(
                status="blocked",
                blocker="reviewer_notification_state_persistence_failed",
            )
            blocked_count += 1
        else:
            item.update(
                status=str(result.get("status") or "blocked"),
                notification_verified=result.get("notification_verified") is True,
                external_write_performed=(
                    result.get("external_writes_performed") is True
                ),
                queue_write_performed=write.get("write_performed") is True,
            )
            if result.get("blocker"):
                item["blocker"] = result["blocker"]
            if result.get("ok") is not True:
                blocked_count += 1
            if result.get("notification_verified") is True:
                verified_count += 1
            external_writes = bool(
                external_writes or result.get("external_writes_performed") is True
            )
            write_performed = bool(
                write_performed or write.get("write_performed") is True
            )
        items.append(item)

    if not execute:
        status = "preview_due" if queued_rows else "no_due_notifications"
    elif blocked_count:
        status = "partial_failure" if len(items) > blocked_count else "blocked"
    elif verified_count:
        status = "drained_verified"
    elif cancelled_count:
        status = "cancelled_stale"
    elif held_count:
        status = "held_outside_delivery_window"
    else:
        status = "no_due_notifications"
    return {
        "ok": blocked_count == 0,
        "schema_version": ISSUE_FIX_REVIEWER_NOTIFICATION_DRAIN_SCHEMA_VERSION,
        "mode": "issue-fix-reviewer-notification-drain",
        "status": status,
        "execute": execute,
        "delivery_observed_at": observed_text,
        "grouping_scope": "review_required_state_bucket",
        "monitor_granularity": "one_monitor_per_state_bucket",
        "notification_granularity": "one_pr_per_message",
        "queued_receipt_count": queued_count,
        "due_pr_count": len(queued_rows),
        "processed_pr_count": len(items),
        "not_due_receipt_count": not_due_count,
        "verified_pr_count": verified_count,
        "cancelled_pr_count": cancelled_count,
        "cancelled_sink_receipt_count": cancelled_sink_receipt_count,
        "held_pr_count": held_count,
        "blocked_pr_count": blocked_count,
        "items": items,
        "external_reads_performed": external_reads,
        "external_writes_performed": external_writes,
        "state_write_performed": write_performed,
        "private_destination_captured": False,
        "private_member_ids_captured": False,
        "private_bot_profile_captured": False,
        "raw_provider_payload_captured": False,
        "local_paths_captured": False,
    }
