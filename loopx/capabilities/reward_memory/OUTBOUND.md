# Outbound guidance recall

[中文版](OUTBOUND.zh-CN.md)

This optional Reward Memory surface recalls reviewed operating preferences
before an agent sends a message. It is not a transport, a text classifier, or
permission to send. The first shipped caller is goal/agent-bound
`loopx lark-inbox send` and `reply`; other tools and Goal Topic auto-replies are
not intercepted by this integration.

## Enable and validate

Use the existing agent-scoped Reward Memory experiment configuration. Add
`outbound_message.before_send` to the corpus and standing-policy surface scopes
and to `surfaces`, using adapter `scoped_feedback`. Set the exact
`peer_ref: agent:<agent-id>` and `automation.automatic_recall: true`. Use a
function-boundary profile with one query and a small result limit. Ingest only
explicitly reviewed, public-safe operating guidance as `soft_preference`;
do not upload draft messages or private incident transcripts.

```sh
loopx configure-goal --goal-id <goal-id> \
  --reward-memory-config .loopx/config/reward-memory.json \
  --reward-memory-agent <agent-id> --execute
loopx reward-memory experiment-status --goal-id <goal-id> --agent-id <agent-id>
loopx lark-inbox send --goal-id <goal-id> --agent-id <agent-id> \
  --route-key <configured-route> --text '<message>' \
  --message-purpose help --provider-preflight --format json
```

Provider preflight verifies identity, membership, mentions and the provider's
dry-run rendering before recall. A plain preview without `--provider-preflight`
does not call either provider. The result includes `outbound_guidance` when the
surface is active. It performs no send. With relevant guidance, even an initial
`--execute` returns `agent_review_required` and zero writes.

The executing agent must read the guidance, check current facts, alternatives,
recipient and duplicates, and decide whether a message is still appropriate.
If it is, repeat the same send/reply command with `--execute` and
`--reviewed-guidance-digest <returned-digest>`. This is an agent review step,
**not a user approval gate**. The digest binds the reviewed guidance, purpose,
scope, sender, destination, placement and message. Changes invalidate it.
It proves acknowledgement, not the quality or truth of the agent's reasoning.
Transport idempotency and readback remain owned by the existing sender.

Purposes are `help`, `progress`, `urgent`, and default `unspecified`; there is
no substring inference from message text. Urgent notices recall guidance but
do not wait for review. Empty/unavailable memory preserves the existing send
path and never asks the user to repair the provider. Permission or sender
validation failures still block normally. Hard-policy memories are not
interpreted by this advisory adapter.

The generic implementation lives in `reward_memory.outbound`; the Lark adapter
receives a callback over an opaque intent digest. It owns no memory store or
project-specific escalation rule. Raw text, chat ids and sender profiles never
enter the recall query. Guidance is returned in the caller's private response,
not sent to the recipient or persisted into the public registry.

## Disable and coverage

Set `automation.automatic_recall: false` to disable recall for the experiment,
or remove this surface from the experiment to disable only outbound recall.
Unconfigured agents and existing direct provider calls preserve their previous
behavior. Activation grants no provider credentials or external-write authority.

Tests cover real recall machinery, readback, agent scope, intent invalidation,
unavailable providers, urgent notices and both actual sender paths with a
synthetic transport. A live read-only provider check is separate from those
tests; no test should send a group message as a smoke side effect.
