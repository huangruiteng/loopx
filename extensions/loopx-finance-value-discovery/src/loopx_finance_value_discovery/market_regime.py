from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .reducer import (
    _iso_date,
    _public_https_url,
    _reject_forbidden_material,
    _text,
)


FINANCE_MARKET_REGIME_INPUT_SCHEMA_VERSION = "finance_market_regime_input_v0"
FINANCE_MARKET_REGIME_PACKET_SCHEMA_VERSION = "finance_market_regime_packet_v0"
FINANCE_MARKET_REGIME_RULE_VERSION = {
    "us": "us_precrash_repair_rules_v0",
    "a_share": "a_share_precrash_repair_rules_v0",
}

RECOVERY_FAILURE_FLAGS = {
    "new_low_after_first_repair",
    "stress_relapse",
    "trend_reloss",
}

COMMON_METRICS = {
    "bounce_from_20d_low_pct",
    "drawdown_from_252d_high_pct",
    "primary_return_10d_pct",
    "primary_sma20_slope_10d_pct",
    "primary_sma50_slope_20d_pct",
    "primary_vs_sma20_pct",
    "primary_vs_sma50_pct",
    "primary_vs_sma200_pct",
    "recovery_anchor_drawdown_pct",
}
US_METRICS = COMMON_METRICS | {
    "credit_return_20d_pct",
    "credit_vs_sma50_pct",
    "credit_vs_sma200_pct",
    "equal_weight_relative_return_20d_pct",
    "equal_weight_vs_sma50_pct",
    "qqq_relative_return_20d_pct",
    "qqq_vs_sma50_pct",
    "vix_level",
}
A_SHARE_METRICS = COMMON_METRICS | {
    "broad_below_sma50_count",
    "broad_relative_return_20d_pct",
    "primary_return_20d_pct",
    "primary_return_60d_pct",
    "turnover_20d_vs_120d_ratio",
    "turnover_ratio_peak_60d",
}


def _number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


def _metrics(value: object, *, market: str) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError("metrics must be an object")
    required = US_METRICS if market == "us" else A_SHARE_METRICS
    if set(value) != required:
        missing = sorted(required - set(value))
        extra = sorted(set(value) - required)
        raise ValueError(
            f"metrics must match {market} rule profile; missing={missing}, extra={extra}"
        )
    result = {
        name: _number(value[name], field=f"metrics.{name}") for name in sorted(required)
    }
    if market == "a_share":
        count = result["broad_below_sma50_count"]
        if not count.is_integer() or not 0 <= count <= 3:
            raise ValueError("metrics.broad_below_sma50_count must be 0, 1, 2, or 3")
        for name in ("turnover_20d_vs_120d_ratio", "turnover_ratio_peak_60d"):
            if result[name] < 0:
                raise ValueError(f"metrics.{name} must be non-negative")
    if market == "us" and not 0 <= result["vix_level"] <= 200:
        raise ValueError("metrics.vix_level must be between 0 and 200")
    return result


def _source(value: object, *, index: int, as_of: str) -> dict[str, Any]:
    field = f"source_refs[{index}]"
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    allowed = {"source_id", "source_tier", "url", "provider_label", "observed_at"}
    if set(value) - allowed:
        raise ValueError(f"{field} has unsupported fields")
    tier = _text(value.get("source_tier"), field=f"{field}.source_tier", limit=32)
    if tier not in {"primary", "independent", "market_data"}:
        raise ValueError(f"{field}.source_tier is unsupported")
    url = value.get("url")
    provider = value.get("provider_label")
    if bool(url) == bool(provider):
        raise ValueError(f"{field} requires exactly one of url or provider_label")
    observed_at = _iso_date(value.get("observed_at"), field=f"{field}.observed_at")
    if observed_at[:10] > as_of[:10]:
        raise ValueError(f"{field}.observed_at must not be after as_of")
    return {
        "source_id": _text(
            value.get("source_id"), field=f"{field}.source_id", limit=96
        ),
        "source_tier": tier,
        "url": _public_https_url(url, field=f"{field}.url") if url else None,
        "provider_label": _text(provider, field=f"{field}.provider_label", limit=120)
        if provider
        else None,
        "observed_at": observed_at,
    }


