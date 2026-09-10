# Unified Finance Gate Contract

`finance_case_contract_v1` is the common, provider-neutral contract for
research cases evaluated by this extension. It does not collect market data or
calculate a finance metric. Collectors and metric providers produce frozen
typed observations; the gate engine compares those values with contract-owned
rules and thresholds.

## Ownership

| Surface | Owner | Responsibility |
| --- | --- | --- |
| Contract | Finance extension | Revision, cutoff, frozen identities and thresholds, gate order, safety boundaries |
| Observation | Collector or metric provider | Public evidence references and a typed value, missing marker, or conflict marker |
| Gate engine | Finance extension | Typed comparison, deterministic short-circuiting, and disposition |
| Replay harness | Finance extension | Canonical hashes and byte-identical re-evaluation |
| Revision promotion | Human owner | Approval after historical, walk-forward, and shadow review |

The contract is intentionally smaller than any individual method. A de-beta,
quality, valuation, or market-regime method may choose different gate ids, but
all must use the same typed comparisons and transition rules. Boolean and
string gates support equality. Numeric gates support equality and ordered
comparisons. Providers cannot declare their own pass or fail result.

## Attribution And Industry Overlays

Layered beta attribution is deterministic arithmetic over caller-supplied,
point-in-time observations. The explained order is frozen as market, rate,
sector, narrow peer, cycle, and event. Residual is computed as total move minus
all six explained components only when every component is observed. The
`de_beta_residual` gate must use that computed value; an independent or
contradictory residual observation is rejected. Attribution does not estimate a
factor or select a source. It does execute the bound gate input and requires the
observation window to satisfy the contract cutoff before it can report a
complete result. Top-level `disposition` preserves the gate decision, including
`rejected`, while `completeness` independently reports whether the gate evidence
and all six components are complete.

An attribution is bound to one gated case identity. The gate input carries the
`case_id` and `subject_ref` of the case it evaluates, and the attribution's
`case_reference` must match both. A passing gate therefore cannot be reused to
present an attribution for a different case or a different security as
research-complete. The `observation_window` must be real ISO-8601 dates that sit
inside the contract's frozen `[point_in_time, evaluation_as_of]` window, so a
malformed or future window cannot be presented as complete.

Industry metric packs are semantic overlays on the same case contract. A pack
may require metric ids, value types, and allowed operator directions. It cannot
provide a threshold, reorder common source or cutoff gates, reinterpret missing
or conflicting evidence, or alter promotion authority. The required
`source_lineage` and `point_in_time` gates are provider-neutral
`boolean eq true` authority gates; a pack input cannot preserve their ids while
changing their type, operator, or reference semantics. Metric thresholds remain
inside the frozen case contract, and observations still pass through the common
gate engine.

## Gate States

| Result state | Meaning | Disposition |
| --- | --- | --- |
| `passed` | Evidence satisfies the frozen gate | Continue |
| `failed` | Evidence falsifies the frozen gate | `rejected` |
| `missing` | Required evidence is absent | `insufficient_evidence` |
| `conflict` | Valid evidence disagrees | `insufficient_evidence` |
| `not_run` | An earlier gate already blocked evaluation | No new conclusion |

Observations must exactly match the ordered `gates` list. An `observed` value is
typed and compared with the frozen rule to produce `passed` or `failed`.
Providers may instead report `missing` or `conflict`. The first `failed`,
`missing`, or `conflict` result blocks the case, and every later observation
must be `not_run`.

Evidence references are state-dependent: `observed` observations require at
least one reference, `conflict` observations require at least two references,
and `not_run` observations must contain none.

Running a later gate after a blocker is rejected as an invalid input rather
than silently accepted.

Passing every gate means only `eligible_for_research_successor`. It never means
method promotion, investment advice, or permission to trade.

## Replay

### Source query coverage (extension 0.5.0)

A gate can opt into receipt-derived source coverage with a `source_coverage`
requirement. It must use `boolean eq true`. The requirement freezes
`request_identity` (`market`, `universe_id`, `query_id`) and
`collection_started_at`; its universe must match the case contract. `query_id`
identifies immutable query parameters in the adapter's evidence catalog; a
reused label cannot prove that those parameters actually stayed unchanged.

