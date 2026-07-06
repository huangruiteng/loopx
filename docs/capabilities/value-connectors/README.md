# Value Connectors

Value connectors turn external channels into reusable LoopX control-plane
inputs. The first shipped path focuses on public GitHub metadata because it is
useful immediately, does not require private data, and can be run by users after
installing LoopX locally.

## Quick Start

Install LoopX from the repository checkout:

```bash
python3 -m pip install -e .
```

When you are testing directly from an uninstalled checkout, replace `loopx`
below with `./scripts/loopx` so the command uses the checkout code instead of an
older local release on `PATH`.

Check connector starter availability:

```bash
loopx value-connectors install-check --format json
```

Check the X/browser connector profile:

```bash
loopx value-connectors install-check \
  --connector social_browser_x \
  --format json
```

Probe a public GitHub issue or PR without network access:

```bash
loopx value-connectors github-public-probe \
  --url https://github.com/owner/repo/issues/1 \
  --format json
```

Probe body-free public metadata:

```bash
loopx value-connectors github-public-probe \
  --url https://github.com/owner/repo/issues/1 \
  --fetch-metadata \
  --format json
```

Monitor whether a public maintainer replied after an approved LoopX comment:

```bash
loopx value-connectors github-reply-monitor \
  --issue-url https://github.com/owner/repo/issues/1 \
  --after-comment-url https://github.com/owner/repo/issues/1#issuecomment-123 \
  --fetch-metadata \
  --format json
```

The probe is intentionally metadata-only. It does not read issue bodies,
comment bodies, timelines, raw provider payloads, auth material, or local paths,
and it cannot post comments, send messages, create accounts, or publish.
The reply monitor follows the same boundary: it only captures comment author,
association, timestamp, and URL metadata, then emits either
`prepare_public_triage_note` or `wait_no_bump`.

## Connector Profiles

| Connector | Current state | User can run now | External write behavior |
| --- | --- | --- | --- |
| `github_public_channel` | implemented starter | yes | none |
| `github_public_reply_monitor` | implemented starter | yes | none |
| `social_browser_x` | ego-browser-backed profile | install-check, public-handle packet, and gated plan | exact profile/post/reply gate required |
| `finance_market_snapshot` | probed candidate profile | plan, user prompt surface, and [no-credential probe packet](finance-market-snapshot-probe.md) | account, private portfolio, trading, and paid-data gates required |
| `agent_reach_ops_source_map` | field-derived pattern | [read-only source-map profile](agent-reach-ops-source-map.md) | publish/audit record required for every external write |
| `botmail_identity` | host connector profile | install-check only | exact send gate required |
| `community_channel` | host/browser connector profile | install-check and plan | exact account/message gate required |

## Why This Is Not Just A Plan

The `plan` command is the safety layer, but `github-public-probe` is a real
starter connector. It lets a user convert public channel URLs into compact
LoopX metadata and then decide whether to monitor, draft a reply, request
approval, or stop.

`social_browser_x` is intentionally one step more gated. It depends on
ego-browser for a logged-in browser session, media uploads, profile maintenance,
posting, and reply monitoring, but LoopX still owns the reusable control-plane
packet:

- observe public handles as metadata-only source items;
- plan account/profile work before touching the browser;
- require exact approval for every public post, reply, image, link, and mention;
- record a money, cost, demand, or capability metric plus a kill condition;
- monitor replies as compact signals instead of copying raw timelines.

Example X public-handle packet:

```bash
loopx content-ops observe-public-handle \
  --url https://x.com/loopxops \
  --source-item-id source_x_loopx_public_handle \
  --no-fetch \
  --format json
```

Example gated X publish plan:

```bash
loopx value-connectors plan \
  --connector-id social_browser_x \
  --connector-kind browser_social_channel \
  --channel "X public post via ego-browser" \
  --stage external_write_request \
  --target-ref "one approved LoopX post" \
  --target-url https://x.com/loopxops \
  --external-write-requested \
  --money-metric "qualified workflow owner asks for LoopX setup help" \
  --success-metric "one audit, demo, or setup request" \
  --kill-condition "spam hiding, account-health degradation, or no workflow owner signal" \
  --format json
```

