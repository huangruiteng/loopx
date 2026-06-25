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

Check connector starter availability:

```bash
loopx value-connectors install-check --format json
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
| `botmail_identity` | host connector profile | install-check only | exact send gate required |
| `community_channel` | host/browser connector profile | install-check and plan | exact account/message gate required |

## Why This Is Not Just A Plan

The `plan` command is the safety layer, but `github-public-probe` is a real
starter connector. It lets a user convert public channel URLs into compact
LoopX metadata and then decide whether to monitor, draft a reply, request
approval, or stop.

Future connectors should follow the same sequence:

```text
install-check -> metadata probe -> value connector plan -> approval gate -> host connector execution
```

LoopX owns the compact control packet and value metric. Host products or user
connectors own account login, private reads, external sends, and production
actions.

## Protocol

See [`value_connector_plan_v0`](../../reference/protocols/value-connector-plan-v0.md).
