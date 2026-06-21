#!/usr/bin/env python3
"""Smoke-test the frontstage public/ops surface strategy contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def compact(text: str) -> str:
    return " ".join(text.split())


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing strategy contract: {needle}")


def main() -> int:
    strategy = read("docs/product/frontstage-two-surface-strategy.md")
    product_index = read("docs/product/README.md")
    dashboard_readme = read("apps/dashboard/README.md")
    showcase_note = read("docs/showcases/frontend-surface.md")
    compact_strategy = compact(strategy)
    compact_dashboard_readme = compact(dashboard_readme)
    compact_showcase_note = compact(showcase_note)

    for needle in [
        "Public showcase and homepage",
        "Real ops control plane",
        "`/frontstage` without `mode=ops` belongs to the public showcase surface",
        "`/frontstage?mode=ops&statusUrl=...` belongs to local ops inspection",
        "`docs/showcases/showcase-catalog.json`",
        "`loopx serve-status --global-registry`",
        "The public showcase surface must not read",
        "The ops surface should still default to read-only",
        "Public visual experiments must not depend on live state",
        "showcase mode ignores `statusUrl`",
        "frontstage-private-status-trap.public.json",
        "`GH_FAKE_*` markers",
        "`/frontstage/developer` is a read-only contributor cockpit",
        "Phase 1, public showcase polish",
        "Phase 2, local ops data layer",
        "Phase 3, controlled local write affordances",
    ]:
        assert_contains(strategy, needle)

    for forbidden in [
        "public ops-mode URLs",
        "remote live status service",
        "browser write authority by default",
        "marketing claims without public evidence",
    ]:
        assert_contains(compact_strategy, forbidden)

    assert_contains(product_index, "frontstage-two-surface-strategy.md")
    assert_contains(product_index, "public showcase/homepage surface")
    assert_contains(product_index, "real local ops control-plane")

    for existing_contract in [
        "The default frontstage route is public showcase mode",
        "ignores `statusUrl`",
        "relative or loopback URLs",
        "Do not use ops-mode URLs as public links",
        "Neither surface is browser write authority",
        "frontstage-private-status-trap.public.json",
        "synthetic `GH_FAKE_*` trap markers",
        "developer extension cockpit lives at `/frontstage/developer`",
    ]:
        assert_contains(compact_dashboard_readme, existing_contract)

    for public_source_contract in [
        "The frontend should read `showcase-catalog.json`",
        "Do not render raw run logs",
        "It is a product explanation surface, not the local operator dashboard",
    ]:
        assert_contains(compact_showcase_note, public_source_contract)

    route_row = "| Public showcase and homepage | Explain LoopX"
    ops_row = "| Real ops control plane | Help the operator inspect"
    assert_contains(compact_strategy, compact(route_row))
    assert_contains(compact_strategy, compact(ops_row))
    assert_contains(
        compact_strategy,
        "Ops widgets must not be promoted to public homepage content",
    )
    assert_contains(
        compact_strategy,
        "ops mode accepts only relative or loopback feeds",
    )
    assert_contains(
        compact_strategy,
        "does not change the Codex CLI/TUI loop priority",
    )

    print("frontstage-two-surface-strategy-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
