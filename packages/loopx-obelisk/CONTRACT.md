# Decision Context advisory provider v0

`loopx-obelisk` implements the existing `decision-context` capability through
`decision_context_advisory_provider_v0`. LoopX owns profile activation,
extension lifecycle checks, bounded request construction, fail-open behavior,
public projection, evidence rebase, and every durable transition. The provider
owns only retrieval through Obelisk's public CLI.

## Request

The extension receives one
`decision_context_advisory_retrieve_request_v0` JSON object on stdin. The
operation is exactly `retrieve`; `scope_ref` is exactly
`host-session:codex:<thread-id>`; result count and timeout are bounded. The
provider does not accept a raw deep link, filesystem path, Goal transition, or
credential.

## Response

The extension returns one
`decision_context_advisory_retrieve_response_v0` JSON object on stdout. Each
item has a provider-private `resource_ref`, a public-safe generic `summary`,
transient `content`, and an optional numeric `score`. Core validates the
allowlist and bounds before creating `ContextProviderRetrieval`; its public
receipt hashes the resource reference and omits content. An explicit one-off
recall may return the content only in a local-private transient CLI packet; it
does not persist the scope, query, or content.

`status=completed` may contain zero items. `status=unavailable` contains no
items and carries a compact `reason_code`. Process failure or an invalid
response is converted by Decision Context into a fail-open unavailable receipt.

## Obelisk boundary

The provider translates the normalized Codex thread id to Obelisk's documented
`codex:<thread-id>` session id and calls only `obelisk --query <temporary.js>`.
The query uses `search(query, { sessionId, limit })`, accepts only Codex rows,
and excludes a row when Obelisk marks its session `is_invoking`. The temporary
query file is removed after every attempt. Doctor calls only
`obelisk --version`.

## Validation

```bash
python3 packages/loopx-obelisk/smoke/obelisk_provider_smoke.py
python3 -m pytest -q tests/capabilities/test_decision_context_extension_provider.py
```
