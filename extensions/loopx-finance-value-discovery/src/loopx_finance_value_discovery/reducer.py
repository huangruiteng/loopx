from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit


FINANCE_VALUE_DISCOVERY_INPUT_SCHEMA_VERSION = "finance_value_discovery_input_v0"
FINANCE_VALUE_DISCOVERY_CARD_SCHEMA_VERSION = "finance_value_discovery_evidence_card_v0"
FINANCE_VALUE_DISCOVERY_PACKET_SCHEMA_VERSION = "finance_value_discovery_packet_v0"
FINANCE_VALUE_DISCOVERY_PROJECTION_SCHEMA_VERSION = (
    "finance_value_discovery_projection_v0"
)
FINANCE_VALUE_DISCOVERY_ERROR_SCHEMA_VERSION = "finance_value_discovery_error_v0"
FINANCE_VALUE_DISCOVERY_EXTENSION_PROTOCOL = "finance_value_discovery_extension_v0"

ALLOWED_ROUTES = {"de_beta_mispricing", "long_compounder"}
ALLOWED_ROLES = {"candidate", "control"}
ALLOWED_CLASSIFICATIONS = {"A", "B", "C", "CONTROL"}
ALLOWED_AXIS_STATES = {"supported", "mixed", "refuted", "missing"}
ALLOWED_SOURCE_TIERS = {"primary", "independent", "secondary", "market_data"}
ALLOWED_CROSS_VALIDATION = {
    "primary_corroborated",
    "independent_corroborated",
    "single_source",
    "unverified",
}
ALLOWED_RELATIVE_SIGNALS = {
    "idiosyncratic_support",
    "group_wide",
    "inconclusive",
    "not_applicable",
}
ALLOWED_VALUATION_STATES = {"verified", "partial", "missing"}
ALLOWED_TERMINAL_RISK_STATES = {"bounded", "material", "unresolved"}

EVIDENCE_AXES = (
    "structural_growth",
    "profit_pool_capture",
    "incremental_capital_efficiency",
    "reinvestment_runway",
    "survival_and_dilution",
    "price_implied_expectations",
)

