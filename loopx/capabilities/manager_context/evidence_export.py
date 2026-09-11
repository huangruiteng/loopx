"""CLI wire projection reusing the manager's existing Core providers."""

import json
from pathlib import Path


def export_page(registry_path, runtime_root_arg, args):
    from ...paths import resolve_runtime_root
    from ...chat_manager_context import manager_turn_context
    from .inspection import ManagerInspection, TOOL_NAME

    registry = json.loads(Path(registry_path).read_text())
    root = resolve_runtime_root(registry, runtime_root_arg, registry_path=registry_path)
    ids = args.portfolio_goal_ids
    if not 1 <= args.limit <= 12 or not 1 <= args.days <= 90 or args.offset < 0:
        raise ValueError("invalid evidence bounds")
    if args.manager_view != "portfolio" and (not ids or len(ids) != 1):
        raise ValueError("one exact Goal required for details")
    if args.manager_view == "portfolio":
        # Local CLI authority chooses the scope before collection; all exported
        # fields use the same audience-safe projection as the manager.
        session = {"channel_id": "manager" if ids is None else "manager.export"}
        context = manager_turn_context(
            registry_path, session, root, authorized_goal_ids=ids, include_details=False
        )
    else:
        available = {g.get("id") for g in registry.get("goals", [])}
        context = {"goals": [{"goal_id": g} for g in ids if g in available]}
    inspector = ManagerInspection(
        context=context,
        registry_path=registry_path,
        runtime_root=root,
        owner_scope=False,
        scope_valid=lambda: True,
        record=lambda _: None,
    )
    query = {"view": args.manager_view, "offset": args.offset, "limit": args.limit}
    if args.manager_view == "portfolio":
        query["include_stopped"] = args.include_stopped
    else:
        query["goal_id"] = ids[0]
    if args.manager_view == "deliveries":
        query["days"] = args.days
    result = inspector.read(TOOL_NAME, query)
    for row in result.get("rows", []):
        row.setdefault("goal_id", query.get("goal_id"))
    result["schema_version"] = "manager_evidence_page_v1"
    return result
