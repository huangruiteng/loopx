# OpenViking project peer provider

LoopX includes a thin, opt-in OpenViking provider for project-scoped semantic
preferences. One canonical project maps to one reserved OpenViking peer. Git
worktrees and fresh clones of the same `origin` therefore share a memory scope,
while another repository resolves to a different scope.

This adapter does not implement memory extraction, ranking, update, or
supersede semantics. OpenViking owns those behaviors. LoopX only derives the
project peer, performs bounded `find` calls, and returns the existing semantic
preference provider protocol for a function-owned application and receipt.

## Scope contract

- Identity comes from the normalized Git `origin`, never the checkout path.
- A non-Git project must provide a stable `--loopx-project-id`.
- Recall targets the exact project peer by default.
- Each `find` binds the OpenViking request actor to the derived project peer.
- User-global memory is available only through `--include-global-fallback`.
- The default budget is one `find`; explicit global fallback needs at least two.
- Only concrete preference nodes under the selected target are returned.
- OpenViking failures remain subject to the outer surface's `fail_open` or
  `fail_closed` policy.

Inspect the local scope without contacting OpenViking:

```bash
loopx semantic-preference openviking-provider \
  --project . \
  --user-space default \
  --describe-scope
```

The output contains the peer id and target URIs, but not the repository URL or
local checkout path. An OpenViking agent integration can use the returned
`peer_id` when adding a user message to a session. For an isolated native
write, create that session with self memory disabled, peer memory enabled, and
the desired memory types allowed. `peer_id` alone identifies the speaker but
does not force an extractor operation away from user-global memory. OpenViking
then owns write, update, and supersede semantics inside the selected peer.

## Local-private hook config

Keep the config ignored and untracked. Provider paths and OpenViking service
configuration remain local:

```json
{
  "schema_version": "semantic_preference_hook_config_v0",
  "enabled": true,
  "provider": {
    "argv": [
      "loopx",
      "semantic-preference",
      "openviking-provider",
      "--project",
      ".",
      "--user-space",
      "default",
      "--max-find-calls",
      "1"
    ],
    "timeout_seconds": 30
  },
  "surfaces": {
    "issue_fix.pr_description": {
      "query": "PR description structure and validation preferences",
      "limit": 3,
      "failure_policy": "fail_open"
    }
  }
}
```

Add `--ov-bin` or `--cli-config` to the provider argv only when the local
OpenViking installation needs explicit paths. Use `--doctor` with the same
arguments for a read-only `ov status` probe.

The consuming function remains the final application boundary. For Issue Fix,
`build_issue_fix_pr_description()` owns one recall, fail-open preservation,
preference attribution, and the compact application receipt.
