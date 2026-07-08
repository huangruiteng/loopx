# Finance Market Snapshot Probe Packet

Status: public-safe no-credential probe packet for `finance_market_snapshot`.

This packet records what LoopX can safely learn before building a live finance
connector. It is not a trading adapter, not an account adapter, and not an
investment-advice surface.

## Scope

Allowed in this probe:

- public, no-credential network reads;
- source and endpoint metadata;
- compact field-shape observations;
- source freshness, terms, and uncertainty labels;
- user gates for account, paid-data, private portfolio, or trading surfaces.

Forbidden in this probe:

- account login, Futu OpenD connection, private portfolio reads, account ids,
  paid-data signup, captcha handling, credentials, or cookies;
- trading, order placement, portfolio mutation, or production actions;
- price targets, suitability claims, guaranteed-return wording, or personal
  investment advice;
- raw provider payloads or raw paid-provider responses in LoopX state.

## Source Findings

| Source | Probe result | Candidate use | Gate |
| --- | --- | --- | --- |
| Futu OpenAPI / OpenD | Official docs describe OpenD as the gateway program and require local/cloud OpenD setup before API use. Official quota docs also describe quote-right permissions and market-specific data rights. | High-quality user-owned terminal path when the user already has OpenD, API agreements, account permission, and quote rights. | Exact user gate before any connection, login, quote subscription, account metadata, portfolio, or trade API call. |
| Eastmoney public quote endpoint | No-credential probe reached `https://push2.eastmoney.com/api/qt/stock/get` for two A-share examples and observed compact JSON with a `data` object plus allowlist-shaped quote fields. | First public metadata canary for A-share quote snapshots. | Treat as `source_unverified` until source terms, stability, throttling, symbol mapping, and freshness semantics are reviewed. |
| Eastmoney quote page | No-credential probe reached `https://quote.eastmoney.com/sh600519.html` as public HTML. | Human-visible source URL and fallback inspection label. | Do not scrape hidden page state into LoopX; prefer compact endpoint field allowlists. |
| AKShare | Public GitHub repo describes a broad Python financial data interface and explicitly warns that data is for academic/reference use and not investment advice. | GitHub OSS fallback for China-market quote, fund, news, and announcement connectors. | Preserve upstream data-risk and non-advice warnings; check source-origin and interface freshness per function. |
| efinance | PyPI describes an Eastmoney-based open-source Python library for stock, fund, and futures data, with MIT metadata. | Lightweight Eastmoney-backed fallback candidate for China-market snapshots. | Same Eastmoney source-origin, freshness, and terms gate applies. |
| yfinance | Public GitHub repo describes a Yahoo Finance API wrapper and says it is unaffiliated with Yahoo, for research/educational or personal-use contexts subject to Yahoo terms. | US-stock/ETF fallback candidate for non-China symbols. | Terms/use-right review required before automated or repeated use. |
| py-futu-api | Public GitHub repo is the Futu OpenAPI Python SDK. | SDK layer after the Futu user gate, not a no-credential fallback. | Requires OpenD/account/quote-right gate first. |

## Candidate Packet Shape

```json
{
  "schema_version": "finance_market_snapshot_probe_packet_v0",
  "connector_id": "finance_market_snapshot",
  "external_reads_performed": true,
  "external_writes_performed": false,
  "account_signup_performed": false,
  "private_source_content_read": false,
  "raw_provider_payload_recorded": false,
  "non_investment_advice": true,
  "sources": [
    {
      "source_id": "eastmoney_public_quote",
      "access_mode": "public_metadata_only",
      "probe_status": "reachable",
      "freshness_label": "source_unverified",
      "observed_shape": ["symbol", "name", "quote_fields", "provider_timestamp"],
      "missing_or_unverified": ["terms", "throttling", "official_field_map"]
    },
    {
      "source_id": "futu_opend",
      "access_mode": "user_owned_terminal_required",
      "probe_status": "gated",
      "freshness_label": "manual_review_required",
      "missing_or_unverified": ["OpenD state", "API agreement", "quote rights"]
    },
    {
      "source_id": "github_oss_fallbacks",
      "access_mode": "public_metadata_only",
      "probe_status": "candidate",
      "freshness_label": "manual_review_required",
      "missing_or_unverified": ["source terms", "function-level origin", "maintenance health"]
    }
  ]
}
```

## Recommended Next Slice

The first dry-run-only `finance_market_snapshot` canary is:

```bash
loopx value-connectors finance-market-snapshot --symbol sh600519 --format json
```

It runs before any live adapter:

1. accept a tiny symbol allowlist such as `sh600519` and `sz000001`;
2. call only the public Eastmoney quote endpoint with explicit timeout and user
   agent;
3. emit only compact allowlisted fields and field-presence metadata, not raw
   provider payloads;
4. label every result `source_unverified` until terms/freshness are reviewed;
5. fail closed to a user gate for Futu/OpenD, private portfolio, paid data,
   trading, captcha, or credential paths.

The emitted `finance_market_snapshot_canary_packet_v0` keeps
`human_decision_owner=true` and marks thesis impact as
`manual_review_required`. This follows the research-loop lesson that finance
connectors should help a person review evidence and update judgment, not
delegate investment decisions to the agent.

## Sources

- [Futu API introduction](https://openapi.futunn.com/futu-api-doc/en/intro/intro.html)
- [Moomoo/Futu authorities and quota](https://openapi.moomoo.com/moomoo-api-doc/en/intro/authority.html)
- [AKShare GitHub repository](https://github.com/akfamily/akshare)
- [efinance PyPI package](https://pypi.org/project/efinance/)
- [yfinance GitHub repository](https://github.com/ranaroussi/yfinance)
- [Futu OpenAPI Python SDK](https://github.com/FutunnOpen/py-futu-api)
