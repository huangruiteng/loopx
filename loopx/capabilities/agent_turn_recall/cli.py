from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ...history import load_registry
from ...materials import find_registry_goal, goal_repo
from ..reward_memory.experiment import (
    resolve_reward_memory_experiment,
    resolve_reward_memory_surface_config,
)
from .core import (
    AGENT_TURN_RECALL_SCHEMA_VERSION,
    AGENT_TURN_RECALL_SURFACE_ID,
    build_agent_turn_recall_preview,
    build_agent_turn_situation,
    run_agent_turn_recall,
)


AGENT_TURN_RECALL_RECEIPT_SCHEMA_VERSION = "agent_turn_recall_receipt_v0"
_SAFE_PATH_TOKEN = re.compile(r"[^A-Za-z0-9._-]+")


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _render(payload: dict[str, object]) -> str:
    lines = ["# Agent Turn Recall", ""]
    for key in (
        "status",
        "goal_id",
        "agent_id",
        "surface_id",
        "provider_call_count",
    ):
        if payload.get(key) is not None:
            lines.append(f"- {key}: `{payload[key]}`")
    context = payload.get("context")
    guidance = context.get("guidance") if isinstance(context, Mapping) else None
    if isinstance(guidance, list):
        lines.append(f"- guidance_count: `{len(guidance)}`")
    return "\n".join(lines) + "\n"


def register_agent_turn_recall_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "agent-turn-recall",
        help="Recall scoped memory from the current autonomous Goal/Todo situation.",
    )
    add_subcommand_format(parser)
    parser.add_argument("--goal-id", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--turn-instance-id", required=True)
    parser.add_argument(
        "--quota-decision-json",
        required=True,
        help="Exact quota should-run JSON path, or - for stdin.",
    )
    parser.add_argument("--session-ref")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the configured provider and write one ignored same-turn receipt.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore a matching same-turn receipt and query the provider again.",
    )


def _goal_repo(registry_path: Path, goal_id: str) -> Path:
    goal = find_registry_goal(load_registry(registry_path), goal_id)
    resolved = goal_repo(goal) if goal else None
    if resolved is None:
        raise ValueError(f"goal `{goal_id}` repository is unavailable")
    repo = Path(resolved)
    if not repo.is_dir():
        raise ValueError(f"goal `{goal_id}` repository is unavailable")
    return repo


def _receipt_path(repo: Path, agent_id: str) -> Path:
    token = _SAFE_PATH_TOKEN.sub("-", agent_id).strip("-") or "agent"
    return repo / ".local" / "loopx" / "agent-turn-recall" / f"{token}.json"


def _quota_decision(path_value: str) -> dict[str, Any]:
    try:
        if path_value == "-":
            payload = json.load(sys.stdin)
        else:
            payload = json.loads(
                Path(path_value).expanduser().read_text(encoding="utf-8")
            )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("quota decision must be readable JSON") from exc
    if not isinstance(payload, dict) or payload.get("mode") != "should-run":
        raise ValueError("quota decision must be one quota should-run object")
    return payload


def _validate_quota_identity(
    quota_decision: Mapping[str, Any],
    *,
    goal_id: str,
    agent_id: str,
    turn_instance_id: str,
) -> None:
    if quota_decision.get("goal_id") != goal_id:
        raise ValueError("quota decision goal_id does not match --goal-id")
    decision_agent = _mapping(quota_decision.get("agent_identity")).get("agent_id")
    if decision_agent != agent_id:
        raise ValueError("quota decision agent_id does not match --agent-id")
    receipt = _mapping(quota_decision.get("heartbeat_receipt"))
    if receipt.get("turn_instance_id") != turn_instance_id:
        raise ValueError(
            "quota decision turn_instance_id does not match --turn-instance-id"
        )
    if receipt.get("status") not in {"committed", "replayed"}:
        raise ValueError("quota decision heartbeat receipt is not committed")