def _sources(value: object, *, as_of: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("source_refs must be a list")
    if not 1 <= len(value) <= 12:
        raise ValueError("source_refs must contain between 1 and 12 items")
    result = [
        _source(item, index=index, as_of=as_of) for index, item in enumerate(value)
    ]
    ids = [item["source_id"] for item in result]
    if len(ids) != len(set(ids)):
        raise ValueError("source_refs must use unique source ids")
    return result


def _failure_flags(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("recovery_failure_flags must be a list")
    flags = [
        _text(item, field=f"recovery_failure_flags[{index}]", limit=48)
        for index, item in enumerate(value)
    ]
    if len(flags) != len(set(flags)) or set(flags) - RECOVERY_FAILURE_FLAGS:
        raise ValueError(
            "recovery_failure_flags must be unique values from "
            f"{sorted(RECOVERY_FAILURE_FLAGS)}"
        )
    return flags


def _layer(layer_id: str, triggered: bool, evidence: str) -> dict[str, Any]:
    return {"layer_id": layer_id, "triggered": triggered, "evidence": evidence}


def _us_layers(
    metrics: Mapping[str, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    precrash = [
        _layer(
            "vulnerability",
            metrics["vix_level"] <= 20 and metrics["primary_vs_sma200_pct"] >= 0,
            "VIX <= 20 and the primary index is at or above its 200-day average.",
        ),
        _layer(
            "leadership_or_breadth_break",
            (
                metrics["qqq_relative_return_20d_pct"] <= -5
                and metrics["qqq_vs_sma50_pct"] < 0
            )
            or (
                metrics["equal_weight_relative_return_20d_pct"] <= -3
                and metrics["equal_weight_vs_sma50_pct"] < 0
            ),
            "QQQ trails by at least 5pp below its 50-day average, or equal weight trails by at least 3pp below its 50-day average.",
        ),
        _layer(
            "credit_confirmation",
            metrics["credit_vs_sma200_pct"] < 0
            and metrics["credit_return_20d_pct"] <= -1,
            "The high-yield proxy is below its 200-day average and its 20-day return is <= -1%.",
        ),
        _layer(
            "trend_confirmation",
            metrics["primary_vs_sma200_pct"] < 0
            and metrics["primary_sma50_slope_20d_pct"] < 0,
            "The primary index is below its 200-day average and its 50-day average has a negative 20-day slope.",
        ),
    ]
    recovery = [
        _layer(
            "rebound_persistence",
            metrics["primary_vs_sma20_pct"] > 0
            and metrics["primary_return_10d_pct"] >= 3
            and metrics["bounce_from_20d_low_pct"] >= 5,
            "The index is above its 20-day average, up at least 3% in 10 days, and at least 5% above its 20-day low.",
        ),
        _layer(
            "short_trend_reclaim",
            metrics["primary_vs_sma50_pct"] > 0
            and metrics["primary_sma20_slope_10d_pct"] > 0,
            "The index is above its 50-day average and its 20-day average is rising.",
        ),
        _layer(
            "participation_repair",
            metrics["equal_weight_relative_return_20d_pct"] > 0,
            "The equal-weight index has outperformed the cap-weighted index over 20 days.",
        ),
        _layer(
            "stress_repair",
            metrics["credit_vs_sma50_pct"] > 0 and metrics["vix_level"] < 25,
            "The high-yield proxy is above its 50-day average and VIX is below 25.",
        ),
    ]
    return precrash, recovery


def _a_share_layers(
    metrics: Mapping[str, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    precrash = [
        _layer(
            "crowding_or_complacency",
            metrics["primary_vs_sma200_pct"] >= 0
            and (
                metrics["primary_return_60d_pct"] >= 12
                or metrics["turnover_20d_vs_120d_ratio"] >= 1.25
            ),
            "The primary index is above its 200-day average with either a >=12% 60-day rise or turnover >=1.25x its 120-day average.",
        ),
        _layer(
            "leadership_or_breadth_break",
            metrics["broad_relative_return_20d_pct"] <= -4
            and metrics["broad_below_sma50_count"] >= 2,
            "The three broad or growth proxies trail the primary index by at least 4pp on average and at least two are below their 50-day averages.",
        ),
        _layer(
            "turnover_or_leverage_unwind",
            metrics["turnover_ratio_peak_60d"] >= 1.25
            and metrics["turnover_20d_vs_120d_ratio"] <= 0.9
            and metrics["primary_return_20d_pct"] < 0,
            "Turnover has fallen from a >=1.25x 60-day peak to <=0.9x while the primary index has a negative 20-day return.",
        ),
        _layer(
            "trend_confirmation",
            metrics["primary_vs_sma200_pct"] < 0
            and metrics["primary_sma50_slope_20d_pct"] < 0,
            "The primary index is below its 200-day average and its 50-day average has a negative 20-day slope.",
        ),
    ]
    recovery = [
        _layer(
            "rebound_persistence",
            metrics["primary_vs_sma20_pct"] > 0
            and metrics["primary_return_10d_pct"] >= 5
            and metrics["bounce_from_20d_low_pct"] >= 8,
            "The index is above its 20-day average, up at least 5% in 10 days, and at least 8% above its 20-day low.",
        ),
        _layer(
            "short_trend_reclaim",
            metrics["primary_vs_sma50_pct"] > 0
            and metrics["primary_sma20_slope_10d_pct"] > 0,
            "The index is above its 50-day average and its 20-day average is rising.",
        ),
        _layer(
            "participation_repair",
            metrics["broad_relative_return_20d_pct"] > 0
            and metrics["broad_below_sma50_count"] <= 1,
            "Broad and growth proxies outperform over 20 days and no more than one remains below its 50-day average.",
        ),
        _layer(
            "stress_repair",
            0.8 <= metrics["turnover_20d_vs_120d_ratio"] <= 1.4,
            "Turnover is between 0.8x and 1.4x its 120-day average, avoiding both dry liquidity and rebound blow-off.",
        ),
    ]
    return precrash, recovery


def _state_packet(
    *,
    layers: list[dict[str, Any]],
    confirmed_layer_ids: set[str],
    observation_required_id: str | None = None,
) -> dict[str, Any]:
    triggered = [str(item["layer_id"]) for item in layers if item["triggered"]]
    clear = [str(item["layer_id"]) for item in layers if not item["triggered"]]
    score = len(triggered)
    confirmed = score >= 3 and bool(set(triggered) & confirmed_layer_ids)
    observed = score >= 2 and (
        observation_required_id is None or observation_required_id in triggered
    )
    return {
        "score": score,
        "triggered_layers": triggered,
        "clear_layers": clear,
        "supporting_evidence": [
            item["evidence"] for item in layers if item["triggered"]
        ],
        "conflicting_evidence": [
            item["evidence"] for item in layers if not item["triggered"]
        ],
        "observed": observed,
        "confirmed": confirmed,
        "layers": layers,
    }


def build_finance_market_regime_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    _reject_forbidden_material(payload)
    allowed = {
        "schema_version",
        "as_of",
        "market",
        "rule_version",
        "point_in_time_data",
        "lookahead_free",
        "metrics",
        "recovery_failure_flags",
        "source_refs",
    }
    if set(payload) - allowed:
        raise ValueError("market-regime input has unsupported fields")
    if payload.get("schema_version") != FINANCE_MARKET_REGIME_INPUT_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {FINANCE_MARKET_REGIME_INPUT_SCHEMA_VERSION}"
        )
    as_of = _iso_date(payload.get("as_of"), field="as_of")
    market = _text(payload.get("market"), field="market", limit=24)
    if market not in FINANCE_MARKET_REGIME_RULE_VERSION:
        raise ValueError("market must be us or a_share")
    expected_rule = FINANCE_MARKET_REGIME_RULE_VERSION[market]
    if payload.get("rule_version") != expected_rule:
        raise ValueError(f"rule_version must be {expected_rule}")
    if payload.get("point_in_time_data") is not True:
        raise ValueError("point_in_time_data must be true")
    if payload.get("lookahead_free") is not True:
        raise ValueError("lookahead_free must be true")
    metrics = _metrics(payload.get("metrics"), market=market)
    current_drawdown = metrics["drawdown_from_252d_high_pct"]
    recovery_anchor = metrics["recovery_anchor_drawdown_pct"]
    if current_drawdown > 0 or recovery_anchor > current_drawdown:
        raise ValueError(
            "recovery_anchor_drawdown_pct must be non-positive and no greater "
            "than drawdown_from_252d_high_pct"
        )
    sources = _sources(payload.get("source_refs"), as_of=as_of)
    flags = _failure_flags(payload.get("recovery_failure_flags"))

    if market == "us":
        pre_layers, recovery_layers = _us_layers(metrics)
        pre_confirmers = {"credit_confirmation", "trend_confirmation"}
        drawdown_threshold = -15.0
        proxy_limitations = [
            "HYG is a tradable credit proxy, not a point-in-time excess bond premium series.",
            "QQQ and equal-weight relative returns are price proxies for leadership and breadth, not advance-decline counts.",
        ]
    else:
        pre_layers, recovery_layers = _a_share_layers(metrics)
        pre_confirmers = {"turnover_or_leverage_unwind", "trend_confirmation"}
        drawdown_threshold = -18.0
        proxy_limitations = [
            "ETF turnover is a liquidity proxy and does not replace exchange-published margin balances.",
            "CSI 500, CSI 1000, and ChiNext ETF relatives approximate participation; they are not full advance-decline breadth.",
        ]

    precrash = _state_packet(
        layers=pre_layers,
        confirmed_layer_ids=pre_confirmers,
    )
    if precrash["confirmed"]:
        precrash_state = "risk_confirmation"
        precrash_next = "escalate_human_risk_review"
    elif precrash["observed"]:
        precrash_state = "risk_observation"
        precrash_next = "review_risk_assumptions_without_automatic_action"
    else:
        precrash_state = "no_precrash_signal"
        precrash_next = "no_regime_action"
    precrash["state"] = precrash_state
    precrash["research_next_action"] = precrash_next

    recovery_eligible = recovery_anchor <= drawdown_threshold
    recovery = _state_packet(
        layers=recovery_layers,
        confirmed_layer_ids={"short_trend_reclaim"},
        observation_required_id="rebound_persistence",
    )
    recovery_triggered = set(recovery["triggered_layers"])
    recovery["confirmed"] = (
        recovery["score"] >= 3
        and "rebound_persistence" in recovery_triggered
        and "short_trend_reclaim" in recovery_triggered
        and bool(recovery_triggered & {"participation_repair", "stress_repair"})
    )
    recovery["eligible"] = recovery_eligible
    recovery["eligibility_threshold_pct"] = drawdown_threshold
    recovery["anchor_drawdown_pct"] = recovery_anchor
    recovery["current_drawdown_pct"] = metrics["drawdown_from_252d_high_pct"]
    recovery["failure_flags"] = flags
    if not recovery_eligible:
        recovery_state = "not_in_drawdown"
        recovery_next = "do_not_interpret_normal_strength_as_crash_repair"
    elif flags:
        recovery_state = "repair_failed"
        recovery_next = "invalidate_prior_repair_and_restart_observation"
    elif recovery["confirmed"]:
        recovery_state = "repair_confirmation"
        recovery_next = "falsify_repair_against_new_low_and_stress_relapse"
    elif recovery["observed"]:
        recovery_state = "repair_observation"
        recovery_next = "wait_for_trend_and_participation_confirmation"
    else:
        recovery_state = "unrepaired"
        recovery_next = "wait_for_persistent_rebound"
    recovery["state"] = recovery_state
    recovery["research_next_action"] = recovery_next

    return {
        "ok": True,
        "schema_version": FINANCE_MARKET_REGIME_PACKET_SCHEMA_VERSION,
        "mode": "finance-market-regime",
        "as_of": as_of,
        "market": market,
        "rule_version": expected_rule,
        "metrics": metrics,
        "precrash": precrash,
        "recovery": recovery,
        "source_refs": sources,
        "data_quality": {
            "point_in_time_data": True,
            "lookahead_free": True,
            "proxy_limitations": proxy_limitations,
            "precrash_validation_status": "research_only_failed_recent_out_of_sample",
            "recovery_validation_status": "promising_small_event_sample"
            if market == "us"
            else "insufficient_small_event_sample",
        },
        "boundary": {
            "public_sources_only": True,
            "external_reads_performed": False,
            "external_writes_performed": False,
            "investment_advice": False,
            "position_or_account_accessed": False,
            "trading_allowed": False,
            "automatic_risk_action_allowed": False,
            "human_decision_owner": True,
        },
        "truth_contract": {
            "risk_observation_is_not_crash_prediction": True,
            "risk_confirmation_may_arrive_after_drawdown_begins": True,
            "single_day_rebound_is_not_repair": True,
            "repair_requires_prior_drawdown": True,
            "repair_eligibility_uses_episode_trough_not_current_drawdown": True,
            "market_rules_are_not_interchangeable": True,
            "proxy_limitations_remain_visible": True,
        },
    }


def render_finance_market_regime_markdown(payload: Mapping[str, Any]) -> str:
    precrash = (
        payload.get("precrash") if isinstance(payload.get("precrash"), Mapping) else {}
    )
    recovery = (
        payload.get("recovery") if isinstance(payload.get("recovery"), Mapping) else {}
    )
    lines = [
        "# LoopX Finance Market Regime",
        "",
        f"- market: `{payload.get('market')}`",
        f"- as_of: `{payload.get('as_of')}`",
        f"- rule_version: `{payload.get('rule_version')}`",
        f"- precrash_state: `{precrash.get('state')}`",
        f"- recovery_state: `{recovery.get('state')}`",
        "- investment_advice: `False`",
        "",
        "## Pre-crash evidence",
        "",
    ]
    lines.extend(
        f"- {item}" for item in precrash.get("supporting_evidence") or ["None"]
    )
    lines.extend(["", "## Pre-crash conflicts", ""])
    lines.extend(
        f"- {item}" for item in precrash.get("conflicting_evidence") or ["None"]
    )
    lines.extend(["", "## Recovery", ""])
    lines.append(f"- eligible: `{recovery.get('eligible')}`")
    lines.append(f"- next: `{recovery.get('research_next_action')}`")
    return "\n".join(lines).rstrip() + "\n"
