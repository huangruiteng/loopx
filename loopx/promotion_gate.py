from __future__ import annotations

from pathlib import Path
from typing import Any

from .doctor import add_promotion_readiness_freshness, latest_promotion_readiness_event
from .history import load_registry
from .paths import resolve_runtime_root


PROMOTION_GATE_ACTION = "python3 examples/canary-promotion-readiness-smoke.py"


def promotion_gate_message(readiness: dict[str, Any]) -> str:
    status = str(readiness.get("freshness_status") or "unknown")
    generated_at = readiness.get("generated_at") or "none"
    age_hours = readiness.get("age_hours")
    reason = readiness.get("reason") or ""
    detail = f"generated_at={generated_at}"
    if age_hours is not None:
        detail += f", age_hours={age_hours}"
    if reason:
        detail += f", reason={reason}"
    return (
        "promotion-readiness evidence is "
        f"{status}; {detail}. This is non-blocking, but before promoting a live "
        "checkout prefer `loopx doctor` and "
        f"`{PROMOTION_GATE_ACTION}`."
    )


def build_promotion_gate(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    readiness = add_promotion_readiness_freshness(
        latest_promotion_readiness_event(runtime_root)
    )
    should_warn = bool(readiness.get("requires_readiness_run"))
    gate_state = "warning" if should_warn else "ready"
    payload = {
        "ok": True,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "gate": "promotion_readiness",
        "gate_state": gate_state,
        "can_promote": not should_warn,
        "should_warn": should_warn,
        "non_blocking": True,
        "recommended_action": PROMOTION_GATE_ACTION if should_warn else "promotion readiness is fresh",
        "readiness": readiness,
    }
    if should_warn:
        payload["warning_message"] = promotion_gate_message(readiness)
    return payload


def render_promotion_gate_markdown(payload: dict[str, Any]) -> str:
    readiness = payload.get("readiness") if isinstance(payload.get("readiness"), dict) else {}
    lines = [
        "# LoopX Promotion Gate",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- gate: `{payload.get('gate')}`",
        f"- gate_state: `{payload.get('gate_state')}`",
        f"- can_promote: `{payload.get('can_promote')}`",
        f"- should_warn: `{payload.get('should_warn')}`",
        f"- non_blocking: `{payload.get('non_blocking')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- freshness_status: `{readiness.get('freshness_status')}`",
        f"- requires_readiness_run: `{readiness.get('requires_readiness_run')}`",
        f"- generated_at: `{readiness.get('generated_at')}`",
        f"- age_hours: `{readiness.get('age_hours')}`",
    ]
    if readiness.get("reason"):
        lines.append(f"- reason: {readiness.get('reason')}")
    if payload.get("warning_message"):
        lines.extend(["", "## Warning", str(payload.get("warning_message"))])
    lines.extend(["", "## Recommended Action", str(payload.get("recommended_action") or "")])
    return "\n".join(lines)
