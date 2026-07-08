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

Give a newly connected agent the read-first connector source map:

```bash
loopx value-connectors source-map --format json
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
| `finance_market_snapshot` | value-discovery profile | research packet shape, plan, user prompt surface, and [no-credential probe packet](finance-market-snapshot-probe.md) | account, private portfolio, trading, and paid-data gates required |
| `agent_reach_ops_source_map` | field-derived source profile | `loopx value-connectors source-map --connector agent_reach_ops_source_map --format json`; [profile note](agent-reach-ops-source-map.md) | publish/audit record required for every external write |
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

`loopx value-connectors source-map --format json` gives a newly connected agent
the current read-first connector catalog without requiring it to read internal
docs. It includes implemented or field-proven source profiles such as public
GitHub metadata probes, GitHub reply monitors, content-ops public handles,
browser-backed X research, Agent-Reach source routing, and the finance market
snapshot probe profile. It also names action-gated profiles such as botmail and
community replies so agents do not treat "can send" as "can freely read/write".

`agent_reach_ops_source_map` is one profile in that packet. Agent-Reach is used
as a source router: first run `agent-reach doctor --json`, then collect
read-only signals from available routes such as GitHub, public web/RSS, V2EX,
or Bilibili. LoopX stores compact evidence cards, maturity scores, the ops
brief, draft packet, publish/audit record, and monitor state.

This profile is intentionally source-first and action-gated. Broad posting
discretion does not remove the need to record exact body, channel/account,
time, source refs, and stop conditions. See the
[Agent-Reach ops source-map profile](agent-reach-ops-source-map.md).

## Finance Value Discovery Profile

`finance_market_snapshot` is a planned value connector profile for finance
value discovery, not for market-timing, price action, or trade automation. Its
job is to help a person turn a broad investment idea into a falsifiable research
packet before any decision is made.

The purpose is judgment building. Retail users usually cannot win by having
faster information access than professional investors, so the connector should
help a person repeatedly practice the same domain loop: state a thesis, inspect
business-value evidence, confront disconfirming facts, update the thesis, and
record what changed in their judgment.

The profile is useful when the user asks for:

- a next-industry-chain discovery pass before company-level work;
- a company value-discovery thesis from public business facts;
- an industry-chain catalyst map and where the company sits in that chain;
- a market-mispricing hypothesis that explains what the market may be missing;
- supporting evidence, disconfirming evidence, missing evidence, and a
  verification window;
- a compact research packet that helps a human update judgment without
  delegating the decision to the agent.

The core packet shape is `finance_value_discovery_research_packet_v0`:

```json
{
  "schema_version": "finance_value_discovery_research_packet_v0",
  "connector_id": "finance_market_snapshot",
  "human_decision_owner": true,
  "investment_advice": false,
  "autotrade_allowed": false,
  "judgment_loop": "thesis -> evidence -> disconfirmation -> thesis update",
  "thesis": "<human-provided or agent-drafted value-discovery thesis>",
  "value_drivers": ["business quality", "reinvestment runway", "margin durability"],
  "industry_chain_position": "<where the company captures value in the chain>",
  "catalysts": ["industry demand change", "product cycle", "regulatory or supply shift"],
  "mispricing_hypothesis": "<why the market might be underestimating the value driver>",
  "evidence_for": ["source-labeled public evidence supporting the thesis"],
  "disconfirming_evidence": ["source-labeled public evidence challenging the thesis"],
  "missing_evidence": ["facts required before stronger conviction"],
  "verification_window": "<events or reports that should update the thesis>",
  "source_freshness": "manual_review_required"
}
```

The upstream industry catalyst discovery packet is
`finance_industry_catalyst_discovery_packet_v0`:

```json
{
  "schema_version": "finance_industry_catalyst_discovery_packet_v0",
  "connector_id": "finance_market_snapshot",
  "research_stage": "industry_chain_discovery",
  "trading_stage_out_of_scope": true,
  "human_decision_owner": true,
  "judgment_loop": "discover chain -> map bottlenecks -> test catalysts -> shortlist companies -> retrospective validation",
  "candidate_industry_chains": ["AI data center power and liquid cooling"],
  "selection_reason": "public evidence suggests AI infrastructure deployment is constrained by power and cooling bottlenecks",
  "bottleneck_map": ["rack power density", "thermal management", "grid connection", "deployment lead time"],
  "catalyst_timeline": ["GPU rack roadmap", "hyperscaler capex", "liquid-cooling adoption", "power architecture standardization"],
  "company_mapping_required": true,
  "candidate_pool_rules": ["research pool first", "trade pool only after separate trading-stage review"],
  "retrospective_validation": {
    "benchmark_chains": ["AI storage", "AI PCB"],
    "pre_catalyst_cutoff": "date before the public price move",
    "question": "Would this process have surfaced the chain before the breakout using only then-available public evidence?"
  }
}
```

Source connectors remain supporting tools. Public filings, company reports,
industry research excerpts, announcements, news, and public datasets can feed
the packet when their source, timestamp, and uncertainty are visible. Market
quotes, volume, and short-term moves are out of scope for this value-discovery
profile.

Safe user prompts:

```text
/loopx 基于公开资料为腾讯做一个价值发现 packet：业务质量、产业链位置、潜在误定价、反证和验证窗口；不要给投资建议。
/loopx 把“AI 云需求可能重估阿里长期价值”拆成 thesis、value drivers、evidence_for、disconfirming_evidence 和 missing_evidence。
/loopx 对一个行业链条做价值发现：谁捕获价值、哪些催化改变利润池、哪些事实能推翻这个 thesis。
/loopx 用研究阶段方法找下一条类似存储、PCB 的产业链机会，并用爆发前公开资料回测这套方法是否能提前发现。
```

Boundaries:

- no trading, order placement, portfolio mutation, paid-data signup, account
  login, captcha handling, or private portfolio read without an exact user gate;
- no investment advice, suitability claim, price target, or guaranteed-return
  wording;
- no hidden source mixing: every metric must carry source, timestamp, and
  uncertainty label;
- no price-action thesis: do not turn short-term quote changes, volume, or
  momentum into the value-discovery argument;
- no raw credential, account id, private holding, or paid provider payload in
  LoopX state.

Example plan-only packet:

```bash
loopx value-connectors plan \
  --connector-id finance_market_snapshot \
  --connector-kind custom_connector \
  --channel "public finance value discovery" \
  --stage observe \
  --target-ref "Tencent value-discovery thesis review" \
  --target-url https://www.tencent.com/en-us/investors.html \
  --external-read \
  --value-axis capability \
  --money-metric "reduce human time spent turning public company facts into a falsifiable thesis" \
  --success-metric "research packet with value drivers, catalyst chain, disconfirming evidence, missing evidence, and verification window" \
  --kill-condition "the thesis depends on price action, private data, paid-source claims, or unverified evidence" \
  --format json
```

See the [no-credential probe packet](finance-market-snapshot-probe.md) for the
current source findings. The short version: public quote/source probes are only
source-readiness evidence. The finance profile should promote a source into the
value-discovery packet only when it helps explain or challenge business value,
industry-chain position, catalysts, or missing evidence.

## Protocol

See [`value_connector_plan_v0`](../../reference/protocols/value-connector-plan-v0.md).