Future connectors should follow the same sequence:

```text
install-check -> metadata probe -> value connector plan -> approval gate -> host connector execution
```

LoopX owns the compact control packet and value metric. Host products or user
connectors own account login, private reads, external sends, and production
actions.

## Agent-Reach Ops Source Map

`agent_reach_ops_source_map` is a reusable field pattern for connector-backed
content operations. Agent-Reach is used as a source router: first run
`agent-reach doctor --json`, then collect read-only signals from available
routes such as GitHub, public web/RSS, V2EX, or Bilibili. LoopX stores compact
evidence cards, maturity scores, the ops brief, draft packet, publish/audit
record, and monitor state.

This profile is intentionally source-first and action-gated. Broad posting
discretion does not remove the need to record exact body, channel/account,
time, source refs, and stop conditions. See the
[Agent-Reach ops source-map profile](agent-reach-ops-source-map.md).

## Finance Market Snapshot Profile

`finance_market_snapshot` is a planned value connector profile for users who
want an agent to pull market facts before analysis. It is useful when the user
asks for a bounded snapshot such as:

- 股票或 ETF 行情: 最新价、涨跌幅、成交额、市值、估值区间、更新时间;
- 基金信息: 净值、费率、持仓摘要、同类排名、公告更新时间;
- 新闻和公告: 公司公告、业绩预告、监管披露、重要新闻摘要;
- 组合观察: 用户给出的公开标的清单的异动、风险提示、待复核项。

Suggested source order:

1. Futu OpenD or another user-owned market terminal when the user already has a
   local daemon, account permission, and data entitlement.
2. Eastmoney or other public finance pages/APIs for public quote, fund,
   announcement, and news metadata.
3. GitHub-hosted open-source finance API wrappers or public datasets only as a
   fallback after freshness, terms, and data-origin checks.

The profile should label every answer with freshness and confidence: `live`,
`delayed`, `cached`, `source_unverified`, or `manual_review_required`. It should
also say when a field is missing instead of filling it from a stale fallback.

Safe user prompts:

```text
/loopx 拉取 AAPL、MSFT、NVDA 今日行情和近 7 天关键新闻，标出更新时间和数据源；不要给投资建议。
/loopx 对 5 只沪深 ETF 做一个公开信息快照：净值、规模、费率、公告、异动；缺失字段列出来。
/loopx 监控我给出的股票清单是否出现公告或大幅波动，只写 compact todo，不自动交易。
```

Boundaries:

- no trading, order placement, portfolio mutation, paid-data signup, account
  login, captcha handling, or private portfolio read without an exact user gate;
- no investment advice, suitability claim, price target, or guaranteed-return
  wording;
- no hidden source mixing: every metric must carry source, timestamp, and
  uncertainty label;
- no raw credential, account id, private holding, or paid provider payload in
  LoopX state.

Example plan-only packet:

```bash
loopx value-connectors plan \
  --connector-id finance_market_snapshot \
  --connector-kind custom_connector \
  --channel "public finance metadata snapshot" \
  --stage observe \
  --target-ref "AAPL/MSFT/NVDA quote and news snapshot" \
  --target-url https://www.eastmoney.com \
  --external-read \
  --value-axis capability \
  --money-metric "reduce analyst time spent collecting public market facts" \
  --success-metric "fresh quote/news table with source, timestamp, and uncertainty labels" \
  --kill-condition "source terms, freshness, or symbol mapping cannot be verified" \
  --format json
```

See the [no-credential probe packet](finance-market-snapshot-probe.md) for the
current source findings. The short version: Eastmoney public quote metadata is
reachable as a `source_unverified` canary, GitHub OSS wrappers are fallback
candidates that still need source-origin checks, and Futu/OpenD is gated until
the user provides a local daemon, account permission, API agreements, and quote
rights.

## Protocol

See [`value_connector_plan_v0`](../../reference/protocols/value-connector-plan-v0.md).
