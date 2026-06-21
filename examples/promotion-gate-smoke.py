#!/usr/bin/env python3
"""Smoke-test the machine-readable promotion-gate JSON contract."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.promotion_gate import build_promotion_gate, render_promotion_gate_markdown  # noqa: E402


GOAL_ID = "loopx-meta"


def write_registry(root: Path) -> tuple[Path, Path]:
    runtime = root / "runtime"
    registry_path = root / "project" / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "loopx-meta",
                        "status": "active-read-only",
                        "repo": str(root / "project"),
                        "state_file": "ACTIVE_GOAL_STATE.md",
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, runtime


def write_readiness_event(runtime: Path, *, generated_at: str, label: str) -> None:
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    json_path = runs_dir / f"{label}.json"
    markdown_path = runs_dir / f"{label}.md"
    json_path.write_text("{}", encoding="utf-8")
    markdown_path.write_text("# readiness\n", encoding="utf-8")
    record = {
        "generated_at": generated_at,
        "goal_id": GOAL_ID,
        "classification": "canary_promotion_readiness_smoke_group",
        "delivery_batch_scale": "multi_surface",
        "delivery_outcome": "primary_goal_outcome",
        "recommended_action": f"fixture {label} readiness",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def assert_missing_gate(registry_path: Path) -> None:
    payload = build_promotion_gate(registry_path=registry_path, runtime_root_override=None)
    assert payload["ok"] is True, payload
    assert payload["gate"] == "promotion_readiness", payload
    assert payload["gate_state"] == "warning", payload
    assert payload["can_promote"] is False, payload
    assert payload["should_warn"] is True, payload
    assert payload["non_blocking"] is True, payload
    assert payload["recommended_action"] == "python3 examples/canary-promotion-readiness-smoke.py", payload
    assert payload["readiness"]["freshness_status"] == "missing", payload
    assert payload["readiness"]["requires_readiness_run"] is True, payload
    assert "warning_message" in payload, payload
    markdown = render_promotion_gate_markdown(payload)
    assert "gate_state: `warning`" in markdown, markdown
    assert "can_promote: `False`" in markdown, markdown


def assert_stale_gate(registry_path: Path, runtime: Path) -> None:
    write_readiness_event(runtime, generated_at="2020-01-01T00:00:00+00:00", label="stale")
    payload = build_promotion_gate(registry_path=registry_path, runtime_root_override=None)
    assert payload["gate_state"] == "warning", payload
    assert payload["can_promote"] is False, payload
    assert payload["should_warn"] is True, payload
    readiness = payload["readiness"]
    assert readiness["freshness_status"] == "stale", payload
    assert readiness["requires_readiness_run"] is True, payload
    assert readiness["classification"] == "canary_promotion_readiness_smoke_group", payload
    assert "promotion-readiness evidence is stale" in payload["warning_message"], payload


def assert_fresh_gate(registry_path: Path, runtime: Path) -> None:
    write_readiness_event(
        runtime,
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        label="fresh",
    )
    payload = build_promotion_gate(registry_path=registry_path, runtime_root_override=None)
    assert payload["gate_state"] == "ready", payload
    assert payload["can_promote"] is True, payload
    assert payload["should_warn"] is False, payload
    assert payload["non_blocking"] is True, payload
    assert payload["recommended_action"] == "promotion readiness is fresh", payload
    assert "warning_message" not in payload, payload
    readiness = payload["readiness"]
    assert readiness["freshness_status"] == "fresh", payload
    assert readiness["requires_readiness_run"] is False, payload
    assert readiness["classification"] == "canary_promotion_readiness_smoke_group", payload
    markdown = render_promotion_gate_markdown(payload)
    assert "gate_state: `ready`" in markdown, markdown
    assert "can_promote: `True`" in markdown, markdown


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-promotion-gate-smoke-") as raw_tmp:
        registry_path, runtime = write_registry(Path(raw_tmp))
        assert_missing_gate(registry_path)
        assert_stale_gate(registry_path, runtime)
        assert_fresh_gate(registry_path, runtime)

    print("promotion-gate-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
