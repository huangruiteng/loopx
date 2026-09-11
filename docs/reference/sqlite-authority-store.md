# SQLite authority provider

SQLite is an **opt-in local conformance candidate**, behind the existing
TypeScript `AuthorityStore` interface. File remains the default. This slice
does not promote a goal, migrate existing authority, enable cross-host writes,
or qualify ten elapsed days of operation.

## Placement and persistence

The provider belongs to the existing shared-coordination authority boundary
(`loopx/control_plane/coordination`). It is bundled with LoopX, not a new
capability or extension. Legal transitions, actor/lease checks, operation
digests and replay decisions remain with the existing typed transaction
executors. Python only admits the corresponding `sqlite_v0` source receipt.

Each goal has a separate database under the runtime's `authority/sqlite-v0`
directory. Metadata binds the goal, schema version and random database
incarnation. Provider revisions combine that incarnation with a monotonic
integer sequence; they are not authority revisions or lease epochs.

The version-1 schema contains:

| Table | Contract |
| --- | --- |
| `metadata` | Version and database/goal identity |
| `head` | One bounded pointer to the current committed projection |
| `commits` | Unique operation ID, canonical commit digest, ordered cursor, original receipts, events and full projection |

`commits` also serves as the durable projection outbox used by
`scanCommitted`. There is no independent ACK or second receipt authority.
Existing consumers resume by cursor. A unique operation index makes receipt
lookup and cursor paging indexed. The common continuity check counts the compact
covering index, so total read/write cost is not independent of history length.
It does not deserialize the complete retained payload history. Historical receipts and full projections are retained without
pruning. Fixed live state therefore produces linear database growth, not
bounded total disk use. Growing application projections require separate
retention/compaction work.

Writes use `BEGIN IMMEDIATE`, a five-second busy timeout, WAL and
`synchronous=FULL`. The head, receipt, events and outbox row commit together.
Before-COMMIT failures roll back; a COMMIT error reports an ambiguous outcome
for receipt reconciliation. Readers use committed snapshots; no history rewrite
is needed for a new transaction. SQLite storage durability still depends on the
local filesystem and hardware honoring synchronization.

Schema changes are explicit: unknown `user_version`, foreign tables or a
different goal/incarnation fail closed. No automatic migration, identity
rotation, corruption repair, or network-filesystem sharing is supported.

## Read integrity

Authority reads share one SQLite snapshot for metadata, head and requested rows.
The same check runs inside the write transaction before any new commit row:
positive unique integer cursors must have `min=1` and `count=max=head`. Thus a
missing head, rolled-back head, or internal cursor gap is rejected as
`provider_protocol_violation` before returning authority or accepting a write.

The newest row's canonical commit digest is recomputed on every authority read
and write. Historical receipt reads additionally validate their selected row;
paged scans validate each returned row and the lookahead row used for
`has_more`. The digest includes the operation ID, projection, events, receipts
and expected predecessor revision, reconstructed from the unchanged v0 sequence
contract. No schema migration or alternate digest format is introduced.

This is integrity validation of the current and accessed evidence, not a full
cryptographic audit of every historical payload on each call. Unaccessed older
row digests are checked when those rows are read. Checksums detect inconsistent
data; they do not authenticate an administrator who can rewrite both the data
and its digest. Restoration of an older, internally consistent database remains
outside this slice's qualification boundary.

## Explicit selection

Use an isolated qualification runtime and an empty, unpromoted goal. Set
`RUNTIME_ROOT` to that runtime's absolute directory. SQLite qualification uses Node 22.14. The provider checks that
`DatabaseSync.close()` finalizes prepared statements synchronously before
opening an authority file; older experimental drivers are rejected. In
particular, Node 22.6 leaves closed database handles alive until GC on Windows
and is not supported for this provider. File-backed LoopX still supports Node
22.6 and needs no SQLite flag. The module loads SQLite only after opt-in.

From the repository checkout, preview selection:

```sh
node --experimental-sqlite --experimental-strip-types \
  loopx/control_plane/coordination/local_authority_provider.ts \
  --runtime-root "$RUNTIME_ROOT" --goal-id example
```

Apply the same command with `--execute`. It creates the empty database and a
durable per-goal selector bound to its incarnation. Repeating it is idempotent.
The command rejects an existing canonical file head or a writer fence. It does
not bootstrap or promote authority. Existing qualification/promotion gates
still govern the first canonical state, with the chosen provider used as the
destination. Do not bypass those gates to enable a live goal.

