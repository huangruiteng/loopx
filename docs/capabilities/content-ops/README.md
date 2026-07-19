# Content-Ops Capability

The content-ops capability is the product path for creator/operator workflows:
public handles, private connector gates, source items, angle candidates, draft
states, feedback signals, and publish gates.

Current implementation remains preview-level. It is useful because it gives real
connector and review surfaces a safe packet format before raw material is copied
or published.

## Implemented Surface

| Layer | Current path |
| --- | --- |
| Capability module | `loopx/capabilities/content_ops/` |
| CLI entry | `loopx content-ops ...` |
| Protocol docs | `docs/reference/protocols/content-ops-surface-v0.md` |
| Smoke | `examples/content-ops-*-smoke.py` |

## Safe Defaults

- Public sources are metadata-first.
- Private connectors enter through owner gates or compact approved counts.
- Raw chats, transcripts, credentials, logs, and local paths are not copied into
  public packets.
- Publishing remains blocked until an explicit user decision.

## Connector-First Ops Pattern

For social and creator operations, start with a connector source map instead of
drafting from memory:

```bash
loopx value-connectors source-map --format json
```

This packet gives a newly connected agent the current read-first connector
catalog, including public GitHub metadata, content-ops public handles,
browser-backed X research, Agent-Reach source routing, and finance snapshot
probes:

```text
doctor -> read-only source map -> maturity score -> ops brief -> draft packet
       -> publish/audit record -> compact monitor
```

The pattern lets a newly connected LoopX agent reuse external signals without
turning LoopX into a raw platform archive or untracked publisher. Even when an
owner grants broad posting discretion, the agent should still record the exact
body, account/channel, source map, timing, and stop condition before an external
post.

## Social Browser Provider

`content-ops` owns the built-in `social_browser_x` provider because public
social observation, source promotion, draft preparation, and publish gates are
content outcomes. The provider supplies one shared source profile, install
check, and metadata-only connector trial. The `value-connectors` CLI remains a
compatibility facade and delegates those packets without changing their output.

The provider does not open a browser, read a timeline, or publish. A real
browser session remains owner-controlled, and every external write still needs
the exact account, body, media/link plan, source references, and stop condition.