def _load_receipt(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != AGENT_TURN_RECALL_RECEIPT_SCHEMA_VERSION:
        return None
    return payload


def _write_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _identity_scope(config: Mapping[str, Any]) -> dict[str, str | None]:
    route = resolve_reward_memory_surface_config(
        config,
        AGENT_TURN_RECALL_SURFACE_ID,
    )
    routes = route.get("recall_corpora")
    if not isinstance(routes, list) or not routes:
        raise ValueError("agent turn recall surface has no corpus")
    identity: dict[str, str | None] | None = None
    for item in routes:
        corpus = item.get("corpus") if isinstance(item, Mapping) else None
        scope = corpus.get("scope") if isinstance(corpus, Mapping) else None
        if not isinstance(scope, Mapping):
            raise ValueError("agent turn recall corpus scope is invalid")
        current = {
            key: str(scope.get(key) or "").strip() or None
            for key in (
                "workspace_ref",
                "project_ref",
                "user_ref",
                "peer_ref",
                "session_ref",
            )
        }
        if identity is not None and current != identity:
            raise ValueError("agent turn recall corpora must share one identity scope")
        identity = current
    assert identity is not None
    return identity


def _resolve_session_ref(
    identity: Mapping[str, str | None], requested: str | None
) -> str | None:
    configured = str(identity.get("session_ref") or "").strip() or None
    requested = str(requested or "").strip() or None
    if configured and requested and configured != requested:
        raise ValueError("--session-ref does not match the configured corpus scope")
    return configured or requested


def _read_authority_checkpoints(
    config: Mapping[str, Any], goal_id: str
) -> dict[str, dict[str, Any]]:
    route = resolve_reward_memory_surface_config(
        config,
        AGENT_TURN_RECALL_SURFACE_ID,
    )
    checkpoints: dict[str, dict[str, Any]] = {}
    for item in route["recall_corpora"]:
        corpus = item["corpus"]
        scope = corpus["scope"]
        checkpoint = {
            "verified": True,
            "corpus_id": corpus["corpus_id"],
            "workspace_ref": scope["workspace_ref"],
            "project_ref": scope["project_ref"],
            "surface_id": AGENT_TURN_RECALL_SURFACE_ID,
            "read_authority": corpus["read_authority"],
            "source_ref": f"registry:{goal_id}:reward-memory",
        }
        for field in ("user_ref", "peer_ref", "session_ref"):
            if scope.get(field):
                checkpoint[field] = scope[field]
        checkpoints[corpus["corpus_id"]] = checkpoint
    return checkpoints


def _deduplicated_payload(
    receipt: Mapping[str, Any],
    *,
    goal_id: str,
    agent_id: str,
) -> dict[str, Any] | None:
    context = receipt.get("context")
    if not isinstance(context, Mapping):
        return None
    return {
        "ok": True,
        "schema_version": AGENT_TURN_RECALL_SCHEMA_VERSION,
        "status": "deduplicated",
        "goal_id": goal_id,
        "agent_id": agent_id,
        "surface_id": AGENT_TURN_RECALL_SURFACE_ID,
        "turn_recall_id": receipt.get("turn_recall_id"),
        "situation_fingerprint": receipt.get("situation_fingerprint"),
        "context": dict(context),
        "provider_call_count": 0,
        "same_turn_receipt_reused": True,
        "source_status": receipt.get("source_status"),
        "grants_new_action_authority": False,
        "quota_spend_performed": False,
        "external_writes_performed": False,
        "suppress_external_sinks": True,
    }


def handle_agent_turn_recall_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    output_format: Callable[..., str],
    print_payload: Callable[..., None],
) -> int | None:
    if args.command != "agent-turn-recall":
        return None
    try:
        goal_repo = _goal_repo(registry_path, args.goal_id)
        experiment_status, config = resolve_reward_memory_experiment(
            registry_path=registry_path,
            goal_id=args.goal_id,
            agent_id=args.agent_id,
        )
        if config is None:
            payload: dict[str, Any] = {
                "ok": True,
                "schema_version": AGENT_TURN_RECALL_SCHEMA_VERSION,
                "status": "disabled",
                "goal_id": args.goal_id,
                "agent_id": args.agent_id,
                "experiment": experiment_status,
                "provider_call_count": 0,
                "grants_new_action_authority": False,
                "quota_spend_performed": False,
                "external_writes_performed": False,
                "suppress_external_sinks": True,
            }
        else:
            identity = _identity_scope(config)
            quota_decision = _quota_decision(args.quota_decision_json)
            _validate_quota_identity(
                quota_decision,
                goal_id=args.goal_id,
                agent_id=args.agent_id,
                turn_instance_id=args.turn_instance_id,
            )
            situation = build_agent_turn_situation(
                quota_decision,
                goal_id=args.goal_id,
                agent_id=args.agent_id,
                turn_instance_id=args.turn_instance_id,
                workspace_ref=str(identity["workspace_ref"] or ""),
                project_ref=str(identity["project_ref"] or ""),
                user_ref=identity["user_ref"],
                session_ref=_resolve_session_ref(identity, args.session_ref),
            )
            receipt_path = _receipt_path(goal_repo, args.agent_id)
            previous = None if args.force_refresh else _load_receipt(receipt_path)
            deduplicated = (
                _deduplicated_payload(
                    previous,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                )
                if previous
                and previous.get("turn_recall_id") == situation["turn_recall_id"]
                else None
            )
            if deduplicated is not None:
                payload = deduplicated
            elif not args.execute:
                payload = build_agent_turn_recall_preview(situation) | {
                    "goal_id": args.goal_id,
                    "agent_id": args.agent_id,
                    "experiment": experiment_status,
                }
            else:
                payload = run_agent_turn_recall(
                    config,
                    situation,
                    observed_at=datetime.now(timezone.utc).isoformat(),
                    read_authority_checkpoints=_read_authority_checkpoints(
                        config, args.goal_id
                    ),
                ) | {
                    "goal_id": args.goal_id,
                    "agent_id": args.agent_id,
                    "experiment": experiment_status,
                }
                if payload.get("status") in {"applied", "not_available"}:
                    _write_receipt(
                        receipt_path,
                        {
                            "schema_version": AGENT_TURN_RECALL_RECEIPT_SCHEMA_VERSION,
                            "turn_recall_id": payload.get("turn_recall_id"),
                            "situation_fingerprint": payload.get(
                                "situation_fingerprint"
                            ),
                            "source_status": payload.get("status"),
                            "context": payload.get("context"),
                        },
                    )
                    payload["same_turn_receipt_written"] = True
    except (OSError, TypeError, ValueError) as exc:
        payload = {
            "ok": False,
            "schema_version": AGENT_TURN_RECALL_SCHEMA_VERSION,
            "status": "invalid_request",
            "goal_id": args.goal_id,
            "agent_id": args.agent_id,
            "error": str(exc),
            "provider_call_count": 0,
            "grants_new_action_authority": False,
            "quota_spend_performed": False,
            "external_writes_performed": False,
            "suppress_external_sinks": True,
        }
    print_payload(payload, output_format(args), _render)
    return 0 if payload.get("ok") else 2
