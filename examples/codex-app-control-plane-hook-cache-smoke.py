#!/usr/bin/env python3
"""Smoke-test the Codex App control-plane hook/cache experiment contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs/product/codex-app-control-plane-hook-cache.md"
PRODUCT_INDEX = REPO_ROOT / "docs/product/README.md"


def main() -> int:
    doc = DOC.read_text(encoding="utf-8")
    index = PRODUCT_INDEX.read_text(encoding="utf-8")
    normalized_doc = " ".join(doc.split())

    required_phrases = [
        "Status: experimental design note, default off.",
        "enabled_by_default: false",
        "mode: advisory_hint",
        "host-runtime hint",
        "LoopX remains authoritative",
        "Missing, stale, or mismatched hints fall back to the CLI.",
        "quiet_wait_cache_lab",
        "guard_projection_lab",
        "default_candidate",
        "Evidence Gates",
        "zero false run and zero false quiet-skip decisions",
        "public/private scans",
        "Fallback CLI Path",
        "Keep all delivery, writeback, publication, and quota spend decisions on the existing CLI guard.",
    ]
    for phrase in required_phrases:
        assert phrase in doc or phrase in normalized_doc, phrase

    forbidden_default_claims = [
        "enabled_by_default: true",
        "default enabled",
        "enable automatically",
        "replace quota should-run",
    ]
    lowered = doc.lower()
    for phrase in forbidden_default_claims:
        assert phrase not in lowered, phrase

    assert "codex-app-control-plane-hook-cache.md" in index, "product index link"

    print("codex-app-control-plane-hook-cache-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
