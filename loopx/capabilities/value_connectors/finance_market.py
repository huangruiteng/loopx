from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FINANCE_MARKET_SNAPSHOT_CANARY_PACKET_SCHEMA_VERSION = (
    "finance_market_snapshot_canary_packet_v0"
)
FINANCE_MARKET_SNAPSHOT_ERROR_SCHEMA_VERSION = "finance_market_snapshot_canary_error_v0"

EASTMONEY_SOURCE_ID = "eastmoney_public_quote"
FINANCE_MARKET_SNAPSHOT_SOURCES = {
    EASTMONEY_SOURCE_ID,
    "futu_opend",
    "private_portfolio",
    "paid_data",
    "trading",
    "captcha",
    "credential",
}
GATED_FINANCE_SOURCES = FINANCE_MARKET_SNAPSHOT_SOURCES - {EASTMONEY_SOURCE_ID}

ALLOWED_SYMBOLS = {
    "sh600519": {
        "secid": "1.600519",
        "human_url": "https://quote.eastmoney.com/sh600519.html",
    },
    "sz000001": {
        "secid": "0.000001",
        "human_url": "https://quote.eastmoney.com/sz000001.html",
    },
}

EASTMONEY_FIELDS = (
    "f57",  # symbol
    "f58",  # name
    "f43",  # latest price, scaled by 100
    "f169",  # price change, scaled by 100
    "f170",  # percent change, scaled by 100
    "f47",  # volume
    "f48",  # turnover
    "f60",  # previous close, scaled by 100
    "f86",  # provider timestamp
    "f116",  # market cap
)
GATED_PROVIDER_KEYS = {
    "account",
    "account_id",
    "ak",
    "body",
    "captcha",
    "cookie",
    "credential",
    "holding",
    "order",
    "portfolio",
    "private",
    "raw",
    "secret",
    "sk",
    "token",
    "trade",
    "trading",
}


def _compact_error(exc: BaseException) -> str:
    return " ".join(str(exc).split())[:180]


