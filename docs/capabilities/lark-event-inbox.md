# Lark event inbox

LoopX can consume Lark feedback without keeping an agent process alive. The
integration deliberately separates collection from interpretation:

```text
Lark event stream
  -> host-managed collector
  -> .loopx/inbox/<channel>/*.json
  -> loopx lark-inbox drain
  -> domain agent writes a todo, vision correction, artifact update, or rationale
  -> loopx lark-inbox ack --message-id ... --execute
```

The collector is host infrastructure. On macOS it may be supervised by
`launchd`; other hosts may use systemd or another restart policy. It should
filter before persistence, keep only messages explicitly addressed to the
configured bot, and write one compact event per Lark `event_id`/`message_id`.
The agent does not need to keep a websocket open.

## Local-private configuration

The inbox is opt-in. Create a local-private generic Lark inbox config:

```json
{
  "schema_version": "lark_event_inbox_config_v0",
  "enabled": true,
  "inbox_dir": ".loopx/inbox/team-feedback"
}
```

`inbox_dir` must stay under `.loopx/inbox`. Destination ids, member ids,
profile names, raw provider payloads, and credentials stay in local-private
configuration or host state and must not enter public LoopX packets.

## Drain and acknowledge

```bash
loopx lark-inbox drain \
  --project . \
  --config .loopx/config/lark/event-inbox.json

loopx lark-inbox ack \
  --project . \
  --config .loopx/config/lark/event-inbox.json \
  --message-id om_xxx \
  --execute
```

Drain is read-only and returns bounded local-private message content. A message
must be acknowledged only after its effect is written back. Duplicate event
files collapse by `message_id`; repeated acknowledgement is idempotent.

## Domain bindings

The inbox itself does not know why a message matters. A domain capability binds
the generic event stream to its own interpretation and writeback rules. For
example, issue-fix can turn reviewer-group messages into PR-description
updates, Kanban context, vision corrections, or explicit no-follow-up
rationale. Other domains can consume the same inbox without adopting any
issue-fix schema or lifecycle.

For issue-fix, outbound GitHub reviewer requests and outbound Lark
notifications remain independent obligations. The Lark inbox is only the
inbound feedback path.
