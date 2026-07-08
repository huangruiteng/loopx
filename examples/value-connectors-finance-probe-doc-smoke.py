#!/usr/bin/env python3
"""Smoke-test the public finance connector probe packet."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs" / "capabilities" / "value-connectors" / "finance-market-snapshot-probe.md"
README = ROOT / "docs" / "capabilities" / "value-connectors" / "README.md"
PROTOCOL = ROOT / "docs" / "reference" / "protocols" / "value-connector-plan-v0.md"


def main() -> int:
    packet = PACKET.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    protocol = PROTOCOL.read_text(encoding="utf-8")

    required = [
        "finance_market_snapshot_probe_packet_v0",
        "finance_value_discovery_research_packet_v0",
        "finance_industry_catalyst_discovery_packet_v0",
        "human_decision_owner",
        "judgment_loop",
        "research_stage",
        "trading_stage_out_of_scope",
        "retrospective_validation",
        "pre_catalyst_cutoff",
        "candidate_industry_chains",
        "bottleneck_map",
        "catalyst_timeline",
        "value_drivers",
        "industry_chain_position",
        "mispricing_hypothesis",
        "disconfirming_evidence",
        "missing_evidence",
        "verification_window",
        "Eastmoney public quote endpoint",
        "Futu OpenAPI / OpenD",
        "AKShare",
        "efinance",
        "yfinance",
        "py-futu-api",
        "source_unverified",
        "manual_review_required",
        "non_investment_advice",
        "raw_provider_payload_recorded",
    ]
    for text in required:
        assert text in packet, text

    forbidden_claims = [
        "is an investment advice engine",
        "emits price targets",
        "guarantees returns",
        '"trading_enabled": true',
        "finance-market-snapshot --symbol",
        "latest_price",
        "pct_change",
        "turnover",
    ]
    lower_packet = packet.lower()
    for text in forbidden_claims:
        assert text not in lower_packet, text

    assert "raw provider payloads or raw paid-provider responses" in packet
    assert "account login" in packet and "credentials" in packet
    assert "trading, order placement" in packet
    assert "no-credential probe packet" in readme
    assert "value discovery" in readme.lower()
    assert "judgment building" in readme.lower()
    assert "industry catalyst discovery" in readme.lower()
    assert "retrospective validation" in readme.lower()
    assert "quotes, volume, and short-term moves are out of scope" in readme
    assert "finance-market-snapshot --symbol" not in readme
    assert "finance_market_snapshot_probe_packet_v0" in protocol
    assert "finance_value_discovery_research_packet_v0" in protocol
    assert "finance_industry_catalyst_discovery_packet_v0" in protocol

    print("value-connectors-finance-probe-doc-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
