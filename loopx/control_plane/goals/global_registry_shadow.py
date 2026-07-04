from __future__ import annotations

from typing import Any


def compact_global_registry_shadow_finding(finding: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "kind": str(finding.get("kind") or "global_registry_finding"),
        "severity": str(finding.get("severity") or "action"),
        "source": "global_registry",
    }
    if finding.get("message"):
        compact["message"] = str(finding.get("message"))
    if finding.get("recommended_action"):
        compact["recommended_action"] = str(finding.get("recommended_action"))
    return compact


def attach_global_registry_shadow_finding(item: dict[str, Any], finding: dict[str, Any]) -> None:
    shadows = item.setdefault("global_registry_shadow_findings", [])
    if isinstance(shadows, list):
        shadows.append(compact_global_registry_shadow_finding(finding))
    project_asset = item.get("project_asset")
    if not isinstance(project_asset, dict):
        return
    summary = project_asset.setdefault("global_registry_shadow_findings", {"open": 0, "kinds": []})
    if not isinstance(summary, dict):
        return
    summary["open"] = int(summary.get("open") or 0) + 1
    kinds = summary.setdefault("kinds", [])
    kind = str(finding.get("kind") or "global_registry_finding")
    if isinstance(kinds, list) and kind not in kinds:
        kinds.append(kind)
