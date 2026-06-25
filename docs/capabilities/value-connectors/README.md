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

The probe is intentionally metadata-only. It does not read issue bodies,
comment bodies, timelines, raw provider payloads, auth material, or local paths,
and it cannot post comments, send messages, create accounts, or publish.

## Connector Profiles

| Connector | Current state | User can run now | External write behavior |
| --- | --- | --- | --- |
| `github_public_channel` | implemented starter | yes | none |
| `social_browser_x` | ego-browser-backed profile | install-check, public-handle packet, and gated plan | exact profile/post/reply gate required |
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

## Protocol

See [`value_connector_plan_v0`](../../reference/protocols/value-connector-plan-v0.md).