FORBIDDEN_KEY_TOKENS = {
    "account",
    "auth",
    "body",
    "cookie",
    "credential",
    "holding",
    "local",
    "password",
    "portfolio",
    "private",
    "raw",
    "secret",
    "token",
    "trade",
    "transcript",
}
FORBIDDEN_VALUE_PATTERNS = (
    re.compile(r"\bBearer\s+", re.IGNORECASE),
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\", re.IGNORECASE),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def _key_tokens(value: object) -> set[str]:
    return {part for part in re.split(r"[^a-z0-9]+", str(value).lower()) if part}


def _reject_forbidden_material(value: object, *, path: str = "input") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            forbidden = _key_tokens(key) & FORBIDDEN_KEY_TOKENS
            if forbidden:
                raise ValueError(
                    f"{path} contains forbidden key token(s): "
                    + ", ".join(sorted(forbidden))
                )
            _reject_forbidden_material(item, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_forbidden_material(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str) and any(
        pattern.search(value) for pattern in FORBIDDEN_VALUE_PATTERNS
    ):
        raise ValueError(
            f"{path} contains private path, auth material, or credential-like text"
        )


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _text(value: object, *, field: str, limit: int = 320) -> str:
    result = " ".join(str(value or "").split())
    if not result:
        raise ValueError(f"{field} is required")
    if len(result) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    _reject_forbidden_material(result, path=field)
    return result


def _text_list(
    value: object,
    *,
    field: str,
    minimum: int = 0,
    maximum: int = 12,
    item_limit: int = 320,
) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field} must be a list")
    if not minimum <= len(value) <= maximum:
        raise ValueError(f"{field} must contain between {minimum} and {maximum} items")
    return [
        _text(item, field=f"{field}[{index}]", limit=item_limit)
        for index, item in enumerate(value)
    ]


def _iso_date(value: object, *, field: str) -> str:
    result = _text(value, field=field, limit=40)
    try:
        if "T" in result:
            datetime.fromisoformat(result.replace("Z", "+00:00"))
        else:
            date.fromisoformat(result)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 date or datetime") from exc
    return result


def _required_true(payload: Mapping[str, Any], field: str) -> bool:
    if payload.get(field) is not True:
        raise ValueError(f"{field} must be true")
    return True


def _public_https_url(value: object, *, field: str) -> str:
    result = _text(value, field=field, limit=500)
    parts = urlsplit(result)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise ValueError(f"{field} must be a public https URL without auth")
    host = parts.hostname.lower()
    if (
        parts.query
        or parts.fragment
        or host == "localhost"
        or host.endswith((".local", ".internal", ".corp", ".lan"))
    ):
        raise ValueError(
            f"{field} must be a public https URL without query or fragment"
        )
    try:
        address = ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError(f"{field} must use a public host")
    return result


def _source(value: object, *, field: str) -> dict[str, Any]:
    source = _mapping(value, field=field)
    allowed = {"source_id", "source_tier", "url", "provider_label", "observed_at"}
    if set(source) - allowed:
        raise ValueError(f"{field} has unsupported fields")
    tier = _text(source.get("source_tier"), field=f"{field}.source_tier", limit=32)
    if tier not in ALLOWED_SOURCE_TIERS:
        raise ValueError(
            f"{field}.source_tier must be one of {sorted(ALLOWED_SOURCE_TIERS)}"
        )
    url = source.get("url")
    provider = source.get("provider_label")
    if bool(url) == bool(provider):
        raise ValueError(f"{field} requires exactly one of url or provider_label")
    return {
        "source_id": _text(
            source.get("source_id"), field=f"{field}.source_id", limit=96
        ),
        "source_tier": tier,
        "url": _public_https_url(url, field=f"{field}.url") if url else None,
        "provider_label": _text(provider, field=f"{field}.provider_label", limit=120)
        if provider
        else None,
        "observed_at": _iso_date(
            source.get("observed_at"), field=f"{field}.observed_at"
        ),
    }


def _axes(value: object, *, field: str) -> dict[str, str]:
    axes = _mapping(value, field=field)
    if set(axes) != set(EVIDENCE_AXES):
        raise ValueError(f"{field} must contain exactly the six frozen evidence axes")
    result: dict[str, str] = {}
    for axis in EVIDENCE_AXES:
        state = _text(axes.get(axis), field=f"{field}.{axis}", limit=24)
        if state not in ALLOWED_AXIS_STATES:
            raise ValueError(
                f"{field}.{axis} must be one of {sorted(ALLOWED_AXIS_STATES)}"
            )
        result[axis] = state
    return result


def _card(value: object, *, index: int) -> dict[str, Any]:
    field = f"cards[{index}]"
    card = _mapping(value, field=field)
    allowed = {
        "schema_version",
        "entity_id",
        "role",
        "classification",
        "peer_group",
        "relative_signal",
        "source_refs",
        "cross_validation_status",
        "axes",
        "incremental_efficiency_signals",
        "supporting_facts",
        "counter_evidence",
        "missing_fields",
        "fully_diluted_valuation_status",
        "terminal_risk_status",
    }
    if set(card) - allowed:
        raise ValueError(f"{field} has unsupported fields")
    if card.get("schema_version") != FINANCE_VALUE_DISCOVERY_CARD_SCHEMA_VERSION:
        raise ValueError(
            f"{field}.schema_version must be {FINANCE_VALUE_DISCOVERY_CARD_SCHEMA_VERSION}"
        )
    role = _text(card.get("role"), field=f"{field}.role", limit=24)
    classification = _text(
        card.get("classification"), field=f"{field}.classification", limit=16
    ).upper()
    if role not in ALLOWED_ROLES or classification not in ALLOWED_CLASSIFICATIONS:
        raise ValueError(f"{field} has unsupported role or classification")
    if (role == "control") != (classification == "CONTROL"):
        raise ValueError(f"{field} control role and CONTROL classification must match")
    relative_signal = _text(
        card.get("relative_signal"), field=f"{field}.relative_signal", limit=40
    )
    if relative_signal not in ALLOWED_RELATIVE_SIGNALS:
        raise ValueError(
            f"{field}.relative_signal must be one of {sorted(ALLOWED_RELATIVE_SIGNALS)}"
        )
    if role == "control" and relative_signal != "not_applicable":
        raise ValueError(f"{field} controls require relative_signal=not_applicable")

    source_values = card.get("source_refs")
    if (
        not isinstance(source_values, Sequence)
        or isinstance(source_values, (str, bytes, bytearray))
        or not 1 <= len(source_values) <= 12
    ):
        raise ValueError(f"{field}.source_refs must contain between 1 and 12 items")
    sources = [
        _source(item, field=f"{field}.source_refs[{i}]")
        for i, item in enumerate(source_values)
    ]
    if len({item["source_id"] for item in sources}) != len(sources):
        raise ValueError(f"{field}.source_refs must use unique source ids")
    cross_validation = _text(
        card.get("cross_validation_status"),
        field=f"{field}.cross_validation_status",
        limit=40,
    )
    if cross_validation not in ALLOWED_CROSS_VALIDATION:
        raise ValueError(f"{field}.cross_validation_status is unsupported")
    tiers = {str(item["source_tier"]) for item in sources}
    if cross_validation == "primary_corroborated" and (
        "primary" not in tiers or len(sources) < 2
    ):
        raise ValueError(
            f"{field} primary_corroborated requires primary plus another source"
        )
    if cross_validation == "independent_corroborated" and (
        "independent" not in tiers or len(sources) < 2
    ):
        raise ValueError(
            f"{field} independent_corroborated requires independent plus another source"
        )
    if cross_validation == "single_source" and len(sources) != 1:
        raise ValueError(f"{field} single_source requires exactly one source")

    normalized_axes = _axes(card.get("axes"), field=f"{field}.axes")
    efficiency = _text_list(
        card.get("incremental_efficiency_signals"),
        field=f"{field}.incremental_efficiency_signals",
        maximum=8,
    )
    supporting = _text_list(
        card.get("supporting_facts"), field=f"{field}.supporting_facts", minimum=1
    )
    counter = _text_list(
        card.get("counter_evidence"), field=f"{field}.counter_evidence", minimum=1
    )
    missing = _text_list(
        card.get("missing_fields"), field=f"{field}.missing_fields", maximum=10
    )
    valuation = _text(
        card.get("fully_diluted_valuation_status"),
        field=f"{field}.fully_diluted_valuation_status",
        limit=24,
    )
    terminal = _text(
        card.get("terminal_risk_status"),
        field=f"{field}.terminal_risk_status",
        limit=24,
    )
    if (
        valuation not in ALLOWED_VALUATION_STATES
        or terminal not in ALLOWED_TERMINAL_RISK_STATES
    ):
        raise ValueError(f"{field} has unsupported valuation or terminal risk state")
    if classification == "A":
        if any(state != "supported" for state in normalized_axes.values()):
            raise ValueError(f"{field} A requires all six axes supported")
        if (
            len(efficiency) < 2
            or missing
            or valuation != "verified"
            or terminal != "bounded"
        ):
            raise ValueError(
                f"{field} A requires efficiency, complete valuation, and bounded terminal risk"
            )
        if cross_validation not in {"primary_corroborated", "independent_corroborated"}:
            raise ValueError(f"{field} A requires corroborated evidence")
    if classification == "B" and all(
        state in {"refuted", "missing"} for state in normalized_axes.values()
    ):
        raise ValueError(f"{field} B requires at least one supported or mixed axis")
    return {
        "schema_version": FINANCE_VALUE_DISCOVERY_CARD_SCHEMA_VERSION,
        "entity_id": _text(card.get("entity_id"), field=f"{field}.entity_id", limit=96),
        "role": role,
        "classification": classification,
        "peer_group": _text(
            card.get("peer_group"), field=f"{field}.peer_group", limit=80
        ),
        "relative_signal": relative_signal,
        "source_refs": sources,
        "cross_validation_status": cross_validation,
        "axes": normalized_axes,
        "incremental_efficiency_signals": efficiency,
        "supporting_facts": supporting,
        "counter_evidence": counter,
        "missing_fields": missing,
        "fully_diluted_valuation_status": valuation,
        "terminal_risk_status": terminal,
    }


def build_finance_value_discovery_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    _reject_forbidden_material(payload)
    allowed = {
        "schema_version",
        "as_of",
        "routes",
        "screen_groups",
        "universe_frozen",
        "controls_frozen",
        "candidate_selected_after_screen",
        "pit_required",
        "full_terminal_outcomes_required",
        "dilution_required",
        "permanent_loss_required",
        "max_successor_count",
        "cards",
    }
    if set(payload) - allowed:
        raise ValueError("input has unsupported fields")
    if payload.get("schema_version") != FINANCE_VALUE_DISCOVERY_INPUT_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {FINANCE_VALUE_DISCOVERY_INPUT_SCHEMA_VERSION}"
        )
    as_of = _iso_date(payload.get("as_of"), field="as_of")
    routes = _text_list(payload.get("routes"), field="routes", minimum=1, maximum=2)
    if len(routes) != len(set(routes)) or set(routes) - ALLOWED_ROUTES:
        raise ValueError(f"routes must be unique values from {sorted(ALLOWED_ROUTES)}")
    screen_groups = _text_list(
        payload.get("screen_groups"),
        field="screen_groups",
        minimum=1,
        maximum=12,
        item_limit=80,
    )
    if len(screen_groups) != len(set(screen_groups)):
        raise ValueError("screen_groups must be unique")
    if "de_beta_mispricing" in routes and len(screen_groups) < 3:
        raise ValueError(
            "de_beta_mispricing requires at least three unrelated screen groups"
        )
    frozen_contract = {
        name: _required_true(payload, name)
        for name in (
            "universe_frozen",
            "controls_frozen",
            "candidate_selected_after_screen",
            "pit_required",
            "full_terminal_outcomes_required",
            "dilution_required",
            "permanent_loss_required",
        )
    }
    max_successor_count = payload.get("max_successor_count")
    if (
        not isinstance(max_successor_count, int)
        or isinstance(max_successor_count, bool)
        or not 0 <= max_successor_count <= 1
    ):
        raise ValueError("max_successor_count must be 0 or 1")
    raw_cards = payload.get("cards")
    if (
        not isinstance(raw_cards, Sequence)
        or isinstance(raw_cards, (str, bytes, bytearray))
        or not 2 <= len(raw_cards) <= 40
    ):
        raise ValueError("cards must contain between 2 and 40 items")
    cards = [_card(item, index=index) for index, item in enumerate(raw_cards)]
    ids = [str(item["entity_id"]) for item in cards]
    if len(ids) != len(set(ids)):
        raise ValueError("cards must use unique entity ids")
    if not any(item["role"] == "candidate" for item in cards) or not any(
        item["role"] == "control" for item in cards
    ):
        raise ValueError("cards must include candidates and controls")
    cutoff = date.fromisoformat(as_of[:10])
    for card in cards:
        for source in card["source_refs"]:
            if date.fromisoformat(str(source["observed_at"])[:10]) > cutoff:
                raise ValueError(
                    f"card {card['entity_id']} source {source['source_id']} is after as_of"
                )

    control_counts = Counter(
        str(card["peer_group"]) for card in cards if card["role"] == "control"
    )
    for card in cards:
        card["de_beta_control_count"] = control_counts.get(str(card["peer_group"]), 0)
        card["de_beta_supported"] = (
            card["role"] == "candidate"
            and card["relative_signal"] == "idiosyncratic_support"
            and card["de_beta_control_count"] >= 2
        )
        if (
            "de_beta_mispricing" in routes
            and card["classification"] == "A"
            and not card["de_beta_supported"]
        ):
            raise ValueError(
                f"card {card['entity_id']} A requires idiosyncratic support and at least two frozen peer controls"
            )

    counts = Counter(str(card["classification"]) for card in cards)
    a_candidates = [
        str(card["entity_id"]) for card in cards if card["classification"] == "A"
    ]
    b_successors = [
        str(card["entity_id"])
        for card in cards
        if card["classification"] == "B"
        and ("de_beta_mispricing" not in routes or card["de_beta_supported"])
    ]
    if a_candidates:
        next_action = "falsify_a_candidates"
        next_targets = a_candidates
    elif b_successors and max_successor_count:
        next_action = "select_at_most_one_b_successor"
        next_targets = b_successors[:1]
    else:
        next_action = "close_no_validated_candidates"
        next_targets = []

    projection = {
        "schema_version": FINANCE_VALUE_DISCOVERY_PROJECTION_SCHEMA_VERSION,
        "candidate_count": sum(card["role"] == "candidate" for card in cards),
        "control_count": sum(card["role"] == "control" for card in cards),
        "screen_group_count": len(screen_groups),
        "classification_counts": {
            classification: counts.get(classification, 0)
            for classification in ("A", "B", "C", "CONTROL")
        },
        "next_action": next_action,
        "next_targets": next_targets,
        "max_successor_count": max_successor_count,
        "continuous_watch_allowed": False,
        "threshold_relaxation_allowed": False,
        "close_without_relaxing_thresholds": next_action
        == "close_no_validated_candidates",
    }
    return {
        "ok": True,
        "schema_version": FINANCE_VALUE_DISCOVERY_PACKET_SCHEMA_VERSION,
        "mode": "finance-value-discovery",
        "as_of": as_of,
        "routes": routes,
        "screen_groups": screen_groups,
        "frozen_contract": frozen_contract,
        "cards": cards,
        "projection": projection,
        "boundary": {
            "public_sources_only": True,
            "raw_provider_payload_recorded": False,
            "private_source_content_read": False,
            "account_or_portfolio_accessed": False,
            "investment_advice": False,
            "price_target_allowed": False,
            "trading_allowed": False,
            "continuous_watch_allowed": False,
            "human_decision_owner": True,
        },
        "truth_contract": {
            "cross_sectional_screen_precedes_named_candidate": True,
            "peer_controls_are_counterfactuals_not_candidates": True,
            "group_wide_derating_is_not_idiosyncratic_alpha": True,
            "classification_requires_support_and_counter_evidence": True,
            "filing_review_follows_screening": True,
            "missing_fields_are_not_silently_filled": True,
            "connector_observations_are_inputs_not_truth": True,
        },
    }


def render_finance_value_discovery_markdown(payload: Mapping[str, Any]) -> str:
    projection = (
        payload.get("projection")
        if isinstance(payload.get("projection"), Mapping)
        else {}
    )
    lines = [
        "# LoopX Finance Value Discovery",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- as_of: `{payload.get('as_of')}`",
        f"- next_action: `{projection.get('next_action')}`",
        f"- continuous_watch_allowed: `{projection.get('continuous_watch_allowed')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
        return "\n".join(lines).rstrip() + "\n"
    lines.extend(["", "## Evidence Cards", ""])
    for card in payload.get("cards") or []:
        if not isinstance(card, Mapping):
            continue
        lines.extend(
            [
                f"### `{card.get('entity_id')}`",
                "",
                f"- classification: `{card.get('classification')}`",
                f"- peer_group: `{card.get('peer_group')}`",
                f"- relative_signal: `{card.get('relative_signal')}`",
                f"- de_beta_control_count: `{card.get('de_beta_control_count')}`",
                "- counter_evidence:",
            ]
        )
        lines.extend(f"  - {item}" for item in card.get("counter_evidence") or [])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