def _scaled(value: Any) -> float | int | str | None:
    if value in (None, "-", ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(value / 100, 2)
    try:
        return round(float(str(value)) / 100, 2)
    except ValueError:
        return str(value)[:80]


def _plain_number(value: Any) -> int | float | str | None:
    if value in (None, "-", ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        parsed = float(str(value))
    except ValueError:
        return str(value)[:80]
    return int(parsed) if parsed.is_integer() else parsed


def _normalise_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().lower()
    if text not in ALLOWED_SYMBOLS:
        raise ValueError(f"symbol must be one of {sorted(ALLOWED_SYMBOLS)}")
    return text


def _load_provider_data(provider_payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(provider_payload, Mapping):
        return {}
    data = provider_payload.get("data")
    if isinstance(data, Mapping):
        return data
    return provider_payload


def _gated_provider_keys(provider_data: Mapping[str, Any]) -> list[str]:
    return sorted(
        str(key)
        for key in provider_data
        if str(key).lower() in GATED_PROVIDER_KEYS
    )


def _quote_fields(provider_data: Mapping[str, Any], *, requested_symbol: str) -> dict[str, Any]:
    return {
        "symbol": str(provider_data.get("f57") or requested_symbol.removeprefix("sh").removeprefix("sz"))[:32],
        "name": str(provider_data.get("f58"))[:80] if provider_data.get("f58") else None,
        "latest_price": _scaled(provider_data.get("f43")),
        "price_change": _scaled(provider_data.get("f169")),
        "pct_change": _scaled(provider_data.get("f170")),
        "volume": _plain_number(provider_data.get("f47")),
        "turnover": _plain_number(provider_data.get("f48")),
        "previous_close": _scaled(provider_data.get("f60")),
        "market_cap": _plain_number(provider_data.get("f116")),
    }


def _fetch_eastmoney_quote(symbol: str, *, timeout_seconds: float) -> Mapping[str, Any]:
    secid = ALLOWED_SYMBOLS[symbol]["secid"]
    fields = ",".join(EASTMONEY_FIELDS)
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields={fields}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "LoopX-value-connectors",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - secid is allowlisted above.
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("Eastmoney response must be a JSON object")
    return payload


def _snapshot_from_provider(
    *,
    symbol: str,
    provider_payload: Mapping[str, Any] | None,
    observed_at: str,
) -> tuple[dict[str, Any], int]:
    provider_data = _load_provider_data(provider_payload)
    gated_keys = _gated_provider_keys(provider_data)
    present_fields = sorted(str(key) for key in provider_data if str(key) in EASTMONEY_FIELDS)
    return (
        {
            "symbol": symbol,
            "source_id": EASTMONEY_SOURCE_ID,
            "source_url": ALLOWED_SYMBOLS[symbol]["human_url"],
            "access_mode": "public_metadata_only",
            "freshness_label": "source_unverified",
            "observed_at": observed_at,
            "provider_timestamp": provider_data.get("f86") if provider_data else None,
            "quote_fields": _quote_fields(provider_data, requested_symbol=symbol),
            "provider_fields_present": present_fields,
            "missing_or_unverified": [
                "provider_terms",
                "throttling",
                "official_field_map",
                "freshness_semantics",
            ],
            "raw_provider_payload_recorded": False,
            "investment_advice": False,
            "supports_or_challenges": "manual_review_required",
        },
        len(gated_keys),
    )


def build_finance_market_snapshot_packet(
    *,
    symbol: str,
    source: str = EASTMONEY_SOURCE_ID,
    provider_payload: Mapping[str, Any] | None = None,
    fetch_metadata: bool = False,
    timeout_seconds: float = 10.0,
    observed_at: str = "2026-07-08T00:00:00Z",
    thesis_id: str | None = None,
    thesis: str | None = None,
) -> dict[str, Any]:
    normalised_symbol = _normalise_symbol(symbol)
    if source not in FINANCE_MARKET_SNAPSHOT_SOURCES:
        raise ValueError(f"source must be one of {sorted(FINANCE_MARKET_SNAPSHOT_SOURCES)}")
    if source in GATED_FINANCE_SOURCES:
        raise ValueError(f"{source} requires an exact user gate before any finance connector read")

    read_error: str | None = None
    live_payload: Mapping[str, Any] | None = None
    if fetch_metadata:
        try:
            live_payload = _fetch_eastmoney_quote(
                normalised_symbol,
                timeout_seconds=timeout_seconds,
            )
        except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            read_error = _compact_error(exc)

    payload_source = live_payload if live_payload is not None else provider_payload
    snapshot, gated_field_count = _snapshot_from_provider(
        symbol=normalised_symbol,
        provider_payload=payload_source,
        observed_at=observed_at,
    )
    validation_errors = []
    validation_warnings = []
    if read_error:
        validation_errors.append("metadata read failed; retry later or use --metadata-json")
    if payload_source is None:
        validation_warnings.append("no provider metadata supplied; emitted reference-only canary packet")

    connector_call = {
        "schema_version": "connector_call_intent_v0",
        "call_id": f"{normalised_symbol}_finance_snapshot_canary",
        "connector_id": "finance_market_snapshot",
        "connector_kind": "custom_connector",
        "channel": "public finance metadata snapshot",
        "stage": "observe",
        "target_ref": normalised_symbol,
        "target_url": ALLOWED_SYMBOLS[normalised_symbol]["human_url"],
        "access_mode": "public_metadata_only",
        "external_reads_allowed": True,
        "external_writes_allowed": False,
        "external_write_requested": False,
        "requires_user_approval": False,
        "approval_gate_id": None,
        "value_axis": "capability",
        "money_metric": "reduce human time spent collecting public market facts",
        "success_metric": "compact source-labeled quote snapshot for human thesis review",
        "kill_condition": "source terms, freshness, symbol mapping, credential, paid-data, portfolio, or trading boundary cannot be verified",
        "promotion_target": "human_review_packet",
    }

    return {
        "ok": not validation_errors,
        "schema_version": FINANCE_MARKET_SNAPSHOT_CANARY_PACKET_SCHEMA_VERSION,
        "mode": "finance-market-snapshot-canary",
        "connector_id": "finance_market_snapshot",
        "connector_call": connector_call,
        "external_reads_performed": bool(fetch_metadata),
        "external_writes_performed": False,
        "account_signup_performed": False,
        "private_source_content_read": False,
        "raw_provider_payload_recorded": False,
        "restricted_material_recorded": False,
        "non_investment_advice": True,
        "autotrade_allowed": False,
        "snapshots": [snapshot],
        "research_context": {
            "human_decision_owner": True,
            "thesis_id": thesis_id,
            "thesis": thesis,
            "supports_or_challenges": "manual_review_required",
            "next_action": "human reviews whether this public fact changes a thesis",
        },
        "read_error": read_error,
        "validation": {
            "ok": not validation_errors,
            "errors": validation_errors,
            "warnings": validation_warnings,
            "symbol_allowlist": sorted(ALLOWED_SYMBOLS),
            "source": source,
            "gated_provider_field_count": gated_field_count,
        },
    }


def render_finance_market_snapshot_markdown(payload: dict[str, Any]) -> str:
    research_context = (
        payload.get("research_context") if isinstance(payload.get("research_context"), Mapping) else {}
    )
    validation = payload.get("validation") if isinstance(payload.get("validation"), Mapping) else {}
    lines = [
        "# LoopX Finance Market Snapshot Canary",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- external_reads_performed: `{payload.get('external_reads_performed')}`",
        f"- external_writes_performed: `{payload.get('external_writes_performed')}`",
        f"- raw_provider_payload_recorded: `{payload.get('raw_provider_payload_recorded')}`",
        f"- non_investment_advice: `{payload.get('non_investment_advice')}`",
        f"- supports_or_challenges: `{research_context.get('supports_or_challenges')}`",
        "",
    ]
    for snapshot in payload.get("snapshots") or []:
        if not isinstance(snapshot, Mapping):
            continue
        fields = snapshot.get("quote_fields") if isinstance(snapshot.get("quote_fields"), Mapping) else {}
        lines.extend(
            [
                f"## {snapshot.get('symbol')}",
                "",
                f"- source_id: `{snapshot.get('source_id')}`",
                f"- freshness_label: `{snapshot.get('freshness_label')}`",
                f"- observed_at: `{snapshot.get('observed_at')}`",
                f"- latest_price: `{fields.get('latest_price')}`",
                f"- pct_change: `{fields.get('pct_change')}`",
                f"- source_url: {snapshot.get('source_url')}",
                "",
            ]
        )
    if payload.get("read_error"):
        lines.extend(["## Read Error", "", str(payload.get("read_error")), ""])
    errors = validation.get("errors") if isinstance(validation.get("errors"), list) else []
    warnings = validation.get("warnings") if isinstance(validation.get("warnings"), list) else []
    if errors:
        lines.extend(["## Validation Errors", ""])
        lines.extend(f"- {error}" for error in errors)
    if warnings:
        lines.extend(["## Validation Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    if payload.get("error"):
        lines.extend(["## Error", "", str(payload.get("error"))])
    return "\n".join(lines).rstrip() + "\n"
