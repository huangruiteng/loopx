# value_connector_plan_v0

Status: public-safe connector planning and starter runtime contract v0.

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

## User Value

This capability is valuable only when the connector output can produce one of:

- revenue or paid conversion evidence;
- measurable cost-reduction evidence;
- a qualified workflow owner, demo request, or demand signal;
- reusable connector capability that clearly enables the first three.

Connector volume by itself is not value.
