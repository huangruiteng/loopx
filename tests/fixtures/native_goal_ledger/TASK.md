# Replay-safe local ledger

Build `ledger.py` using only the Python standard library. Implement
`reduce_events(events)` and `python ledger.py INPUT` (UTF-8 JSONL).

Every event has nonempty string `id`, `account`, and `type`. Credit/debit events
have a strictly positive integer `amount` (booleans are invalid). Reverse events
have `target`, referencing an earlier credit/debit in the same account. Reverse
an original at most once; never reverse a reversal. Reject overdrafts at every
prefix, including reversal of a credit. Exact event replays are idempotent;
conflicting reuse of an id is invalid. Reject missing/extra fields, invalid
types and references with `ValueError`. Never mutate input dictionaries. Keep
zero-balance accounts; names are case-sensitive and may contain Unicode.

The CLI ignores blank lines and prints exactly one JSON object sorted by account
with a trailing newline. Empty input succeeds with `{}`. Invalid JSON or domain
input must leave stdout empty, write a concise diagnostic to stderr, and exit
nonzero. Add reducer and subprocess tests, including long replay, and a README.

This is a finite local task: no upload, publication, deployment,
package installation, or external side effect is part of acceptance. Keep all
changes in the disposable project/worktrees. Do not change this specification
or LoopX source to make the task pass. Do not substitute fabricated evidence
for actual code delivery.
