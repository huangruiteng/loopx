"""Check a review's declared evidence for consistency, never its truth."""

from collections.abc import Mapping
from typing import Any

from .review_contract import build_review_execution_contract, build_review_plan


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
    # Rebuild policy from this installed capability, not caller-supplied plans.
    plan = build_review_plan(matches[0])
    contract = build_review_execution_contract()
    requirements = {
        row["evidence_id"]: row for row in contract["evidence_requirements"]
    }
    blockers: list[str] = []
    errors: list[str] = []
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
