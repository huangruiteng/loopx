# value_connector_plan_v0

Status: public-safe connector planning and starter runtime contract v0.

`loopx value-connectors` is a compatibility CLI and protocol facade. Generic
planning and the stable command surface remain here. Public GitHub probes are
owned by `issue-fix`; the `social_browser_x` source, install, and connector-trial
contracts are owned by `content-ops`. Existing callers still invoke the commands
below while the facade delegates to those providers.

`value_connector_plan_v0` is a compact contract for external-value connector
calls. It sits before real connector execution so LoopX can separate useful
business-development work from unsafe automation.

The v0 goal is practical:

- show how to install and run connector starters;
- allow bounded public metadata reads;
- keep account setup, external posting, email sends, paid services, private
  reads, auth material, and production actions behind explicit gates;
- require every connector call to name a money, cost, demand, or capability
  metric plus a kill condition.

## CLI

Check installed starter dependencies:

```bash
loopx value-connectors install-check --format json
```

Run the first shipped connector starter without a network read:

```bash
loopx value-connectors github-public-probe \
  --url https://github.com/owner/repo/issues/1 \
  --format json
```

Run the same connector with a bounded public metadata read:

```bash
loopx value-connectors github-public-probe \
  --url https://github.com/owner/repo/issues/1 \
  --fetch-metadata \
  --format json
```

Detect public maintainer interest after an approved LoopX comment without
reading comment bodies or bumping the thread:

```bash
loopx value-connectors github-reply-monitor \
  --issue-url https://github.com/owner/repo/issues/1 \
  --after-comment-url https://github.com/owner/repo/issues/1#issuecomment-123 \
  --fetch-metadata \
  --format json
```

Plan a gated external write or account setup before any connector performs it:

```bash
loopx value-connectors plan \
  --connector-id community_channel \
  --connector-kind community_channel \
  --channel "public community thread" \
  --stage external_write_request \
  --target-ref "thread asking about agent workflow operations" \
  --external-write-requested \
  --money-metric "qualified workflow owner asks for a LoopX audit" \
  --success-metric "one audit or demo request" \
  --kill-condition "channel rules reject the reply or no workflow owner appears" \
  --format json
```

## Records

| Record | Purpose |
| --- | --- |
| `value_connector_plan_v0` | Plan-level objective, brand boundary, connector calls, approval gates, and truth contract. |
| `connector_call_intent_v0` | One planned connector call with channel, stage, access mode, value axis, metric, success metric, and kill condition. |
| `connector_approval_gate_v0` | Exact-call approval gate for account setup, external writes, sends, publishing, or private expansion. |
| `github_public_channel_probe_packet_v0` | Starter connector output for public GitHub issue/PR/discussion metadata. |
| `github_public_reply_monitor_packet_v0` | Starter connector output for public maintainer reply detection after a LoopX comment. |
| `content_ops_social_browser_x_provider_v0` | Content-ops-owned source, install, and metadata-only trial contract behind the compatibility facade. |
| `finance_market_snapshot_profile_v0` | Candidate profile for quote/fund/news/announcement pulls with source, freshness, uncertainty, and no-investment-advice gates. |
| `finance_market_snapshot_probe_packet_v0` | No-credential public-source probe packet for Eastmoney/Futu/GitHub OSS source readiness, gates, and fallback decisions. |
| `value_connector_install_check_packet_v0` | Local install/use checklist for connector starters. |

## Boundaries

The contract is valid only when:

- external writes are never allowed directly from a plan or probe;
- every account setup or external write request has an approval gate;
- money/cost/demand/capability metric and kill condition are present;
- raw bodies, comment bodies, timelines, private source content, auth material,
  local paths, and raw provider payloads are absent;
- `truth_contract.plan_only=true` for plans;
- starter probes report whether a bounded external read happened.

## Starter Connector

