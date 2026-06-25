from __future__ import annotations

import ipaddress
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit, urlunsplit


VALUE_CONNECTOR_PLAN_PACKET_SCHEMA_VERSION = "value_connector_plan_packet_v0"
VALUE_CONNECTOR_PLAN_SCHEMA_VERSION = "value_connector_plan_v0"
CONNECTOR_CALL_INTENT_SCHEMA_VERSION = "connector_call_intent_v0"
CONNECTOR_APPROVAL_GATE_SCHEMA_VERSION = "connector_approval_gate_v0"
VALUE_CONNECTOR_PLAN_VALIDATION_SCHEMA_VERSION = "value_connector_plan_validation_v0"
VALUE_CONNECTOR_PLAN_PROJECTION_SCHEMA_VERSION = "value_connector_plan_projection_v0"

ALLOWED_CONNECTOR_KINDS = {
    "github_channel",
    "botmail_identity",
    "community_channel",
    "x_public_channel",
    "browser_social_channel",
    "signup_probe",
    "lead_monitor",
    "custom_connector",
}
ALLOWED_STAGES = {
    "observe",
    "account_setup",
    "draft",
    "external_write_request",
    "monitor",
    "value_attribution",
}
ALLOWED_ACCESS_MODES = {
    "public_metadata_only",
    "agent_owned_identity",
    "private_metadata_gate",
    "external_write_gated",
    "fixture_only",
}
ALLOWED_VALUE_AXES = {
    "revenue",
    "cost_reduction",
    "demand",
    "capability",
}
ALLOWED_GATE_STATUSES = {
    "blocked_until_explicit_approval",
    "approved_for_this_exact_call",
    "denied",
    "needs_revision",
}

RAW_OR_PRIVATE_KEY_HINTS = (
    "body",
    "chat",
    "cookie",
    "auth material",
    "dm",
    "local_path",
    "log",
    "message_body",
    "password",
    "raw",
    "secret",
    "token",
    "transcript",
)
FORBIDDEN_TEXT_SNIPPETS = (
    "restricted-value",
    "sensitive-value",
    "bearer ",
)


