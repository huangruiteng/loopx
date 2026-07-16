# Lark event inbox

LoopX can consume Lark feedback without keeping an agent process alive. The
integration deliberately separates collection from interpretation:

```text
Lark event stream
  -> host-managed collector
  -> .loopx/inbox/<channel>/*.json
  -> loopx lark-inbox drain
  -> domain agent writes a todo, vision correction, artifact update, or rationale
  -> direct bot question: loopx lark-inbox reply (optional, configured sender only)
  -> loopx lark-inbox ack --message-id ... --execute
```

The collector is host infrastructure. LoopX can validate a local-private
collector config, preview or explicitly install a macOS `launchd` / Linux
`systemd` user service, and report supervisor plus event-bus health. The
installed service runs `lark-cli --profile <configured-profile> event consume`
directly with a bounded timeout,
so stdin EOF under a supervisor cannot terminate an otherwise unbounded
consumer. When the official npm package exposes a Node wrapper, LoopX records
absolute paths for both Node and the wrapper so launchd does not depend on an
interactive-shell PATH. It filters before persistence and writes one compact event per Lark
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

Optional source-thread replies are a separate, default-off boundary. Enable
them only for a `configured_chat_all` inbox and bind an explicit non-default
bot profile to the same local-private chat:

```json
{
  "schema_version": "lark_event_inbox_config_v0",
  "enabled": true,
  "inbox_dir": ".loopx/inbox/team-feedback",
  "capture_scope": "configured_chat_all",
  "reply": {
    "enabled": true,
    "sender_profile": "project-review-bot",
    "sender_identity": "bot",
    "bot_display_name": "Project Review Bot",
    "chat_id": "oc_<local-private-chat-id>"
  }
}
```

The reply path never uses the machine default profile. Before any send it
verifies that the named profile resolves to the expected bot and that the bot
can read the configured chat. A profile/app mismatch fails with
`lark_inbox_reply_sender_identity_mismatch`; a profile that cannot access the
configured chat fails with
`lark_inbox_reply_sender_not_in_configured_chat`. Neither failure falls back
to another app. Public results contain only compact status/receipt fields, not
the profile, chat id, message id, reply text, or provider payload.

## Host collector lifecycle

Keep the collector config ignored and untracked. It references the generic
inbox config but owns host-only details such as the chat id and supervisor:

```json
{
  "schema_version": "lark_event_collector_config_v0",
  "enabled": true,
  "service_name": "loopx-lark-feedback",
  "event_key": "im.message.receive_v1",
  "identity": "bot",
  "profile": "project-review-bot",
  "supervisor": "launchd",
  "chat_id": "oc_<local-private-chat-id>",
  "consume_timeout": "30m",
  "lark_cli_bin": "lark-cli",
  "event_inbox_config": ".loopx/config/lark/event-inbox.json"
}
```

The packaged v0 lifecycle accepts only `im.message.receive_v1`, bot identity,
an isolated `loopx-` service name, and `configured_chat_all`. These constraints
match the canonical inbox schema, avoid collisions with unrelated user services,
and make thread completeness explicit instead of pretending that an
`addressed_only` consumer sees later unaddressed replies. Plan and install
output never returns the chat id, local paths, generated jq, or credentials.

An enabled collector must bind an explicit non-default Lark CLI profile. When
`profile` is omitted, LoopX may reuse the enabled inbox reply
`sender_profile`; when both are present they must match. The generated service
places `--profile` before `event consume`, so collection and optional replies
cannot silently use different app identities. Public plan/status packets expose
only whether a profile is bound and where the binding came from, never its
value.

```bash
loopx lark-inbox collector-plan \
  --project . \
  --config .loopx/config/lark/collector.json

# Preview first; this writes nothing and starts no process.
loopx lark-inbox collector-install \
  --project . \
  --config .loopx/config/lark/collector.json

# Explicitly write the user service and start/restart it.
loopx lark-inbox collector-install \
  --project . \
  --config .loopx/config/lark/collector.json \
  --execute

# Read-only supervisor, event-bus, and real-event evidence check.
loopx lark-inbox collector-status \
  --project . \
  --config .loopx/config/lark/collector.json \
  --probe-event-bus
```

Missing `lark-cli` produces a non-blocking install hint. Missing scopes or bot
configuration still belong to `lark-cli`; LoopX does not authenticate a bot,
copy app credentials, or silently install packages. Service installation is a
local host write and therefore requires explicit `--execute`. Status separates
`healthy` from `real_event_evidence_present`: a running subscriber can be
healthy before the first message, while acceptance of a real integration still
requires one post-install event to appear in the inbox.

Register the generic inbox pointer once at the goal boundary:

```bash
loopx configure-goal \
  --goal-id <goal-id> \
  --lark-event-inbox-config .loopx/config/lark/event-inbox.json

# Review the preview, then apply explicitly.
loopx configure-goal \
  --goal-id <goal-id> \
  --lark-event-inbox-config .loopx/config/lark/event-inbox.json \
  --execute
```

The configuration catalog exposes this optional capability on demand. Quota
projects `enabled`, `config_pointer_registered`, a public-safe command, and a
content-free urgency summary; it never projects the private path, message ids,
senders, or message bodies. The summary includes pending/direct-question/direct-
mention counts and the oldest pending age. A configured direct reply becomes a
high-priority `lark_event_inbox` work lane before ordinary monitor or advancement
work. Generated heartbeat bodies run the actual goal-boundary `drain_command`;
`loopx lark-inbox drain --goal-id <goal-id> --project .`
resolves the ignored config from the goal registry. A disabled or empty inbox
is a quiet zero-spend path, so projects without Lark keep the default behavior.

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

Urgency classification stays local: explicit configured bot-name/LoopX mentions
and bounded question signals produce counts only. The agent still drains and
interprets the source event before deciding the durable effect or reply; the
summary is a scheduling signal, not semantic authority.

For a direct question or explicit bot mention, write the requested durable
effect first, preview one concise source-thread reply, execute it, require
readback, and only then ACK:

```bash
loopx lark-inbox reply \
  --project . \
  --config .loopx/config/lark/event-inbox.json \
  --message-id om_xxx \
  --text '已记录并修正。'

loopx lark-inbox reply \
  --project . \
  --config .loopx/config/lark/event-inbox.json \
  --message-id om_xxx \
  --text '已记录并修正。' \
  --execute
```

The command uses an idempotency key derived from the source message and reply
text, sends with `--reply-in-thread`, and reads the created message back through
the same configured profile. Ordinary chatter remains a no-reply path;
enabling this capability does not grant reviewer-notification or other
outbound authority.

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
