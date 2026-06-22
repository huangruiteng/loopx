#!/usr/bin/env python3
"""Smoke-test the public SWE-Marathon full-suite status catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
JSON_PATH = DOC_DIR / "swe-marathon-full-suite-status-20260622.json"
MD_PATH = DOC_DIR / "swe-marathon-full-suite-status-20260622.md"

FORBIDDEN_PATTERNS = [
    re.compile("/" + "Users/"),
    re.compile("/" + "private/"),
    re.compile(r"\." + "local/"),
    re.compile("trajectory_copied" + r"\"\\s*:\\s*" + "tr" + "ue"),
    re.compile("raw_logs_copied" + r"\"\\s*:\\s*" + "tr" + "ue"),
    re.compile("raw_task_text_copied" + r"\"\\s*:\\s*" + "tr" + "ue"),
    re.compile("verifier_output_copied" + r"\"\\s*:\\s*" + "tr" + "ue"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
]


def assert_public_safe(text: str) -> None:
    for pattern in FORBIDDEN_PATTERNS:
        assert not pattern.search(text), pattern.pattern


def load_catalog() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_catalog_shape() -> None:
    catalog = load_catalog()
    assert catalog["schema_version"] == "swe_marathon_full_suite_status_v0"
    assert catalog["benchmark_id"] == "swe-marathon"
    assert catalog["summary"]["case_count"] == 20
    assert len(catalog["cases"]) == 20
    assert catalog["summary"]["public_ledger_case_count"] == 3
    assert catalog["summary"]["not_started_case_count"] == 17
    assert catalog["summary"]["gpu_required_case_count"] == 4
    assert catalog["selection_policy"]["next_fresh_case"] == (
        "vliw-kernel-optimization"
    )
    assert catalog["selection_policy"]["secondary_fresh_case"] == "wasm-simd"


def test_case_statuses_and_lanes() -> None:
    cases = {case["case_id"]: case for case in load_catalog()["cases"]}
    assert set(cases) == {
        "biofabric-rust-rewrite",
        "embedding-eval",
        "excel-clone",
        "find-network-alignments",
        "jax-pytorch-rewrite",
        "kubernetes-rust-rewrite",
        "mastodon-clone",
        "nextjs-vite-rewrite",
        "parameter-golf",
        "post-train-ifeval",
        "ruby-rust-port",
        "rust-c-compiler",
        "rust-java-lsp",
        "s3-clone",
        "slack-clone",
        "stripe-clone",
        "trimul-cuda",
        "vliw-kernel-optimization",
        "wasm-simd",
        "zstd-decoder",
    }
    assert cases["zstd-decoder"]["public_ledger_status"] == (
        "paired_treatment_regressed"
    )
    assert cases["find-network-alignments"]["public_ledger_status"] == (
        "baseline_failed_treatment_candidate"
    )
    assert cases["rust-c-compiler"]["public_ledger_status"] == (
        "single_arm_recorded"
    )
    gpu_cases = [
        case_id
        for case_id, case in cases.items()
        if str(case["resource_profile"]).startswith("gpu_")
    ]
    assert sorted(gpu_cases) == [
        "embedding-eval",
        "jax-pytorch-rewrite",
        "parameter-golf",
        "trimul-cuda",
    ]
    p0_fresh = [
        case_id
        for case_id, case in cases.items()
        if case["experiment_tier"] == "p0_next_fresh_cpu_no_cua_candidate"
    ]
    assert p0_fresh == ["vliw-kernel-optimization", "wasm-simd"]


def test_public_boundary() -> None:
    catalog_text = JSON_PATH.read_text(encoding="utf-8")
    markdown_text = MD_PATH.read_text(encoding="utf-8")
    assert_public_safe(catalog_text)
    assert_public_safe(markdown_text)
    catalog = load_catalog()
    boundary = catalog["source_boundary"]
    assert boundary == {
        "raw_task_text_copied": False,
        "raw_logs_copied": False,
        "trajectory_copied": False,
        "verifier_output_copied": False,
        "local_paths_recorded": False,
    }
    assert "vliw-kernel-optimization" in markdown_text
    assert "Do not repeat `zstd-decoder` immediately" in markdown_text


if __name__ == "__main__":
    test_catalog_shape()
    test_case_statuses_and_lanes()
    test_public_boundary()
    print("swe-marathon-full-suite-status-smoke ok")
