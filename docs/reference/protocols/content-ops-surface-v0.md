# content_ops_surface_v0

Status: public-safe state-surface contract v0.

`content_ops_surface_v0` is a compact creator/self-media operations state
surface. It lets LoopX remember source status, angle selection, draft state,
feedback effects, publish gates, and reusable material memory without turning
LoopX into a publisher or storing raw platform/chat material.

The surface is intentionally a meta layer over the generic LoopX model:

- source records may promote into normal LoopX agent or user todos;
- feedback records may become preference hints, boundary corrections, rewrite
  todos, or publish decisions;
- publish records are gates, never implicit permission to post;
- projections are read-only views and must be recomputed from compact source
  records.

## Records

| Record | Required Purpose |
| --- | --- |
| `source_item_v0` | Compact observation with `source_status`, `freshness`, terms note, attribution, and allowed quote/use policy. |
| `angle_candidate_v0` | Candidate content angle linked to source items, with audience, topic, preference fit, evidence quality, decision, and rejection reason when skipped. |
| `draft_item_v0` | Outline/draft/rewrite state with source map, preference hints, validation surface, and `publish_gate_id`. |
| `feedback_signal_v0` | User or operator feedback with a typed effect: preference hint, source boundary correction, rewrite todo, or publish decision. |
| `publish_gate_v0` | Human approval state for external posting. Draft existence never allows autopublish. |
| `material_memory_v0` | Durable source-safe library entry with attribution, reuse boundary, rejected angles, and preference hints. |
| `connector_trial_v0` | Metadata-only trial plan for a browser, chat, document, or platform connector before LoopX ingests real source records. |

## Source Status

`source_item_v0.source_status` should use one of:

- `public`;
- `private_needs_review`;
- `synthetic_public_safe`;
- `unpublished`;
- `forbidden_for_public_surface`.

Every source item must also include `freshness` and `allowed_use`. The v0
allowed-use set is:

- `summarize_and_transform`;
- `metadata_only`;
- `do_not_quote`;
- `forbidden`.

This keeps connector output from becoming raw evidence by accident. Browser,
chat, platform, and document connectors own raw retrieval; LoopX stores only the
compact source contract.

## Connector Trials

`connector_trial_v0` lets an operator start testing a real connector without
turning LoopX into a scraper, publisher, or private archive reader. The trial
records only the connector handle, source status, freshness, allowed use, trial
state, promotion target, and gates.

The first creator-ops trial surface covers two suggested connector routes:

- X via `ego-lite browser`: public/terms-aware signal intake with
  `access_mode=public_metadata_only`, no posting, no login-gated timeline dump,
  and promotion only to compact `source_item_v0` records.
- WeChat via `chatlog-alpha/chatview`: private-needs-review material intake with
  `access_mode=private_metadata_only`; LoopX stores metadata-only signals until
  the owner explicitly approves source use.

Every connector trial must set `external_write_allowed=false`. Private or
metadata-only trials must expose a user gate before source body use, quoting, or
publication.

## Projection

`content_ops_surface_projection_v0` is the first-screen status view derived from
the compact surface. It should include:

- `first_screen.waiting_on`: `user`, `operator`, or `agent`;
- counts for source review, ready-to-draft angles, feedback waits, and publish
  decisions;
- connector-trial counts by state, access mode, and owner gate;
- `todo_candidates` that can promote into normal LoopX todos;
- source-status, draft-state, feedback-effect, and publish-gate counts;
- validation result and public/private boundary result;
- a `truth_contract` that says `projection_is_writable=false`.

The projection is useful when an operator can answer:

- what can be drafted safely now;
- what source still needs review;
- what feedback changed durable preferences or boundaries;
- what publish decision is waiting;
- which side work can continue while publishing is gated.

## Boundary Rules

The surface is valid only when:

- every draft has a source map and publish gate;
- every publish gate has `approval_required=true` and
  `autopublish_allowed=false`;
- raw private material, raw platform bodies, credentials, local paths, and raw
  logs are absent from compact records;
- private or metadata-only sources remain blocked from quoting until a user or
  owner review changes the source status;
- external posting, platform publish, and production actions remain outside
  this contract.

## Fixture And Smoke

The public-safe fixture helper is implemented in
`loopx/content_ops_surface.py`. It provides:

- `build_content_ops_surface_fixture()`;
- `validate_content_ops_surface(surface)`;
- `project_content_ops_surface(surface)`.

The durable smoke is:

```bash
python3 examples/content-ops-surface-fixture-smoke.py
```

The smoke checks record coverage, source/draft/gate references, first-screen
projection fields, connector metadata-trial routing, todo candidates,
no-autopublish policy, and public/private boundary hygiene.
