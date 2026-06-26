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
`loopx/capabilities/content_ops/surface.py`. It provides:

- `build_content_ops_surface_fixture()`;
- `validate_content_ops_surface(surface)`;
- `project_content_ops_surface(surface)`.
- `build_content_ops_preview_packet()`;

The CLI preview is the first runnable connector-pilot entry point:

```bash
loopx content-ops preview --format json
```

It returns `content_ops_preview_packet_v0` with the fixture, projection,
validation, connector-trial counts, and explicit booleans proving that no
external reads, external writes, private source-body reads, or autopublish
actions happened. Real connector adapters should first match this packet shape
before they ingest any public platform metadata or private metadata-only source
handle.

Before a real connector even decides what to read, the generic exploration
planner can render the selected source lanes, access/read status, route,
fallback, evidence quality, promotion target, and owner gates:

```bash
loopx content-ops exploration-plan --format json
```

It returns `content_ops_exploration_plan_packet_v0` with an
`exploration_plan_v0` fixture. This is the first reusable primitive selected
from the CS-Notes exploration capability map: repo issues, public social
signals, private chat metadata, and experiment result counters can all be
represented as lanes before source bodies, response payloads, local paths, or
external writes are captured. Private or raw-material lanes must project a
concrete user gate rather than silently becoming readable work.

Repo issue fix work can promote the public issue lane into a concrete intake
packet:

```bash
loopx content-ops issue-fix-intake --format json
```

It returns `content_ops_issue_fix_intake_packet_v0` with an
`issue_fix_intake_v0` fixture built on `exploration_plan_v0`. The packet models
public GitHub issue/PR metadata, selected code-context routes, candidate agent
todos, owner/user gate projections, and the next safe action. It performs no
external read, stores no issue body or comment body, records no local paths or
private repo state, and does not authorize external issue comments, assignment,
merge, or automerge. If a fix path needs private repro material, the packet
keeps that as a conditional user gate while allowing metadata-only triage and
focused smoke drafting to continue.

The next step toward a real issue-fix workflow is the mocked GitHub metadata
adapter preview:

```bash
loopx content-ops issue-fix-metadata-preview \
  --url https://github.com/owner/repo/issues/123 \
  --metadata-json mocked-provider.json \
  --format json
```

It returns `content_ops_issue_fix_metadata_preview_packet_v0`. The default path
does not perform a live GitHub read; it accepts either a public issue/PR
reference or mocked provider JSON and copies only allowlisted metadata fields
such as repo, issue ref, state, labels, updated_at, and comments_count. Raw
fields such as issue body, comment bodies, timeline events, or provider
response payloads are represented only as gated field names. The packet also
emits a `loopx_todo_writeback_preview_v0` candidate for the agent todo, but it
does not write the todo unless a later command explicitly executes that
writeback.

A live public metadata read is available only as an explicit opt-in:

```bash
loopx content-ops issue-fix-metadata-preview \
  --url https://github.com/owner/repo/issues/123 \
  --fetch-metadata \
  --format json
```

The opt-in path uses `gh api --jq` to emit only the body-free metadata fields
consumed by the packet. The public artifact records `external_reads_performed:
true` and `adapter_preview.live_read_performed: true`, but issue bodies,
comment bodies, timeline events, raw provider responses, stdout/stderr, local
paths, todo writes, external comments, PR creation, merge, and publish actions
remain outside the artifact.

Metadata preview is only the intake surface. The issue-fix product path should
continue to an executable acceptance loop:

```bash
loopx issue-fix acceptance-fixture --format json
```

That command returns `issue_fix_acceptance_loop_v0` with a validated fix
artifact: failing repro, minimal patch, passing focused validation, and a
PR-review-ready evidence packet. See
[`issue_fix_acceptance_loop_v0`](issue-fix-acceptance-loop-v0.md).

The first reusable public connector adapter is the public-handle observation
command:

```bash
loopx content-ops observe-public-handle \
  --url https://x.com/OpenAI \
  --source-item-id source_x_openai_public_handle_20260623 \
  --format json
```

It returns `content_ops_public_handle_observation_packet_v0` with a compact
`source_item_v0`. By default it performs one HEAD-only metadata read against a
public `https` URL, rejects localhost/private-address/credential-bearing/query
URLs, does not follow redirects, does not read response content, does not send
cookies, does not log in, does not write externally, and never grants
autopublish permission. Deterministic tests and dry routing can use
`--no-fetch` to build the same packet shape without external reads.

The packet also carries `content_ops_connector_runtime_policy_v0`. A live
browser connector trial against X showed that opening a normal public profile
page can autoload timelines, post text, media streams, analytics, and
engagement data. Therefore the safe default for public-handle metadata intake
is `head_only_metadata_probe`; browser opening is not the default metadata path.
For reusable X research, draft, and gated posting behavior, use
[`x_public_channel_ops_v0`](x-public-channel-ops-v0.md). Account-specific launch
calendars, exact post bodies, mentions, and operator skills belong in ignored
local state or user-local Codex skills, not in the public repository.

Private connectors use a gate-projection command before any source access:

