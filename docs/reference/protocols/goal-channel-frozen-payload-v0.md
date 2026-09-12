# Goal Channel frozen payload v0

Status: provider-backed, capability-neutral exact-approval delivery contract.

`goal_channel_frozen_payload_request_v0` lets any producing capability submit
one final public-safe Markdown result for a LoopX Goal Channel. It does not
classify domain facts or make content safe. The producer retains responsibility
for semantics, sources, redaction, and the truthful `public_safe=true`
attestation.

## Lifecycle

1. The producer supplies a capability id, opaque payload ref, title, Markdown,
   footer, and one `public_claim:action:<scope>` decision scope.
2. LoopX renders the final Lark card, hashes the canonical card, and stores the
   content in an owner-local `0600` receipt. Public Todo state contains only
   the receipt id, digest, scope, and execution requirements.
3. LoopX creates one blocked Agent delivery Todo and one User gate whose
   `unblocks_todo_id` points to that successor. Approve consumes only the exact
   required scope; reject or cancel keeps delivery blocked.
4. Delivery reloads both Todos and the private receipt. It fails closed unless
   the gate is done with `approve`, the successor is open (or already done for
   an exact replay), and its required decision scopes are empty.
5. The Lark extension resolves the route only from the durable Goal Channel
   binding. The caller cannot select the chat, profile, Bot, sender, or mention
   recipients. Binding drift after preparation invalidates the approval.
6. Before sending, LoopX verifies the project Bot and reads complete Bot-visible
   channel history. An exact existing card is reused. Otherwise one
   provider-idempotent message is sent. Provider-native sender, chat, and card
   readback are required before the delivery Todo and receipt become satisfied.

## Boundaries

- Receipt content and provider identifiers stay in local-private runtime state.
- Public command results expose only opaque ids, digests, decision scopes, and
  lifecycle status.
- Mention markup is rejected; audience selection belongs to a capability with
  an explicit typed audience policy.
- The contract grants no standing publication authority. Every payload needs
  its own exact gate unless another capability, such as Periodic Report, owns a
  separately documented standing subscription.
- A successful provider write without exact native readback is not completion.

This mechanism complements `content_ops_item_v0`: content-ops can track
provider-neutral item state without storing bodies, while this Lark extension
owns one concrete Goal Channel effect and its private payload receipt.