The process starting the managed Effect runtime must use the qualified Node
runtime too. Stop a previously running managed runtime normally before changing
its Node executable. Adding an experimental flag to Node 22.6 does not fix its
statement lifecycle.

After separately admitted canonical initialization, ordinary `loopx todo`
commands use the persisted selector. For example:

```sh
loopx --registry "$REGISTRY_PATH" --runtime-root "$RUNTIME_ROOT" \
  --format json todo list --goal-id example
```

An unavailable database, malformed selector, changed incarnation or lost
selector fails closed; none silently falls back to file authority. Deleting
the generated Markdown does not delete the canonical Todo state.

Provider-open errors retain selection identity separately from request errors.
A validated SQLite selector produces `source_authority=sqlite_v0` even when its
database is missing or unreadable. An invalid, unavailable or missing selector
reports `source_authority=null` because selection is unresolved; it never guesses
file authority. Typed `local_authority_selector_*` and
`local_authority_provider_*` reason codes identify that boundary, with a
`provider_reason_code` when the store returned a more specific diagnostic.
These failures set both `decision_read_from_provider=false` and
`legacy_fallback_used=false`. Successful responses and unrelated request/domain
errors retain their existing contracts.

## Promotion failure evidence

`legacy_writer_fenced` reports whether this promotion invocation verified the
exact persisted fence against the request. Provider opening precedes that
verification so opening errors retain their selected-provider diagnostics.
Such early failures report `false`, even if a fence exists but was not read and
matched. This is not proof that legacy writes are allowed; callers must consult
the durable writer guard. After successful fence verification, later failures
retain `true`. Request fields alone never establish fencing evidence.

The failure-path regression matrix covers:

| Boundary | Evidence checked |
| --- | --- |
| Selector/database open | List, exact read, mutation, create, claim, native/planning update, compatibility edit, terminal, monitor poll, archive, ACK and promotion retain typed source/reason, no fallback and unchanged authority bytes. |
| Fence readback | Missing, malformed and mismatched fences do not establish verified fencing; an open failure cannot infer it from an existing marker. |
| After verified fence | Missing/invalid shadow and rejected qualification preserve verified fencing without canonical writes. |
| Existing promotion readback | Exact receipt/first-commit lineage permits replay; missing receipts or mismatched lineage reject without modifying authority. |

The matrix is typed against every exported runtime entrypoint so adding a new
entrypoint requires an explicit failure fixture.

These tests use disposable file/SQLite stores and the production runtime
entrypoints. They preserve the current qualification gate: mirrored file shadow
health alone does not authorize a new canonical cutover. Shared store conformance
separately covers transactional CAS, commit ambiguity, receipt reconciliation and
projection replay. No active Goal is needed for this validation.

## Stop and recovery boundary

To stop using the candidate, stop the owning goal/host runtime and retain its
database and selector. For a managed goal, `loopx configure-goal --goal-id
example --quota-compute 0 --execute` pauses automatic turns; separately stop
any active host process before taking an offline backup. Pausing does not
cancel a transaction already running.

There is deliberately no in-place switch back to file authority after commits:
that requires an explicit migration with receipt/lineage validation. Do not
delete the selector to disable the provider. Preserve the database together
with any `-wal`/`-shm` files when recovering an interrupted runtime; use SQLite
backup facilities or a fully stopped database for a coherent backup. Restoring
an older snapshot as concurrent live authority is not supported. Disposable
qualification runtimes may be retired as a whole after their processes stop.

Selection grants local storage use only. It grants no actor/lease ownership,
external service access, cross-host synchronization or promotion authority.

## Reproduce validation

```sh
npm ci --ignore-scripts
npm run typecheck:control-plane
node --no-warnings --experimental-sqlite --experimental-strip-types --test \
  tests/control_plane_ts/sqlite_authority_store.test.ts \
  tests/control_plane_ts/local_authority_provider.test.ts
python -m pytest -q tests/control_plane/test_sqlite_authority_cli.py
node --no-warnings --experimental-sqlite --experimental-strip-types \
  examples/coordination/sqlite-capacity.ts
```

The tests exercise real SQLite, independent writer processes, CAS competition,
original-receipt replay, lost responses, interrupted head publication, schema
rejection, persistent selection, native CLI read/update and planning replay after
Markdown deletion, and archive acknowledgement against the selected store.
The capacity command uses a disposable database with a fixed 4 KiB live
payload, 10k/100k commits, and 100 samples per read workload. It emits measured
latency percentiles and database bytes, then deletes only its temporary
database. These accelerated measurements do not satisfy the separate ten-day
soak, retention, disk-exhaustion, restore or promotion gates.
