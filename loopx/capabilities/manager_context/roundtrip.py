"""A delegated request stays open until its receiver returns a conclusion.

The existing inbox owns request/decision truth; this module owns only return
routing, receiver-authored replies, and publication receipts. No model polling.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone, timedelta

from . import _root, _read, _write, _hash, authority
from .tracking import _entry, _now, _receipt
from ...file_lock import exclusive_file_lock
from ...presentation.public_safety import scan_public_boundary_text

PHASES = ("decision", "conclusion")


def register(root, row, session, turn):
    """Called by trusted Chat delivery, never with model-authored routing."""
    value = {k: row[k] for k in ("request_id", "goal_id", "agent_id", "source_id")}
    value.update(
        session_id=session["session_id"],
        client_turn_id=turn["client_turn_id"],
        channel_id=session["channel_id"],
    )
    path = _root(root) / "roundtrips" / (row["request_id"] + ".json")
    with exclusive_file_lock(path.with_suffix(".lock")):
        if path.exists():
            old = _read(path)
            if any(old.get(k) != v for k, v in value.items()):
                raise ValueError("context return route conflict")
        else:
            _write(path, value | {"registered_at": _now()})


def _route(root, row):
    path = _root(root) / "roundtrips" / (row["request_id"] + ".json")
    if not path.exists():
        # Legacy opt-in only when the receiver actually publishes a reply. Recover
        # exact trusted Chat receipts, never infer a destination from Goal alone.
        from ...chat_store import ChatSessionStore

        store = ChatSessionStore(root)
        matches = []
        for session in store.list_sessions():
            for p in (store.root / "sessions" / session["session_id"] / "turns").glob(
                "*.json"
            ):
                try:
                    turn = _read(p)
                except (OSError, ValueError):
                    # An unrelated damaged/oversized historical turn cannot
                    # prevent recovery of this exact request's return receipt.
                    continue
                receipt = (turn.get("response") or {}).get(
                    "context_handoff_receipt"
                ) or {}
                if receipt.get("request_id") == row["request_id"]:
                    matches.append((session, turn))
        if len(matches) != 1:
            raise ValueError("original Chat return route unavailable or ambiguous")
        register(root, row, *matches[0])
    value = _read(path)
    if any(
        value.get(k) != row.get(k)
        for k in ("request_id", "goal_id", "agent_id", "source_id")
    ):
        raise ValueError("context return route identity mismatch")
    return value


def needs_conclusion(root, request_id):
    return (_root(root) / "roundtrips" / (request_id + ".json")).exists() and not (
        _root(root) / "replies" / request_id / "conclusion.json"
    ).exists()


def report(root, goal_id, agent_id, request_id, phase, text):
    """Receiver declares an audience-ready decision or this request's conclusion."""
    row = _entry(root, goal_id, agent_id, request_id)
    route = _route(root, row)
    decision, error = _receipt(root, "decisions", row)
    if error or not decision:
        raise ValueError("record the receiver decision before returning a reply")
    if (
        phase not in PHASES
        or not isinstance(text, str)
        or not text.strip()
        or len(text) > 20000
    ):
        raise ValueError(
            "a decision/conclusion phase and bounded reply text are required"
        )
    text = text.strip()
    if route["channel_id"] != "manager" and not scan_public_boundary_text(text)["ok"]:
        raise ValueError(
            "reply contains private boundary material; write an audience-safe conclusion"
        )
    path = _root(root) / "replies" / request_id / (phase + ".json")
    with exclusive_file_lock((_root(root) / "replies" / request_id / "report.lock")):
        value = {k: row[k] for k in ("request_id", "goal_id", "agent_id", "source_id")}
        value.update(phase=phase, text=text, decision=decision["decision"])
        if path.exists():
            old = _read(path)
            if any(old.get(k) != v for k, v in value.items()):
                raise ValueError(
                    "reply already committed; conflicting replacement rejected"
                )
        else:
            if phase == "decision" and (path.parent / "conclusion.json").exists():
                raise ValueError(
                    "cannot publish an intermediate decision after conclusion"
                )
            _write(path, value | {"created_at": _now()})
    return {
        "ok": True,
        "request_id": request_id,
        "phase": phase,
        "status": "queued_for_original_conversation",
        "delivered": False,
    }


def reply_status(root, row):
    result = []
    for phase in PHASES:
        path = _root(root) / "replies" / row["request_id"] / (phase + ".json")
        if not path.exists():
            continue
        reply = _read(path)
        state_path = path.with_name(phase + ".delivery.json")
        state = _read(state_path) if state_path.exists() else {}
        result.append(
            {
                "phase": phase,
                "status": state.get("status", "queued"),
                "created_at": reply.get("created_at"),
                "delivered_at": state.get("delivered_at"),
                "error": state.get("error"),
            }
        )
    return result


