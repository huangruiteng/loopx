from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from loopx.canary.planner import CURRENT_REPO_PROFILES
from loopx.canary.quality_surface_catalog import (
    QUALITY_SURFACE_CATALOG,
    build_quality_surface_catalog_audit,
)


def test_current_high_risk_surfaces_have_no_catalog_drift() -> None:
    audit = build_quality_surface_catalog_audit(
        CURRENT_REPO_PROFILES,
        repo_root=Path(__file__).resolve().parents[2],
    )

    assert audit["ok"] is True
    assert audit["drift_count"] == 0
    assert audit["repository_reference_validation"] == "performed"
    assert audit["classified_surface_count"] == audit["high_risk_profile_count"]
    assert {gap["surface_id"] for gap in audit["gaps"]} == {
        "peer-agent-runtime"
    }
    assert audit["gaps"][0]["layer"] == "model_behavior"


def test_packaged_audit_keeps_classification_without_source_checkout() -> None:
    audit = build_quality_surface_catalog_audit(CURRENT_REPO_PROFILES)

    assert audit["ok"] is True
    assert audit["repository_reference_validation"] == "source_checkout_unavailable"


def test_unclassified_high_risk_profile_is_drift() -> None:
    profiles = [*CURRENT_REPO_PROFILES, {"id": "new-risk", "quality_risk": "high"}]

    audit = build_quality_surface_catalog_audit(profiles)

    assert audit["ok"] is False
    assert {
        (item["code"], item.get("canary_profile_id")) for item in audit["drift"]
    } >= {("unclassified_high_risk_profile", "new-risk")}


def test_oracle_cannot_reuse_product_source_as_expected_truth() -> None:
    catalog = deepcopy(QUALITY_SURFACE_CATALOG)
    catalog[0]["semantic_oracle"]["refs"] = [catalog[0]["owner_paths"][0]]

    audit = build_quality_surface_catalog_audit(
        CURRENT_REPO_PROFILES,
        catalog=catalog,
    )

    assert audit["ok"] is False
    assert any(
        item["code"] == "circular_oracle_uses_product_source"
        for item in audit["drift"]
    )


def test_not_applicable_layer_requires_a_reason_but_is_not_a_gap() -> None:
    catalog = deepcopy(QUALITY_SURFACE_CATALOG)
    catalog[0]["layers"]["model_behavior"] = {"status": "not_applicable"}

    invalid = build_quality_surface_catalog_audit(
        CURRENT_REPO_PROFILES,
        catalog=catalog,
    )
    assert any(
        item["code"] == "not_applicable_without_rationale"
        for item in invalid["drift"]
    )

    catalog[0]["layers"]["model_behavior"]["rationale"] = (
        "Scheduler precedence is deterministic."
    )
    valid = build_quality_surface_catalog_audit(
        CURRENT_REPO_PROFILES,
        catalog=catalog,
    )
    assert valid["ok"] is True
    assert not any(
        gap["surface_id"] == "interaction-scheduler-authority"
        for gap in valid["gaps"]
    )


def test_same_evidence_cannot_stand_in_for_multiple_layers() -> None:
    catalog = deepcopy(QUALITY_SURFACE_CATALOG)
    shared_ref = catalog[0]["layers"]["durable_smoke"]["refs"][0]
    catalog[0]["layers"]["release_gate"] = {
        "status": "covered",
        "refs": [shared_ref],
    }

    audit = build_quality_surface_catalog_audit(
        CURRENT_REPO_PROFILES,
        catalog=catalog,
    )

    assert any(
        item["code"] == "duplicate_evidence_across_layers"
        for item in audit["drift"]
    )
