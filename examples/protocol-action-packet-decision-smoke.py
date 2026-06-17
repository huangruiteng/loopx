#!/usr/bin/env python3
"""Smoke-test the protocol action packet decision note."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DECISION_DOC = REPO_ROOT / "docs" / "reference" / "protocols" / "protocol-action-packet-decision-v0.md"
WRAPPER_SMOKE = REPO_ROOT / "examples" / "protocol-action-packet-codex-cli-wrapper-smoke.py"


def main() -> None:
    text = DECISION_DOC.read_text(encoding="utf-8")
    wrapper_smoke = WRAPPER_SMOKE.read_text(encoding="utf-8")

    required = [
        "Keep `protocol_action_packet_v0` as the hot-path protocol simplification",
        "`llm=no_api`",
        "Use the Codex CLI wrapper only as an explicit cold-path sidecar experiment.",
        "Defer direct LLM API wiring",
        "should not call Codex CLI",
        "default smoke path fake/no-model",
        "must not persist raw stderr",
        "Terminal-Bench/Harbor execution",
        "environment readiness lane",
    ]
    for needle in required:
        assert needle in text, needle

    assert "--real-codex-cli" in wrapper_smoke
    assert "real_codex_cli_probe" in wrapper_smoke
    assert "fake_codex_cli_contract" in wrapper_smoke
    assert text.index("## Decision") < text.index("## Evidence") < text.index("## Operating Rule")
    assert text.index("## Operating Rule") < text.index("## Next Work")
    print("protocol-action-packet-decision-smoke ok")


if __name__ == "__main__":
    main()