def _text(value: Any, *, field: str, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueError(f"{field} is required")
    lowered = text.lower()
    if any(snippet in lowered for snippet in FORBIDDEN_TEXT_SNIPPETS):
        raise ValueError(f"{field} must not include auth material or secret-looking values")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _optional_text(value: Any, *, field: str, limit: int = 220) -> str | None:
    if value is None:
        return None
    return _text(value, field=field, limit=limit)


def _normalise_public_https_url(url: str) -> str:
    text = str(url or "").strip()
    parsed = urlsplit(text)
    if parsed.scheme != "https":
        raise ValueError("target_url must use https")
    if parsed.username or parsed.password:
        raise ValueError("target_url must not include auth material")
    if parsed.query or parsed.fragment:
        raise ValueError("target_url must not include query or fragment data")
    if parsed.port not in (None, 443):
        raise ValueError("target_url must use the default https port")
    host = parsed.hostname
    if not host:
        raise ValueError("target_url must include a host")
    lowered_host = host.lower().rstrip(".")
    if lowered_host == "localhost" or lowered_host.endswith((".localhost", ".local")):
        raise ValueError("target_url must not target localhost or local hosts")
    try:
        address = ipaddress.ip_address(lowered_host.strip("[]"))
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise ValueError("target_url must not target private or local addresses")
    path = parsed.path or "/"
    return urlunsplit(("https", parsed.netloc, path, "", ""))


def _normalise_id(value: Any, *, field: str) -> str:
    text = _text(value, field=field, limit=96).lower().replace(" ", "_")
    if any(char in text for char in "/\\<>"):
        raise ValueError(f"{field} must be a compact id")
    return text


def _connector_call(
    *,
    call_id: str,
    connector_id: str,
    connector_kind: str,
    channel: str,
    stage: str,
    target_ref: str,
    value_axis: str,
    money_metric: str,
    success_metric: str,
    kill_condition: str,
    access_mode: str,
    target_url: str | None = None,
    audience: str = "external operators running long-lived agent workflows",
    sender_identity: str = "LoopX operator",
    external_reads_allowed: bool = False,
    external_write_requested: bool = False,
    approval_gate_id: str | None = None,
    promotion_target: str = "qualified_lead_or_connector_signal",
) -> dict[str, Any]:
    if connector_kind not in ALLOWED_CONNECTOR_KINDS:
        raise ValueError(f"connector_kind must be one of {sorted(ALLOWED_CONNECTOR_KINDS)}")
    if stage not in ALLOWED_STAGES:
        raise ValueError(f"stage must be one of {sorted(ALLOWED_STAGES)}")
    if access_mode not in ALLOWED_ACCESS_MODES:
        raise ValueError(f"access_mode must be one of {sorted(ALLOWED_ACCESS_MODES)}")
    if value_axis not in ALLOWED_VALUE_AXES:
        raise ValueError(f"value_axis must be one of {sorted(ALLOWED_VALUE_AXES)}")

    requires_approval = external_write_requested or stage in {
        "account_setup",
        "external_write_request",
    }
    normalised_target_url = _normalise_public_https_url(target_url) if target_url else None
    return {
        "schema_version": CONNECTOR_CALL_INTENT_SCHEMA_VERSION,
        "call_id": _normalise_id(call_id, field="call_id"),
        "connector_id": _normalise_id(connector_id, field="connector_id"),
        "connector_kind": connector_kind,
        "channel": _text(channel, field="channel", limit=120),
        "stage": stage,
        "target_ref": _text(target_ref, field="target_ref", limit=180),
        "target_url": normalised_target_url,
        "audience": _text(audience, field="audience", limit=180),
        "sender_identity": _text(sender_identity, field="sender_identity", limit=120),
        "access_mode": access_mode,
        "external_reads_allowed": bool(external_reads_allowed),
        "external_writes_allowed": False,
        "external_write_requested": bool(external_write_requested),
        "requires_user_approval": bool(requires_approval),
        "approval_gate_id": approval_gate_id if requires_approval else None,
        "value_axis": value_axis,
        "money_metric": _text(money_metric, field="money_metric", limit=180),
        "success_metric": _text(success_metric, field="success_metric", limit=180),
        "kill_condition": _text(kill_condition, field="kill_condition", limit=220),
        "promotion_target": _text(promotion_target, field="promotion_target", limit=140),
        "forbidden_before_approval": [
            "auth material collection",
            "captcha bypass",
            "paid service signup",
            "private source content read",
            "external posting or messaging",
            "production action",
        ],
    }


def _approval_gate(
    *,
    gate_id: str,
    channel: str,
    decision_owner: str,
    exact_call_required: bool = True,
) -> dict[str, Any]:
    return {
        "schema_version": CONNECTOR_APPROVAL_GATE_SCHEMA_VERSION,
        "gate_id": _normalise_id(gate_id, field="gate_id"),
        "channel": _text(channel, field="channel", limit=120),
        "status": "blocked_until_explicit_approval",
        "approval_required": True,
        "autopublish_allowed": False,
        "decision_owner": _text(decision_owner, field="decision_owner", limit=120),
        "exact_call_required": bool(exact_call_required),
        "exact_fields_required": [
            "connector_id",
            "channel",
            "sender_identity",
            "target_ref",
            "target_url_or_handle",
            "message_text_or_signup_action",
            "success_metric",
            "kill_condition",
        ],
    }


def build_value_connector_plan_fixture(
    *,
    generated_at: str = "2026-06-25T00:00:00Z",
    scenario: str = "external_value_channel_queue",
) -> dict[str, Any]:
    """Build a public-safe connector planning fixture.

    The fixture models reusable connector calls without executing external
    reads, account signups, outbound messages, or production actions.
    """

    gates = [
        _approval_gate(
            gate_id="gate_agent_owned_account_setup",
            channel="agent-owned account setup",
            decision_owner="LoopX operator",
        ),
        _approval_gate(
            gate_id="gate_external_public_reply",
            channel="public community reply",
            decision_owner="LoopX operator",
        ),
        _approval_gate(
            gate_id="gate_x_account_identity_setup",
            channel="X browser account identity",
            decision_owner="LoopX operator",
        ),
        _approval_gate(
            gate_id="gate_x_exact_publish",
            channel="X public post or reply",
            decision_owner="LoopX operator",
        ),
    ]
    calls = [
        _connector_call(
            call_id="github_issue_intake",
            connector_id="github_public_channel",
            connector_kind="github_channel",
            channel="GitHub issue",
            stage="monitor",
            target_ref="public workflow intake issue",
            target_url="https://github.com/huangruiteng/loopx/issues/670",
            access_mode="public_metadata_only",
            external_reads_allowed=True,
            value_axis="demand",
            money_metric="qualified workflow submission that can become an audit or pilot",
            success_metric="one relevant external workflow comment or demo request",
            kill_condition="no relevant workflow signal after the follow-up window",
        ),
        _connector_call(
            call_id="github_discussion_intake",
            connector_id="github_public_channel",
            connector_kind="github_channel",
            channel="GitHub discussion",
            stage="monitor",
            target_ref="public workflow discussion",
            target_url="https://github.com/huangruiteng/loopx/discussions/673",
            access_mode="public_metadata_only",
            external_reads_allowed=True,
            value_axis="demand",
            money_metric="conversation with an operator who has a reusable agent workflow",
            success_metric="one workflow shared with enough metadata for a LoopX audit",
            kill_condition="only generic interest and no workflow owner appears",
        ),
        _connector_call(
            call_id="x_public_signal_scan",
            connector_id="social_browser_x",
            connector_kind="x_public_channel",
            channel="X public search and profile metadata",
            stage="observe",
            target_ref="loop-engineering public posts, handles, and reply surfaces",
            target_url="https://x.com/loopxops",
            access_mode="public_metadata_only",
            external_reads_allowed=True,
            value_axis="demand",
            money_metric="qualified builder or workflow owner signal for LoopX local control-plane onboarding",
            success_metric="one target-specific draft packet or stop decision with source attribution",
            kill_condition="signals are generic hype, spam-shaped, or not connected to agent workflow operations",
        ),
        _connector_call(
            call_id="x_identity_maintenance",
            connector_id="social_browser_x",
            connector_kind="browser_social_channel",
            channel="X account profile via ego-browser",
            stage="account_setup",
            target_ref="LoopX-only public account identity and profile assets",
            target_url="https://x.com/loopxops",
            access_mode="agent_owned_identity",
            approval_gate_id="gate_x_account_identity_setup",
            value_axis="revenue",
            money_metric="public product channel ready to receive qualified workflow-owner replies without using private identity",
            success_metric="profile identity is public-safe, LoopX-only, and ready for one approved launch post",
            kill_condition="account setup requires payment, captcha bypass, non-LoopX brand claims, or private employer context",
        ),
        _connector_call(
            call_id="x_launch_post_gate",
            connector_id="social_browser_x",
            connector_kind="browser_social_channel",
            channel="X public post via ego-browser",
            stage="external_write_request",
            target_ref="one local-first LoopX launch post with image and repo link",
            target_url="https://x.com/loopxops",
            access_mode="external_write_gated",
            external_write_requested=True,
            approval_gate_id="gate_x_exact_publish",
            value_axis="revenue",
            money_metric="qualified workflow owner asks for LoopX setup help, audit, demo, or repo adoption",
            success_metric="one non-spam reply or click-through signal that can enter a paid-path or pilot conversation",
            kill_condition="post is hidden as spam, account health degrades, or replies do not map to a concrete workflow owner",
        ),
        _connector_call(
            call_id="botmail_identity_signup_probe",
            connector_id="botmail_identity",
            connector_kind="botmail_identity",
            channel="email-gated community signup",
            stage="account_setup",
            target_ref="agent-owned external account identity",
            access_mode="agent_owned_identity",
            approval_gate_id="gate_agent_owned_account_setup",
            value_axis="revenue",
            money_metric="reachable buyer or operator contact path created without owner inbox dependency",
            success_metric="one verified account that can receive qualified lead replies",
            kill_condition="signup requires payment, auth material, captcha bypass, or non-LoopX brand claims",
        ),
        _connector_call(
            call_id="community_reply_draft",
            connector_id="community_channel",
            connector_kind="community_channel",
            channel="third-party community thread",
            stage="external_write_request",
            target_ref="thread asking about long-running agent operations",
            access_mode="external_write_gated",
            external_write_requested=True,
            approval_gate_id="gate_external_public_reply",
            value_axis="revenue",
            money_metric="qualified reply from a budget owner or workflow owner",
            success_metric="reply asks for audit, demo, or concrete workflow review",
            kill_condition="thread is not asking for agent operations help or channel rules reject promotion",
        ),
        _connector_call(
            call_id="lead_response_monitor",
            connector_id="lead_monitor",
            connector_kind="lead_monitor",
            channel="reply monitor",
            stage="value_attribution",
            target_ref="inbound replies from public issue, discussion, email, or community posts",
            access_mode="public_metadata_only",
            external_reads_allowed=True,
            value_axis="revenue",
            money_metric="reply classified as buyer, workflow owner, demo request, or no-fit",
            success_metric="one reply routed to audit, demo, or stop decision within one turn",
            kill_condition="inbound signal cannot be classified into a paid, cost, demand, or capability path",
        ),
    ]
    return {
        "schema_version": VALUE_CONNECTOR_PLAN_SCHEMA_VERSION,
        "plan_id": _normalise_id(scenario, field="scenario"),
        "generated_at": _text(generated_at, field="generated_at", limit=80),
        "objective": (
            "Plan external connector calls that can create revenue, cost, demand, "
            "or capability evidence while keeping all external writes gated."
        ),
        "brand_boundary": {
            "external_brand": "LoopX",
            "external_only_brand_claims": True,
            "unrelated_employer_or_vendor_claims_allowed": False,
        },
        "connector_calls": calls,
        "approval_gates": gates,
        "truth_contract": {
            "plan_only": True,
            "external_reads_performed": False,
            "external_writes_performed": False,
            "account_signup_performed": False,
            "restricted_material_recorded": False,
            "private_source_content_read": False,
            "autopublish_allowed": False,
            "production_actions_allowed": False,
        },
    }


def build_single_value_connector_plan(
    *,
    connector_id: str,
    connector_kind: str,
    channel: str,
    stage: str,
    target_ref: str,
    value_axis: str,
    money_metric: str,
    success_metric: str,
    kill_condition: str,
    generated_at: str,
    target_url: str | None = None,
    audience: str = "external operators running long-lived agent workflows",
    sender_identity: str = "LoopX operator",
    external_reads_allowed: bool = False,
    external_write_requested: bool = False,
) -> dict[str, Any]:
    requires_gate = external_write_requested or stage in {
        "account_setup",
        "external_write_request",
    }
    gate_id = "gate_requested_connector_call" if requires_gate else None
    access_mode = "external_write_gated" if external_write_requested else "public_metadata_only"
    calls = [
        _connector_call(
            call_id=f"{connector_id}_{stage}",
            connector_id=connector_id,
            connector_kind=connector_kind,
            channel=channel,
            stage=stage,
            target_ref=target_ref,
            target_url=target_url,
            audience=audience,
            sender_identity=sender_identity,
            access_mode=access_mode,
            external_reads_allowed=external_reads_allowed,
            external_write_requested=external_write_requested,
            approval_gate_id=gate_id,
            value_axis=value_axis,
            money_metric=money_metric,
            success_metric=success_metric,
            kill_condition=kill_condition,
        )
    ]
    gates = (
        [
            _approval_gate(
                gate_id=gate_id or "gate_requested_connector_call",
                channel=channel,
                decision_owner=sender_identity,
            )
        ]
        if requires_gate
        else []
    )
    return {
        "schema_version": VALUE_CONNECTOR_PLAN_SCHEMA_VERSION,
        "plan_id": _normalise_id(f"{connector_id}_{stage}_plan", field="plan_id"),
        "generated_at": _text(generated_at, field="generated_at", limit=80),
        "objective": "Plan one reusable connector call before any external action executes.",
        "brand_boundary": {
            "external_brand": "LoopX",
            "external_only_brand_claims": True,
            "unrelated_employer_or_vendor_claims_allowed": False,
        },
        "connector_calls": calls,
        "approval_gates": gates,
        "truth_contract": {
            "plan_only": True,
            "external_reads_performed": False,
            "external_writes_performed": False,
            "account_signup_performed": False,
            "restricted_material_recorded": False,
            "private_source_content_read": False,
            "autopublish_allowed": False,
            "production_actions_allowed": False,
        },
    }


def _as_mappings(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _raw_key_names(value: Any) -> list[str]:
    names: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                lowered = str(key).lower()
                if any(hint in lowered for hint in RAW_OR_PRIVATE_KEY_HINTS):
                    names.add(str(key))
                visit(child)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            for child in item:
                visit(child)

    visit(value)
    return sorted(names)


def validate_value_connector_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    calls = _as_mappings(plan.get("connector_calls"))
    gates = _as_mappings(plan.get("approval_gates"))
    gate_ids = {str(gate.get("gate_id")) for gate in gates if gate.get("gate_id")}
    errors: list[str] = []

    if plan.get("schema_version") != VALUE_CONNECTOR_PLAN_SCHEMA_VERSION:
        errors.append("plan schema_version must be value_connector_plan_v0")
    if not calls:
        errors.append("at least one connector_call_intent_v0 is required")

    brand = plan.get("brand_boundary") if isinstance(plan.get("brand_boundary"), Mapping) else {}
    if brand.get("external_brand") != "LoopX":
        errors.append("brand_boundary.external_brand must be LoopX")
    if brand.get("external_only_brand_claims") is not True:
        errors.append("brand_boundary.external_only_brand_claims must be true")
    if brand.get("unrelated_employer_or_vendor_claims_allowed") is not False:
        errors.append("unrelated employer or vendor claims must be disabled")

    call_ids: set[str] = set()
    for call in calls:
        call_id = str(call.get("call_id") or "")
        if call.get("schema_version") != CONNECTOR_CALL_INTENT_SCHEMA_VERSION:
            errors.append(f"connector call {call_id or '<missing>'} has wrong schema")
        if not call_id:
            errors.append("connector call must include call_id")
        elif call_id in call_ids:
            errors.append(f"duplicate connector call_id {call_id}")
        call_ids.add(call_id)
        if call.get("connector_kind") not in ALLOWED_CONNECTOR_KINDS:
            errors.append(f"connector call {call_id} has invalid connector_kind")
        if call.get("stage") not in ALLOWED_STAGES:
            errors.append(f"connector call {call_id} has invalid stage")
        if call.get("access_mode") not in ALLOWED_ACCESS_MODES:
            errors.append(f"connector call {call_id} has invalid access_mode")
        if call.get("value_axis") not in ALLOWED_VALUE_AXES:
            errors.append(f"connector call {call_id} has invalid value_axis")
        if call.get("external_writes_allowed") is not False:
            errors.append(f"connector call {call_id} must set external_writes_allowed=false")
        if call.get("money_metric") in (None, ""):
            errors.append(f"connector call {call_id} must include money_metric")
        if call.get("success_metric") in (None, ""):
            errors.append(f"connector call {call_id} must include success_metric")
        if call.get("kill_condition") in (None, ""):
            errors.append(f"connector call {call_id} must include kill_condition")
        target_url = call.get("target_url")
        if target_url:
            try:
                _normalise_public_https_url(str(target_url))
            except ValueError as exc:
                errors.append(f"connector call {call_id} target_url invalid: {exc}")
        requested = call.get("external_write_requested") is True
        gated_stage = call.get("stage") in {"account_setup", "external_write_request"}
        if requested or gated_stage:
            if call.get("requires_user_approval") is not True:
                errors.append(f"connector call {call_id} must require user approval")
            gate_id = str(call.get("approval_gate_id") or "")
            if gate_id not in gate_ids:
                errors.append(f"connector call {call_id} references missing approval gate")

    for gate in gates:
        gate_id = str(gate.get("gate_id") or "")
        if gate.get("schema_version") != CONNECTOR_APPROVAL_GATE_SCHEMA_VERSION:
            errors.append(f"approval gate {gate_id or '<missing>'} has wrong schema")
        if gate.get("status") not in ALLOWED_GATE_STATUSES:
            errors.append(f"approval gate {gate_id} has invalid status")
        if gate.get("approval_required") is not True:
            errors.append(f"approval gate {gate_id} must require approval")
        if gate.get("autopublish_allowed") is not False:
            errors.append(f"approval gate {gate_id} must set autopublish_allowed=false")

    truth = plan.get("truth_contract") if isinstance(plan.get("truth_contract"), Mapping) else {}
    for key in (
        "plan_only",
        "external_reads_performed",
        "external_writes_performed",
        "account_signup_performed",
        "restricted_material_recorded",
        "private_source_content_read",
        "autopublish_allowed",
        "production_actions_allowed",
    ):
        expected = True if key == "plan_only" else False
        if truth.get(key) is not expected:
            errors.append(f"truth_contract.{key} must be {str(expected).lower()}")

    raw_key_names = _raw_key_names(plan)
    if raw_key_names:
        errors.append("raw/private-looking key names must not appear in value connector plans")

    return {
        "schema_version": VALUE_CONNECTOR_PLAN_VALIDATION_SCHEMA_VERSION,
        "ok": not errors,
        "errors": errors,
        "connector_call_count": len(calls),
        "approval_gate_count": len(gates),
        "raw_key_names": raw_key_names,
    }


def project_value_connector_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    calls = _as_mappings(plan.get("connector_calls"))
    gates = _as_mappings(plan.get("approval_gates"))
    stage_counts = dict(sorted(Counter(str(call.get("stage")) for call in calls).items()))
    value_axis_counts = dict(
        sorted(Counter(str(call.get("value_axis")) for call in calls).items())
    )
    connector_kind_counts = dict(
        sorted(Counter(str(call.get("connector_kind")) for call in calls).items())
    )
    gated_calls = [
        call.get("call_id")
        for call in calls
        if call.get("requires_user_approval") is True
    ]
    executable_now = [
        call.get("call_id")
        for call in calls
        if call.get("requires_user_approval") is not True
        and call.get("external_writes_allowed") is False
    ]
    return {
        "schema_version": VALUE_CONNECTOR_PLAN_PROJECTION_SCHEMA_VERSION,
        "first_screen": {
            "waiting_on": "user" if gated_calls else "agent",
            "agent_can_prepare": True,
            "external_write_blocked": True,
            "gated_call_count": len(gated_calls),
            "safe_prepare_call_count": len(executable_now),
        },
        "stage_counts": stage_counts,
        "value_axis_counts": value_axis_counts,
        "connector_kind_counts": connector_kind_counts,
        "gated_calls": gated_calls,
        "safe_prepare_calls": executable_now,
        "approval_gate_ids": [gate.get("gate_id") for gate in gates],
        "truth_contract": {
            "projection_is_writable": False,
            "external_action_requires_exact_gate": True,
            "money_metric_required": True,
        },
    }


def build_value_connector_plan_packet(plan: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_value_connector_plan(plan)
    projection = project_value_connector_plan(plan)
    return {
        "ok": bool(validation.get("ok")),
        "schema_version": VALUE_CONNECTOR_PLAN_PACKET_SCHEMA_VERSION,
        "mode": "value-connectors-plan",
        "external_reads_performed": False,
        "external_writes_performed": False,
        "account_signup_performed": False,
        "restricted_material_recorded": False,
        "private_source_content_read": False,
        "autopublish_allowed": False,
        "plan": dict(plan),
        "projection": projection,
        "validation": validation,
    }


def render_value_connector_plan_markdown(payload: dict[str, Any]) -> str:
    plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
    projection = (
        payload.get("projection") if isinstance(payload.get("projection"), Mapping) else {}
    )
    first_screen = (
        projection.get("first_screen") if isinstance(projection.get("first_screen"), Mapping) else {}
    )
    validation = (
        payload.get("validation") if isinstance(payload.get("validation"), Mapping) else {}
    )
    lines = [
        "# LoopX Value Connector Plan",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- plan_id: `{plan.get('plan_id')}`",
        f"- external_reads_performed: `{payload.get('external_reads_performed')}`",
        f"- external_writes_performed: `{payload.get('external_writes_performed')}`",
        f"- account_signup_performed: `{payload.get('account_signup_performed')}`",
        f"- first_screen.waiting_on: `{first_screen.get('waiting_on')}`",
        f"- safe_prepare_call_count: `{first_screen.get('safe_prepare_call_count')}`",
        f"- gated_call_count: `{first_screen.get('gated_call_count')}`",
        "",
        "## Connector Calls",
        "",
    ]
    for call in plan.get("connector_calls") or []:
        if not isinstance(call, Mapping):
            continue
        lines.extend(
            [
                f"- `{call.get('call_id')}` on `{call.get('channel')}`",
                f"  - stage: `{call.get('stage')}`",
                f"  - value_axis: `{call.get('value_axis')}`",
                f"  - metric: {call.get('money_metric')}",
                f"  - kill_condition: {call.get('kill_condition')}",
                f"  - approval_gate_id: `{call.get('approval_gate_id')}`",
            ]
        )
    errors = validation.get("errors") if isinstance(validation.get("errors"), list) else []
    if errors:
        lines.extend(["", "## Validation Errors", ""])
        lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines).rstrip() + "\n"
