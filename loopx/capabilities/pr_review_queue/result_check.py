"""Check a review's declared evidence for consistency, never its truth."""

from collections.abc import Mapping
from typing import Any

from .review_contract import build_review_execution_contract, build_review_plan


def _missing(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _require_fields(
    blockers: list[str],
    *,
    evidence_id: str,
    value: object,
    fields: object,
    location: str = "",
) -> None:
    if not isinstance(fields, list):
        return
    if not isinstance(value, Mapping):
        blockers.append(f"{evidence_id}:{location or 'value'}_not_object")
        return
    for field in fields:
        if not isinstance(field, str) or _missing(value.get(field)):
            prefix = f"{location}:" if location else ""
            blockers.append(f"{evidence_id}:{prefix}missing_field:{field}")


def _require_items(
    blockers: list[str],
    *,
    evidence_id: str,
    row: Mapping[str, Any],
    requirement: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    items_field = requirement.get("items_field")
    if not isinstance(items_field, str):
        return []
    raw_items = row.get(items_field)
    if not isinstance(raw_items, list):
        blockers.append(f"{evidence_id}:missing_or_invalid_items")
        return []
    count = requirement.get("item_count")
    if isinstance(count, Mapping):
        minimum = count.get("minimum")
        maximum = count.get("maximum")
        if type(minimum) is int and len(raw_items) < minimum:
            blockers.append(f"{evidence_id}:too_few_items")
        if type(maximum) is int and len(raw_items) > maximum:
            blockers.append(f"{evidence_id}:too_many_items")
    items: list[Mapping[str, Any]] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, Mapping):
            blockers.append(f"{evidence_id}:items[{index}]_not_object")
            continue
        items.append(item)
        _require_fields(
            blockers,
            evidence_id=evidence_id,
            value=item,
            fields=requirement.get("item_fields"),
            location=f"items[{index}]",
        )
    return items


def _required_validation_case_ids(
    requirement: Mapping[str, Any],
    applicability: Mapping[str, Any],
) -> set[str]:
    required: set[str] = set()
    cases = requirement.get("required_cases")
    if not isinstance(cases, list):
        return required
    for case in cases:
        if not isinstance(case, Mapping):
            continue
        case_id = case.get("case_id")
        condition = case.get("required_when")
        if not isinstance(case_id, str):
            continue
        if condition == "always" or (
            isinstance(condition, str) and applicability.get(condition) is True
        ):
            required.add(case_id)
    return required


def check_review_result(
    packet: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    target = result.get("target_exact_head")
    items = packet.get("pull_requests")
    if not isinstance(items, list):
        raise TypeError("review packet must contain pull_requests")
    matches = [
        item
        for item in items
        if isinstance(item, Mapping)
        and build_review_plan(item)["target"]["exact_head_key"] == target
        and target is not None
    ]
    if len(matches) != 1:
        raise ValueError("review result must match exactly one packet PR head")
    if not str(matches[0].get("review_action_kind") or "").strip():
        raise ValueError(
            "review result cannot execute an inventory-only exact head; regenerate "
            "the packet with an explicit fresh-audit request"
        )
    # Rebuild policy from this installed capability, not caller-supplied plans.
    plan = build_review_plan(matches[0])
    applicability = plan.get("applicability")
    if not isinstance(applicability, Mapping):
        applicability = {}
    contract = build_review_execution_contract()
    requirements = {
        row["evidence_id"]: row for row in contract["evidence_requirements"]
    }
    blockers: list[str] = []
    errors: list[str] = []
    revision = result.get("review_policy_revision")
    if type(revision) is not int or revision != contract["policy_revision"]:
        blockers.append("review_policy_revision:stale_or_missing")
    if result.get("schema_version") != "pull_request_review_result_v1":
        errors.append("unsupported_result_schema")
    evidence = result.get("evidence")
    if not isinstance(evidence, Mapping):
        evidence = {}
        errors.append("evidence_not_object")
    for key in plan["required_evidence_ids"]:
        row = evidence.get(key)
        if not isinstance(row, Mapping):
            blockers.append(f"{key}:missing")
            continue
        status = row.get("status")
        if status != "verified":
            blockers.append(f"{key}:not_verified")
        if status not in contract["evidence_status_values"]:
            errors.append(f"{key}:invalid_status")
        detail = {k: v for k, v in row.items() if k not in {"status", "verdict"}}
        if not any(v not in (None, "", [], {}) for v in detail.values()):
            blockers.append(f"{key}:missing_evidence_detail")
        if status == "verified":
            requirement = requirements[key]
            _require_fields(
                blockers,
                evidence_id=key,
                value=row,
                fields=requirement.get("fields"),
            )
            items = _require_items(
                blockers,
                evidence_id=key,
                row=row,
                requirement=requirement,
            )
            positive_field = requirement.get("positive_field")
            if isinstance(positive_field, str):
                _require_fields(
                    blockers,
                    evidence_id=key,
                    value=row.get(positive_field),
                    fields=requirement.get("positive_fields"),
                    location=positive_field,
                )
            negative_field = requirement.get("negative_field")
            if (
                isinstance(negative_field, str)
                and applicability.get("negative_walkthrough_required") is True
            ):
                _require_fields(
                    blockers,
                    evidence_id=key,
                    value=row.get(negative_field),
                    fields=requirement.get("negative_fields"),
                    location=negative_field,
                )
            required_cases = _required_validation_case_ids(requirement, applicability)
            if required_cases:
                observed_cases = {
                    str(item.get("case_id"))
                    for item in items
                    if isinstance(item.get("case_id"), str)
                }
                for case_id in sorted(required_cases - observed_cases):
                    blockers.append(f"{key}:missing_required_case:{case_id}")
        allowed = requirements[key].get("verdict_values")
        if allowed and row.get("verdict") not in allowed:
            blockers.append(f"{key}:missing_or_invalid_verdict")
        rejected = contract["completion_gate"]["blocking_evidence_verdicts"].get(
            key, []
        )
        if row.get("verdict") in rejected:
            blockers.append(f"{key}:blocking_verdict")
    findings = result.get("findings")
    if not isinstance(findings, list):
        errors.append("findings_not_array")
    else:
        for finding in findings:
            if not isinstance(finding, Mapping):
                errors.append("finding_not_object")
                continue
            severity = finding.get("severity")
            if "blocking" in finding and not isinstance(finding["blocking"], bool):
                errors.append("invalid_finding_blocking_flag")
            if severity not in {"P0", "P1", "P2", "P3"}:
                errors.append("invalid_finding_severity")
            if finding.get("blocking") is True or severity in {"P0", "P1"}:
                blockers.append("unresolved_blocking_finding")
    verdict = result.get("verdict")
    if verdict not in {"APPROVE", "REQUEST_CHANGES"}:
        errors.append("unsupported_verdict")
    if verdict == "APPROVE" and blockers:
        errors.append("approval_contradicts_evidence")
    return {
        "ok": not errors,
        "schema_version": "pull_request_review_result_check_v0",
        "target_exact_head": target,
        "verdict": verdict,
        "approval_consistent": not errors and not blockers,
        "errors": sorted(set(errors)),
        "approval_blockers": sorted(set(blockers)),
        "evidence_truth_verified": False,
        "remote_head_verified": False,
        "external_writes_performed": False,
    }