```bash
loopx content-ops project-private-connector-gate \
  --connector-id chatlog_alpha_chatview \
  --connector-name chatlog-alpha/chatview \
  --surface wechat_private_archive \
  --proposed-source-item-id source_wechat_metadata_signal_001 \
  --format json
```

It returns `content_ops_private_connector_gate_packet_v0` with an
`owner_gate`, a metadata-only `source_item_v0` placeholder, and a concrete
`user_todo_projection`. It performs no external read, no private source-content
read, no external write, and no publish action. The only safe next action is to
surface the owner decision: approve metadata-only intake, reject it, or request
a narrower source handle. Real chatlog-alpha/chatview ingestion must stay
behind that gate.

The private gate packet also carries `content_ops_connector_runtime_policy_v0`.
A live browser connector trial against the public ChatView entrypoint showed
that the default web app route can autoload message-list and message-detail API
requests. LoopX must therefore not browser-open that default route before owner
approval. Before approval, the runtime policy forbids paths such as
`/api/messages`, `/api/reports`, and `/api/channel-state`; connector work is
limited to storing the compact gate packet, surfacing the owner question, and
fixture-only smoke coverage.

Once an owner explicitly approves a bounded ChatView trial, turn only the
approved counts and path classes into a visible operator card:

```bash
loopx content-ops project-chatview-report \
  --channel-count 2 \
  --recent-record-count 50 \
  --report-count 5 \
  --api-request-count 54 \
  --api-path-count /api/channels=1 \
  --api-path-count /api/messages=1 \
  --api-path-count /api/channel-state=1 \
  --api-path-count /api/reports=1 \
  --api-path-count /api/messages/:id=50 \
  --format json
```

It returns an aggregation-compatible
`content_ops_private_connector_gate_packet_v0` with a
`content_ops_chatview_connector_report_v0` operator card. The command does not
open ChatView, does not save response payloads, does not emit source bodies, and
does not authorize publication. Its output can be passed directly to
`aggregate-packets` as a `--private-gate-packet-json` input.

Connector packets can then be aggregated into the compact state surface:

```bash
loopx content-ops aggregate-packets \
  --public-packet-json public-handle-packet.json \
  --private-gate-packet-json private-connector-gate-packet.json \
  --surface-id content_ops_connector_packet_aggregation \
  --format json
```

It returns `content_ops_packet_aggregation_v0` with a generated
`content_ops_surface_v0`, its read-only projection, validation details, and
boundary booleans. The aggregation does not re-open connector URLs, read source
bodies, read private material, write externally, or authorize publication. A
public packet becomes a `metadata_packet_collected` connector trial, while a
private gate packet remains `needs_owner_gate`; this prevents the projection
from scheduling another metadata trial after a public packet has already been
collected.

For an operator-visible end-to-end artifact, generate the walkthrough packet:

```bash
loopx content-ops walkthrough-artifact \
  --public-handle-url https://x.com/OpenAI \
  --channel-count 2 \
  --recent-record-count 50 \
  --report-count 2 \
  --api-request-count 54 \
  --api-path-count /api/channels=1 \
  --api-path-count /api/messages=1 \
  --api-path-count /api/channel-state=1 \
  --api-path-count /api/reports=1 \
  --api-path-count /api/messages/:id=50 \
  --private-preview-item-count 12 \
  --theme-signal "market-risk watch" \
  --theme-signal "semiconductor earnings pressure" \
  --format json
```

It returns `content_ops_walkthrough_artifact_v0`: public source cards, a
ChatView operator card, aggregate projection, chain steps, draft gate, and a
private operator preview summary. The preview summary may say how many private
records were inspected locally and list operator-curated theme labels, but it
must not persist source content, response payloads, local paths, credentials, or
publication authority. This is the public-safe artifact shape for showing value:
the user can see the live private material in the current operator session, while
the repository records only compact counts, labels, gates, and validation.

The durable smoke is:

```bash
python3 examples/content-ops-surface-fixture-smoke.py
python3 examples/content-ops-preview-cli-smoke.py
python3 examples/content-ops-public-handle-observation-smoke.py
python3 examples/content-ops-private-connector-gate-smoke.py
python3 examples/content-ops-packet-aggregation-smoke.py
python3 examples/content-ops-chatview-report-smoke.py
python3 examples/content-ops-walkthrough-artifact-smoke.py
```

The smoke checks record coverage, source/draft/gate references, first-screen
projection fields, connector metadata-trial routing, todo candidates,
no-autopublish policy, public/private boundary hygiene, and the public-handle
adapter's no-content/no-write guarantees. It also verifies that private
connector intake projects an owner gate and a runtime deny policy before any
private source-content read, and that packet aggregation promotes only compact
source/gate records into the state surface. The ChatView report smoke verifies
that a real-trial-shaped operator card remains metadata-only and can be
aggregated without source bodies or response payloads. The walkthrough smoke
verifies that the final operator artifact remains public-safe while still
showing a concrete source-to-surface-to-draft-gate chain. A live X HEAD probe is
available only when `LOOPX_LIVE_PUBLIC_HANDLE_SMOKE=1` is explicitly set.
