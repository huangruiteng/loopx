#!/usr/bin/env python3
"""Smoke-test the content-ops layout template and acceptance contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def _run(*args: str, check: bool = True) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def _measurement(*, sparse_page: str | None = None) -> dict[str, Any]:
    pages = []
    for index in range(1, 6):
        page_id = f"p{index:02d}"
        if page_id == "p01":
            bottom = 1580
        elif page_id == "p05":
            bottom = 1364
        else:
            bottom = 1470
        if page_id == sparse_page:
            bottom = 700
        pages.append(
            {
                "page_id": page_id,
                "asset_ref": f"images/{page_id}.jpg",
                "canvas": {"width": 1440, "height": 1920},
                "meaningful_content_bounds": {"top": 154, "bottom": bottom},
                "checks": {
                    "overflow": False,
                    "collision": False,
                    "single_character_line": False,
                },
            }
        )
    return {
        "schema_version": "content_ops_layout_measurement_v0",
        "plan_id": "layout:dsh-plugin-scaling:light-serif-longform",
        "template_id": "light-serif-longform",
        "pages": pages,
    }


def main() -> int:
    from loopx.capabilities.content_ops.layout import check_layout_packet

    catalog = _run("content-ops", "template-list")
    assert catalog["ok"] is True, catalog
    assert catalog["template_count"] == 4, catalog
    template_ids = {
        "light-serif-longform",
        "monochrome-editorial",
        "product-brief",
        "control-plane-hybrid",
    }
    assert template_ids == {
        template["template_id"] for template in catalog["templates"]
    }

    for template_id in template_ids:
        built_in = _run(
            "content-ops",
            "template-show",
            "--template-id",
            template_id,
        )
        cover_density = built_in["template"]["density"]["role_overrides"]["cover"]
        assert cover_density == {"min": 0.82, "max": 0.94}, built_in
        assert built_in["template"]["page_sequence"] == {
            "first_role": "cover",
            "density_order": "first_page_maximum",
            "interior_min": 0.72,
        }, built_in

    template = _run(
        "content-ops",
        "template-show",
        "--template-id",
        "light-serif-longform",
    )
    assert template["template"]["canvas"] == {"width": 1440, "height": 1920}
    assert template["template"]["density"]["default_min"] == 0.66

    missing_template = _run(
        "content-ops",
        "template-show",
        "--template-id",
        "missing-template",
        check=False,
    )
    assert missing_template["ok"] is False, missing_template
    assert "unknown content-ops layout template" in missing_template["error"]

    plan_packet = _run(
        "content-ops",
        "layout-plan",
        "--item-id",
        "dsh-plugin-scaling",
        "--template-id",
        "light-serif-longform",
        "--page",
        "p01:cover:dsh",
        "--page",
        "p02:argument:dsh",
        "--page",
        "p03:mechanism:dsh",
        "--page",
        "p04:evidence:dsh",
        "--page",
        "p05:closing:loopx",
        "--required-role",
        "cover",
        "--required-role",
        "argument",
        "--required-role",
        "evidence",
        "--required-role",
        "closing",
        "--closing-role",
        "closing",
        "--generated-at",
        "2026-08-15T12:00:00+08:00",
    )
    assert plan_packet["ok"] is True, plan_packet
    assert plan_packet["plan"]["pages"][-1] == {
        "page_id": "p05",
        "role": "closing",
        "subject_id": "loopx",
    }

    with tempfile.TemporaryDirectory() as tmp:
        plan_path = Path(tmp) / "plan.json"
        measurement_path = Path(tmp) / "measurement.json"
        plan_path.write_text(json.dumps(plan_packet), encoding="utf-8")
        measurement_path.write_text(json.dumps(_measurement()), encoding="utf-8")
        accepted = _run(
            "content-ops",
            "layout-check",
            "--plan-json",
            str(plan_path),
            "--measurement-json",
            str(measurement_path),
        )
    assert accepted["ok"] is True, accepted
    assert accepted["status"] == "pass", accepted
    assert accepted["autopublish_allowed"] is False, accepted

    sparse_cover = _measurement()
    sparse_cover["pages"][0]["meaningful_content_bounds"]["bottom"] = 1475
    rejected_cover = check_layout_packet(plan_packet, sparse_cover)
    assert rejected_cover["status"] == "revise", rejected_cover
    cover_result = rejected_cover["page_results"][0]
    assert cover_result["density"] < 0.82, rejected_cover
    assert {failure["code"] for failure in cover_result["failures"]} == {
        "content_too_sparse"
    }, rejected_cover

    loose_interior = _measurement()
    loose_interior["pages"][1]["meaningful_content_bounds"]["bottom"] = 1280
    rejected_interior = check_layout_packet(plan_packet, loose_interior)
    assert rejected_interior["status"] == "revise", rejected_interior
    interior_result = rejected_interior["page_results"][1]
    assert 0.66 < interior_result["density"] < 0.72, rejected_interior
    assert {failure["code"] for failure in interior_result["failures"]} == {
        "content_too_sparse"
    }, rejected_interior

    denser_interior = _measurement()
    denser_interior["pages"][0]["meaningful_content_bounds"]["bottom"] = 1500
    denser_interior["pages"][1]["meaningful_content_bounds"]["bottom"] = 1520
    rejected_sequence = check_layout_packet(plan_packet, denser_interior)
    assert rejected_sequence["status"] == "revise", rejected_sequence
    assert rejected_sequence["page_results"][1]["status"] == "pass", rejected_sequence
    assert {
        failure["code"] for failure in rejected_sequence["page_results"][0]["failures"]
    } == {"first_page_not_density_maximum"}, rejected_sequence

    # The new defaults accept breathing room previously rejected by the floors.
    readable = _measurement()
    readable["pages"][0]["meaningful_content_bounds"]["bottom"] = 1500
    readable["pages"][1]["meaningful_content_bounds"]["bottom"] = 1364
    assert check_layout_packet(plan_packet, readable)["status"] == "pass"

    # More permissive floors must not allow overcrowding or bypass safety.
    crowded = _measurement()
    crowded["pages"][1]["meaningful_content_bounds"]["bottom"] = 1640
    crowded_result = check_layout_packet(plan_packet, crowded)
    assert "content_too_dense" in {
        f["code"] for f in crowded_result["page_results"][1]["failures"]
    }, crowded_result
    unsafe_layout = _measurement()
    unsafe_layout["pages"][1]["checks"]["overflow"] = True
    assert check_layout_packet(plan_packet, unsafe_layout)["status"] == "revise"

    wrong_first_role = json.loads(json.dumps(plan_packet))
    wrong_first_role["plan"]["pages"][0]["role"] = "argument"
    wrong_first_role["plan"]["pages"][1]["role"] = "cover"
    rejected_first_role = check_layout_packet(wrong_first_role, _measurement())
    assert "first_page_role_mismatch" in {
        failure["code"] for failure in rejected_first_role["failures"]
    }, rejected_first_role

    wrong_plan = _measurement()
    wrong_plan["plan_id"] = "layout:another-item:light-serif-longform"
    mismatched = check_layout_packet(plan_packet, wrong_plan)
    assert mismatched["status"] == "revise", mismatched
    assert "plan_id_mismatch" in {
        failure["code"] for failure in mismatched["failures"]
    }, mismatched

    unsafe = _measurement()
    unsafe["pages"][0]["asset_ref"] = "file:private-page.jpg"
    try:
        check_layout_packet(plan_packet, unsafe)
    except ValueError as exc:
        assert "public-safe relative reference" in str(exc)
    else:
        raise AssertionError("absolute asset_ref was accepted")

    print("content-ops-layout-library-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