def drain(root, registry, store, external_sender, *, now=None, cancelled=lambda: False):
    """Restart-safe return delivery; transport retries never rerun the worker/model."""
    now = now or datetime.now(timezone.utc)
    processed = 0
    for path in sorted((_root(root) / "replies").glob("*/*.json")):
        if cancelled():
            break
        if path.stem not in PHASES:
            continue
        state_path = path.with_name(path.stem + ".delivery.json")
        with exclusive_file_lock(path.with_suffix(".lock")):
            try:
                state = _read(state_path) if state_path.exists() else {}
            except (OSError, ValueError):
                # A damaged receipt has unknown delivery state: do not resend
                # it blindly, and do not starve unrelated pending returns.
                logging.getLogger(__name__).warning("Unreadable manager return receipt")
                continue
            if state.get("status") in {
                "delivered",
                "superseded",
                "verification_required",
            }:
                continue
            if state.get("retry_at") and now.isoformat() < state["retry_at"]:
                continue
            try:
                reply = _read(path)
                row = _entry(
                    root, reply["goal_id"], reply["agent_id"], reply["request_id"]
                )
                if (
                    path.parent.name != row["request_id"]
                    or reply.get("phase") != path.stem
                    or reply.get("source_id") != row["source_id"]
                ):
                    raise ValueError("return_reply_identity_mismatch")
                route = _route(root, row)
                session = store.load_session(route["session_id"])
                turn = store.turn_for_client(
                    route["session_id"], route["client_turn_id"]
                )
                if (
                    not session
                    or session.get("status") == "closed"
                    or session.get("channel_id") != route["channel_id"]
                    or not turn
                ):
                    raise ValueError("original_conversation_unavailable")
                grant = authority(root, registry, session, turn)
                target = {k: row[k] for k in ("goal_id", "agent_id")}
                if (
                    target not in grant["targets"]
                    or grant.get("source_id") != row["source_id"]
                ):
                    raise ValueError("return_authorization_unavailable")
                if turn.get("status") != "completed":
                    raise ValueError("initial_receipt_not_completed")
                if (
                    path.stem == "decision"
                    and (path.parent / "conclusion.json").exists()
                ):
                    _write(
                        state_path,
                        {"status": "superseded", "reason": "conclusion_ready"},
                    )
                    continue
                prefix = "处理结论" if path.stem == "conclusion" else "处理进展"
                text = f"{prefix} · {row['agent_id']} · 委托 {row['request_id'][:8]}\n\n{reply['text']}"
                # Transcript writes are independently idempotent, including when
                # Lark is offline. Keep the original Turn and logical conversation.
                mid = "handoff." + _hash([row["request_id"], path.stem])
                if cancelled():
                    return processed
                store.append_message(
                    route["session_id"],
                    role="agent",
                    text=text,
                    turn_id=turn["turn_id"],
                    origin="manager_followup",
                    message_id=mid,
                )
                if cancelled():
                    return processed
                transport = {}
                if route["channel_id"] != "manager":
                    sent = external_sender(route, session, turn, text)
                    if sent.get("reply_verified") is not True:
                        if sent.get("external_write_performed") is True:
                            _write(
                                state_path,
                                {
                                    "status": "verification_required",
                                    "error": "provider_delivery_unverified",
                                },
                            )
                            continue
                        raise ValueError("return_transport_unavailable")
                    transport = {
                        "provider_receipt": sent.get("idempotency_key"),
                        "reply_verified": True,
                    }
                _write(
                    state_path,
                    {
                        "status": "delivered",
                        "delivered_at": now.isoformat(),
                        "message_id": mid,
                        **transport,
                    },
                )
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                attempts = int(state.get("attempts", 0)) + 1
                _write(
                    state_path,
                    {
                        "status": "retry_pending",
                        "attempts": attempts,
                        "error": "original_route_or_return_delivery_unavailable",
                        "retry_at": (
                            now + timedelta(seconds=min(300, 5 * 2 ** min(attempts, 6)))
                        ).isoformat(),
                    },
                )
            processed += 1
            if processed >= 20:
                break
    return processed


class ReturnService:
    """Cheap local receipt pump hosted by the existing Chat server."""

    def __init__(self, root, registry, store, external_sender):
        self.args = (root, registry, store, external_sender)
        self.stop = threading.Event()
        self.thread = threading.Thread(
            target=self.run, daemon=True, name="loopx-manager-returns"
        )

    def start(self):
        self.thread.start()

    def run(self):
        while not self.stop.is_set():
            try:
                drain(*self.args, cancelled=self.stop.is_set)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                logging.getLogger(__name__).warning(
                    "Manager return receipts unavailable; retrying"
                )
            self.stop.wait(3)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)
