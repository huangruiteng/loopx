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
