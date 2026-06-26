# x_public_channel_ops_v0

Status: public-safe connector and publish-gate protocol v0.

`x_public_channel_ops_v0` defines how LoopX can support public X/Twitter
research, draft preparation, and approved posting without storing raw platform
material or turning a local operator workflow into a public repo skill.

This protocol is intentionally generic. It does not encode a specific account,
posting calendar, influencer list, launch copy, local browser profile, or
private source library.

## Boundary

LoopX may store compact channel-operation records:

- source handles and public URLs;
- whether a source read was metadata-only, public-content-read, or gated;
- post angle, source map, draft state, asset plan, and approval state;
- external-write result pointers, such as a public post URL after posting.

LoopX must not store:

- login cookies, browser profiles, credentials, or session artifacts;
- raw timelines, raw post bodies from private or login-gated surfaces, raw
  replies, analytics dumps, media streams, or screenshots with private state;
- account-specific growth lists, private operator notes, or exact launch
  schedules that only make sense for one maintainer;
- unapproved post bodies as if they were publish permission.

## Record Shape

### `x_source_observation_v0`

Compact source-intake record.

Required fields:

- `source_id`;
- `source_url`;
- `source_status`: `public`, `public_metadata_only`,
  `login_gated_needs_owner_review`, or `forbidden`;
- `read_mode`: `head_only_metadata`, `public_body_read`,
  `browser_observation`, or `no_read`;
- `allowed_use`: `metadata_only`, `summarize_and_transform`,
  `do_not_quote`, or `forbidden`;
- `terms_note`;
- `next_gate`.

Default to `head_only_metadata` for public handles. Browser observation is not
the default because opening X pages can autoload timelines, media, analytics,
and engagement data.

### `x_draft_packet_v0`

No-send draft packet.

Required fields:

- `target_reader`;
- `angle_family`;
- `source_map`;
- `post_body`;
- `asset_plan`;
- `repo_or_product_link`;
- `mention_plan`;
- `timing_window`;
- `anti_spam_checks`;
- `publish_gate_id`.

The packet may be shared for review, but it is not publish permission.

### `x_publish_gate_v0`

Explicit human approval record.

Required fields:

- `gate_id`;
- `approval_required=true`;
- `autopublish_allowed=false`;
- `approved_body_hash`;
- `approved_assets`;
- `approved_time_window`;
- `approved_account_or_identity`;
- `revocation_check`;
- `stop_conditions`.

Posting may proceed only when the current user/controller approval matches the
exact body, assets, account identity, and time window.

### `x_publish_result_v0`

Compact result after an approved external write.

Required fields:

- `published`;
- `post_url` when visible;
- `posted_at`;
- `account_identity_status`;
- `asset_upload_status`;
- `first_hour_monitor_plan`;
- `blocker` when not posted.

Do not store cookies, upload payloads, raw screenshots, or engagement dumps.

## Posting-Time Policy

Timing is a recommendation, not permission. Agents should re-research current
platform guidance when timing materially affects a launch.

Generic default:

- For US/EU developer-tool audiences, prefer weekday 9:00-11:00 US Eastern
  when the post should reach US East morning and Europe afternoon.
- Tuesday to Thursday is usually stronger than Friday.
- If constrained to the next 24 hours, choose the next available weekday
  9:00-11:00 US Eastern slot and leave 30-60 minutes for replies.
- Record the timezone conversion in `x_draft_packet_v0.timing_window`.
- If the chosen time is outside the preferred window, mark it as a user or
  business constraint rather than a platform optimum.

## Content Rules

For LoopX launch or education content:

- name the category as `loop engineering` when that is the claim;
- define "control plane" as state, gates, evidence, quota, and handoff around
  an agent loop, not merely a dashboard or front end;
- emphasize local-first adoption when the conversion goal is repo visits or
  installation;
- include a repository/product link when making an open-source claim;
- use one strong visual when it helps the reader understand the mechanism;
- mention people sparingly and only when the post is relevant to their public
  work or current conversation.

Avoid:

- mass tagging;
- repeated generic replies;
- unsubstantiated benchmark, revenue, or customer claims;
- private screenshots or raw operator state;
- publishing from an account whose identity, login state, or approval boundary
  is uncertain.

## Ego-Lite Browser Use

`ego-lite browser` may be used as a user-controlled browser channel when it is
installed and the user has logged in. It is a runtime channel, not a durable
public repo dependency.

Before using it for X:

1. Verify the requested action is inside an approved `x_publish_gate_v0`.
2. Verify the account identity is acceptable for the post.
3. Upload only approved assets.
4. Stop for captcha, credentials, identity confusion, upload failure, or a
   changed post body.
5. After posting, record only `x_publish_result_v0` compact fields.

## Anti-Spam And Reply Policy

For cold or low-reputation accounts:

- each reply must have target-specific evidence in the first paragraph;
- the ask must be concrete and low-pressure;
- stop after one reply unless the owner engages;
- if a public comment or post is minimized as spam, do not bump, repost, edit,
  delete, or appeal without explicit owner approval.

Public lead monitoring should prefer metadata-only checks such as state,
comment count, minimized status, author association, and updated timestamp
until an owner approves body reads.

## Fit With `content_ops_surface_v0`

This protocol specializes the generic content-ops records:

- `x_source_observation_v0` is a source-specific `source_item_v0`;
- `x_draft_packet_v0` is a source-mapped `draft_item_v0`;
- `x_publish_gate_v0` is a channel-specific `publish_gate_v0`;
- `x_publish_result_v0` is compact external evidence after a gated write.

Use this protocol for public product behavior and reusable connector guidance.
Keep maintainer-specific social-media skills, exact launch calendars, and
account operating notes in ignored local state or user-local Codex skills.
