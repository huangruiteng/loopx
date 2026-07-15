# Provider-neutral review batch v0

`review_batch_v0` is a cold-path composition contract for bounded human review.
It turns already-normalized candidate packets into one deterministic decision
surface. Candidate collection, repository APIs, chat APIs, scoring policy, and
external delivery remain adopter responsibilities.

Use it when several sources need one stable sort/limit, an exact decision
digest, and compact delivery receipts:

```bash
loopx review-batch compose --request-json request.json --format json
loopx review-batch bind-decisions \
  --batch-json batch.json \
  --decisions-json decisions.json \
  --format json
```

Both commands are local and effect-free. They do not fetch candidates, publish
comments, update documents, send chat messages, or infer external authority.

## Composition request

A `review_batch_request_v0` contains:

- `batch_id` and `generated_at`;
- `policy.soft_limit`, `policy.hard_limit`, an ordered list of stable priority
  reason codes, and the adopter's allowed decision values;
- typed `candidate_sources[]`, each with `source_id`, `source_kind`, and
  normalized `candidates[]`;
- optional compact `sink_receipts[]` produced by an external adapter.

Each candidate provides a stable id and source reference, a bounded summary,
priority tier and registered reason codes, compact evidence state/references,
and either a proposed action or a compact draft. The core sorts candidates by
tier, configured reason order, and stable candidate id; it applies the hard
limit before the soft report limit.

The core rejects raw content, logs, transcripts, credentials, secret/token
fields, and local-private paths. Adopters must normalize those inputs before
calling the command.

## Digest and decision binding

Every selected candidate receives a digest over its normalized identity,
evidence, priority, and proposal. The batch digest binds the exact ordered list
of candidate digests to the policy. `review_batch_decisions_v0` must repeat the
batch digest and each decided candidate's digest. `bind-decisions` rejects
stale, tampered, unknown, duplicated, or policy-invalid decisions by
recomputing both digest layers, then emits a compact
`review_batch_decision_receipt_v0` without executing them.

## Delivery receipts

Sink delivery runs outside the core. A receipt is provider-neutral:

- `sink_id` and `sink_kind`;
- `status`: `preview`, `sent`, `failed`, or `skipped`;
- optional `idempotency_key` and `receipt_ref`;
- `readback_verified`.

`sent` is accepted only when idempotency, a receipt reference, and verified
readback are all present. The core stores no provider response body.

## Adopter boundary

An adopter may source pull requests, issue-comment drafts, documents, or other
reviewable items, but those names and policies do not enter this core. It owns:

- candidate adapters and freshness checks;
- domain-specific risk scoring mapped to registered reason codes;
- document/chat rendering and delivery;
- authority checks before any external effect;
- applying only decisions whose exact digests were bound successfully.

This keeps a daily maintainer report, a content review queue, and an operations
decision brief on the same small contract without hard-coding one provider or
project into LoopX.
