# Content-Ops Capability

The content-ops capability is the product path for creator/operator workflows:
public handles, private connector gates, source items, angle candidates, draft
states, feedback signals, and publish gates.

Current implementation remains preview-level. It is useful because it gives real
connector and review surfaces a safe packet format before raw material is copied
or published.

The capability also ships a provider-neutral item lifecycle for real local
operations queues. It preserves stable item identity, revision-bound approval,
delivery receipts, exact readback, and supersession without copying draft bodies
or provider credentials into LoopX state. See
[`content_ops_item_v0`](../../../docs/reference/protocols/content-ops-item-lifecycle-v0.md).

`loopx content-ops queue-status` projects caller-owned item files into one
read-only managed queue surface with state counts and a next action. Priority is
the order of the `--item-json` inputs; windows live in item approval and delivery
intent records. See
[`content_ops_queue_projection_v0`](../../../docs/reference/protocols/content-ops-queue-v0.md).

The built-in layout template library moves reusable presentation rules out of
writing skills. `template-list` and `template-show` expose four generic visual
systems; `layout-plan` records typed page roles before
rendering; `layout-check` rejects sparse, overcrowded, overflowing, colliding,
or role-incomplete page sets. See
[`content_ops_layout_plan_v0`](../../../docs/reference/protocols/content-ops-layout-v0.md).

## Implemented Surface

| Layer | Current path |
| --- | --- |
| Capability module | `loopx/capabilities/content_ops/` |
| CLI entry | `loopx content-ops ...` |
| Protocol docs | `docs/reference/protocols/content-ops-surface-v0.md` |
| Queue projection | `docs/reference/protocols/content-ops-queue-v0.md` |
| Layout contract | `docs/reference/protocols/content-ops-layout-v0.md` |
| Smoke | `examples/content-ops-*-smoke.py` |

## Safe Defaults

- Public sources are metadata-first.
- Private connectors enter through owner gates or compact approved counts.
- Raw chats, transcripts, credentials, logs, and local paths are not copied into
  public packets.
- Publishing remains blocked until an explicit user decision.
- Revising approved content invalidates the approval and any delivery intent.
- Provider delivery and readback receipts must match the approved revision and
  digest; the lifecycle helper performs no external write.
- Layout acceptance never implies content approval or publishing authority.
- Built-in cover pages require `0.82–0.94` meaningful vertical density; the
  template field is `density.role_overrides.cover`.
- Built-in `page_sequence` defaults require a cover first, make it the density
  maximum, and require at least `0.72` meaningful density on interior pages;
  the final page keeps its closing/CTA role limits.

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
