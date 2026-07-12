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
filter before persistence and write one compact event per Lark
`event_id`/`message_id`. The agent does not need to keep a websocket open.

Use `addressed_only` only when direct bot mentions are the entire feedback
contract. Lark's real-time `im.message.receive_v1` projection does not expose a
thread id, so it cannot recognize later replies in a bot-started thread. A
review or collaboration inbox that must learn from the whole discussion should
use `configured_chat_all`: the host collector filters by its local-private chat
id, persists every message from that chat, and lets the domain binding group or
ignore messages during durable writeback.

## Local-private configuration

The inbox is opt-in. Create a local-private generic Lark inbox config:

```json
{
  "schema_version": "lark_event_inbox_config_v0",
  "enabled": true,
  "inbox_dir": ".loopx/inbox/team-feedback",
  "capture_scope": "configured_chat_all"
}
```

`inbox_dir` must stay under `.loopx/inbox`. Destination ids, member ids,
profile names, raw provider payloads, and credentials stay in local-private
configuration or host state and must not enter public LoopX packets.

`capture_scope` defaults to `addressed_only` for compatibility. Drain output
reports `thread_complete=false` and a coverage warning for that mode. For
`configured_chat_all`, the collector's jq filter should select the configured
chat only; do not add a content-level `@bot` predicate.

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

## Bounded history reconciliation

Real-time event subscriptions do not backfill messages sent before a collector
started, and an earlier `addressed_only` collector will already have omitted
unaddressed replies. Fetch the bounded source conversation with the Lark CLI,
project each message into `lark_event_inbox_event_v0`, then pipe the JSON array
or NDJSON into the generic importer:

```bash
<bounded-lark-message-export> \
  | loopx lark-inbox ingest \
      --project . \
      --config .loopx/config/lark/event-inbox.json \
      --execute
```

Ingest validates ids and schema, deduplicates by `message_id`, writes only to
the configured local-private inbox, and returns counts rather than message
content. It does not acknowledge imported messages; the domain agent must still
write each actionable effect before ACK.

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