The matching observation contains **only** `gate_id` and `source_pages`.
Callers cannot also supply a value, state, reason, or computed coverage result.
The engine derives the observation and includes a `finance_source_coverage_v1`
report in that gate's result. A coverage gate after an earlier blocker instead
uses the existing `not_run` observation. Unbound gates reject receipt fields.
The complete runnable input is
[`finance-source-coverage-v1.json`](examples/finance-source-coverage-v1.json).

Each normalized page contains its request identity, positive `page_number`,
`source_status`, `started_at`, `observed_at`, `rows`, `total_count`, `has_more`,
`snapshot_id`, and `snapshot_evidence_ref`. Row metadata consists of `id`,
`market`, `content_sha256`, and optional `publication_at`. Bodies and unmodeled
fields are rejected. Receipts require timezone-aware timestamps ordered inside
the frozen collection window. A date-only case evaluation cutoff is midnight
UTC; use a timestamp for intraday or end-of-day collection. The collection start
must lie inside the case window. Collection time does not prove availability at
the case's earlier historical `point_in_time`.

| Coverage state | Evidence condition | Gate / case result |
| --- | --- | --- |
| `complete` | Contiguous pages from 1, a unique terminal page, one reported total matching unique IDs, consistent versions, common nonempty snapshot identity and evidence reference | `passed`; later gates still determine the case |
| `partial` | Missing pages, unknown total/end/snapshot assertion, or no observations | `missing` / `insufficient_evidence` |
| `unstable` | Cross-page overlap, changed repeated page, conflicting record versions, totals, terminal pages, or snapshots | `missing` / `insufficient_evidence`, with explicit instability reasons |
| `source_error` | Source failure, missing rows, mismatched query/market, or invalid row metadata | `missing` / `insufficient_evidence`, with explicit error reasons |

Source errors take precedence over instability, then gaps; all reason lists
remain visible. Instability is not an economic hypothesis failure. The engine
uses `missing` rather than inventing multiple independent evidence references
to satisfy the existing `conflict` observation contract. A complete query may
contain zero records; an empty error response or absent receipt never proves
that. Identical retries preserve unique IDs; changed versions remain recorded.

Completeness is **conditional on adapter assertions**. The engine does not fetch
or authenticate snapshot evidence, establish source truth, prove historical
publication time, discover new economic events, or validate an investment edge.
`snapshot_evidence_state=adapter_asserted` makes that limit explicit. The
coverage digest identifies computed evidence, not independent corroboration.
Only normalized, authorized public metadata should enter this public reducer.

Inputs are bounded to 128 receipts, 500 rows per receipt and 5,000 rows including
retries. Exceeding a bound is an explicit error; no truncation is called complete.
Page-number validation does not allocate memory proportional to a reported last
page. Freeze a narrower query or use a domain adapter with its own explicit
partition coverage contract for larger collections.

No new collector, scheduler, builtin capability, or CLI command is added.
Existing `evaluate`, `replay`, and the managed extension entrypoint consume the
same input. Replay binds the requirement, receipt metadata and computed report.

The replay receipt binds three SHA-256 values:

- the normalized contract;
- the complete input, including evidence references;
- the evaluation before the receipt is attached.

Canonicalization uses compact ASCII JSON with sorted keys. Replay recomputes
the evaluation and requires matching hashes plus byte-identical canonical
output. Changing a threshold, cutoff, observation, reason, or result fails
closed.

## Compatibility

The existing `finance_value_discovery_input_v0` reducer and
`finance_value_discovery_extension_v0` provider protocol remain supported.
`finance_case_gate_input_v1` now requires a `subject_ref` naming the case
subject, so a gate input packet must declare the subject it evaluates; this
binds the case identity end to end. The `finance_value_discovery_input_v0`
packets are not reclassified and gain no new fields.

The 0.5.0 coverage gate is opt-in. Inputs without `source_coverage` retain their
existing normalized contract, result fields and replay bytes. Older extension
versions reject the new fields; install 0.5.0 before invoking this form. To stop
using it, choose a separately frozen contract revision without that gate, rather
than removing evidence from an already evaluated contract. Prior evaluations
must be replayed with their original contract and implementation version. To
disable the entire optional workflow, use `loopx extension disable
loopx-finance-value-discovery --execute`; this does not authorize any financial
operation or remove evidence already stored by its owner.