`github_public_channel` is the first implemented starter. It accepts public
GitHub issue, PR, and discussion URLs. Query strings, fragments, auth material,
non-`github.com` hosts, and non-HTTPS URLs are rejected.

For issue and PR URLs, `--fetch-metadata` uses GitHub REST and copies only
allowlisted metadata such as title, state, labels, comment count, timestamps,
author association, and URL. It does not copy issue body, comment bodies,
timeline events, raw provider payloads, auth material, or local paths.

For discussion URLs, `--fetch-metadata` uses GitHub CLI GraphQL when `gh` is
installed and authenticated. Without `gh`, users can still run no-fetch mode or
use `install-check` to see the missing dependency.

`github_public_reply_monitor` accepts a public issue or PR URL and an anchor
issue-comment URL. Its live mode uses GitHub CLI REST metadata and captures only
comment author, author association, timestamps, and URL. It detects whether a
public maintainer/member/collaborator replied after the LoopX comment and
returns `prepare_public_triage_note`; otherwise it returns `wait_no_bump`.

## Finance Market Snapshot Profile

`finance_market_snapshot` is a planned finance profile for bounded market-fact
pulls. The v0 surface is a plan and gate contract, not a live trading adapter
and not an investment-advice engine.

Supported pull intents:

- quote snapshots for stocks, ETFs, and indexes;
- fund snapshots such as NAV, fee, size, holding summary, and announcement
  timestamp;
- public news, company announcement, earnings, and regulatory-disclosure
  snapshots;
- compact watch todos for a user-provided public symbol list.

Preferred source order:

1. a user-owned terminal or daemon such as Futu OpenD when account permission,
   local daemon state, and data entitlement are already available;
2. public finance metadata pages/APIs such as Eastmoney for quote, fund, news,
   and announcement facts;
3. GitHub-hosted open-source wrappers or public datasets as fallback only after
   terms, freshness, and source-origin checks.

Every finance packet should project:

- source id and source URL or provider label;
- `observed_at` or provider timestamp;
- freshness label: `live`, `delayed`, `cached`, `source_unverified`, or
  `manual_review_required`;
- missing-field list instead of silent fallback filling;
- non-investment-advice disclaimer.

Forbidden before an exact approval gate:

- login, private portfolio reads, account identifiers, paid-data signup,
  captcha handling, or credential collection;
- trading, order placement, portfolio mutation, or production actions;
- price targets, suitability claims, guaranteed-return language, or personal
  investment advice;
- raw paid-provider payloads or private account material in LoopX state.

## Browser Social Connector Profile

`social_browser_x` is the first browser-backed value connector profile. It is
not a headless X API client and it does not grant LoopX permission to post. It
documents how a user's agent can use an ego-browser session for public-safe X
work while LoopX keeps the control-plane state.

Allowed before an exact approval gate:

- `install-check` reporting whether `ego-browser` is available;
- metadata-only public-handle packets through `loopx content-ops
  observe-public-handle`;
- no-send research notes, target-specific draft packets, image/body/link/mention
  review packets, and reply-monitor plans;
- value metrics and kill conditions for the planned post, reply, or monitor.

Forbidden before an exact approval gate:

- account creation, profile edits, posting, replies, reposts, follows used as
  growth automation, deletion, appeals, or paid actions;
- captcha bypass, credential collection, cookie export, raw timeline capture,
  private DMs, or non-public material;
- public claims outside the declared LoopX brand boundary.

The connector exists because browser channels often have the highest business
value but the highest account-health and public/private-boundary risk. A useful
LoopX packet should let a user hand their own agent the process without handing
over judgment:

```text
install-check -> public metadata packet -> no-send draft packet -> exact approval gate -> ego-browser execution -> compact reply/value monitor
```

## User Value

This capability is valuable only when the connector output can produce one of:

- revenue or paid conversion evidence;
- measurable cost-reduction evidence;
- a qualified workflow owner, demo request, or demand signal;
- reusable connector capability that clearly enables the first three.

Connector volume by itself is not value.
